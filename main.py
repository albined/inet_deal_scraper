"""
Autonomous Inet Product Monitor Bot

This bot monitors the Inet Twitch channel for campaign links,
scrapes products from those campaigns, and posts them to Discord.
"""

import os
import asyncio
import re
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from twitchio.ext import commands
from fnmatch import fnmatch

from inet_scraper import InetProductMonitor
from discord_bot import InetDiscordBot

# Load environment variables
load_dotenv()


class TwitchTokenManager:
    """Manages Twitch OAuth token refresh"""
    
    def __init__(self, refresh_token):
        self.refresh_token = refresh_token
        self.token = None
        self.expiration_date = None
        self._refresh_token()
    
    def _refresh_token(self):
        """Refresh the token using the Twitch token generator API"""
        url = f"https://twitchtokengenerator.com/api/refresh/{self.refresh_token}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                self.token = data.get('token')
                if 'refresh' in data:
                    self.refresh_token = data.get('refresh')
                self.expiration_date = datetime.now() + timedelta(days=59)
                print(f"✓ Twitch token refreshed successfully. Expires on: {self.expiration_date.strftime('%Y-%m-%d')}")
            else:
                raise Exception("Token refresh failed")
                
        except requests.RequestException as e:
            print(f"❌ Error refreshing token: {e}")
            raise
    
    def get_token(self):
        """Get the current token, refreshing if expired"""
        if self.expiration_date is None or datetime.now() >= self.expiration_date:
            print("Token expired or not set, refreshing...")
            self._refresh_token()
        return self.token
    
    def __str__(self):
        return self.get_token()


class TwitchStreamChecker:
    """Checks if a Twitch channel is live"""
    
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self._get_app_access_token()
    
    def _get_app_access_token(self):
        """Gets an app access token from Twitch"""
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        try:
            response = requests.post("https://id.twitch.tv/oauth2/token", params=params)
            response.raise_for_status()
            self.access_token = response.json()["access_token"]
            print("✓ Twitch app access token obtained")
        except requests.RequestException as e:
            print(f"❌ Error getting access token: {e}")
            raise
    
    def is_channel_live(self, channel_name):
        """Check if a channel is currently live"""
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {"user_login": channel_name}
        try:
            response = requests.get("https://api.twitch.tv/helix/streams", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return bool(data.get("data"))
        except requests.RequestException as e:
            print(f"⚠️ Error checking stream status: {e}")
            return False


class InetMonitorBot(commands.Bot):
    """Twitch bot that monitors chat for Inet campaign links"""
    
    def __init__(self, token_manager, channel, link_template, inet_monitor, discord_bot, scrape_interval):
        super().__init__(
            token=str(token_manager),
            prefix='!',
            initial_channels=[channel]
        )
        self.token_manager = token_manager
        self.channel_name = channel
        self.link_template = link_template
        self.inet_monitor = inet_monitor
        self.discord_bot = discord_bot
        self.scrape_interval = scrape_interval
        self.seen_links = set()
        self.scrape_task = None
        self.is_monitoring = False
    
    async def event_ready(self):
        """Called once when the bot goes online"""
        print(f'✓ Twitch bot logged in as {self.nick}')
        print(f'✓ Monitoring chat in #{self.channel_name}')
        print(f'✓ Looking for links matching: {self.link_template}')
        self.is_monitoring = True
        
        # Start periodic scraping task
        if self.scrape_task is None or self.scrape_task.done():
            self.scrape_task = asyncio.create_task(self._periodic_scrape())
    
    async def event_message(self, message):
        """Called for every message in chat"""
        if message.echo:
            return
        
        # Look for links matching the template
        links = self._extract_links(message.content)
        
        if links:
            print(f'🔗 [{message.author.name}]: Found {len(links)} link(s)')
            for link in links:
                if link not in self.seen_links:
                    print(f'   🆕 New link: {link}')
                    self.seen_links.add(link)
                    self.inet_monitor.add_page(link)
                    # Trigger immediate scrape
                    await self._scrape_and_post()
                else:
                    print(f'   ⏭️  Already tracking: {link}')
                    # Still scrape even if we've seen the link before
                    await self._scrape_and_post()
    
    def _extract_links(self, message):
        """Extract URLs from message that match the template"""
        # Find all URLs in the message
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message)
        
        # Filter URLs that match the template
        matching_urls = []
        for url in urls:
            if fnmatch(url, self.link_template):
                matching_urls.append(url)
        
        return matching_urls
    
    async def _scrape_and_post(self):
        """Scrape for new products and post to Discord"""
        try:
            print(f'\n🔍 Scraping for new products...')
            new_products = self.inet_monitor.check_for_new_products()
            
            if new_products:
                print(f'📤 Posting {len(new_products)} new product(s) to Discord...')
                await self.discord_bot.send_products(new_products)
            else:
                print('✓ No new products found')
                
        except Exception as e:
            print(f'❌ Error during scrape: {e}')
    
    async def _periodic_scrape(self):
        """Periodically scrape for new products"""
        print(f'⏰ Starting periodic scraping (every {self.scrape_interval} seconds)')
        
        while self.is_monitoring:
            await asyncio.sleep(self.scrape_interval)
            
            if self.is_monitoring and self.inet_monitor.pages_to_check:
                await self._scrape_and_post()
    
    def stop_monitoring(self):
        """Stop monitoring and cancel scraping task"""
        print('⏸️  Stopping Twitch chat monitoring...')
        self.is_monitoring = False
        if self.scrape_task and not self.scrape_task.done():
            self.scrape_task.cancel()


async def main():
    """Main application loop"""
    
    print("="*70)
    print("🤖 INET PRODUCT MONITOR BOT")
    print("="*70)
    print()
    
    # Load configuration
    twitch_channel = os.getenv('TWITCH_CHANNEL')
    twitch_refresh_token = os.getenv('TWITCH_REFRESH_TOKEN')
    twitch_client_id = os.getenv('TWITCH_CLIENT_ID')
    twitch_client_secret = os.getenv('TWITCH_CLIENT_SECRET')
    online_check_interval = int(os.getenv('TWITCH_ONLINE_CHECK_INTERVAL', 300))
    scrape_interval = int(os.getenv('SCRAPE_INTERVAL', 120))
    link_template = os.getenv('LINK_TEMPLATE', 'https://www.inet.se/kampanj/*')
    
    inet_email = os.getenv('INET_EMAIL')
    inet_password = os.getenv('INET_PASSWORD')
    
    print("📋 Configuration:")
    print(f"   Twitch Channel: {twitch_channel}")
    print(f"   Online Check Interval: {online_check_interval}s")
    print(f"   Scrape Interval: {scrape_interval}s")
    print(f"   Link Template: {link_template}")
    print()
    
    # Initialize components
    print("🚀 Initializing components...")
    
    # Initialize Inet monitor
    inet_monitor = InetProductMonitor(
        email=inet_email,
        password=inet_password
    )
    
    # Initialize Discord bot (pass monitor reference for !links command)
    discord_bot = InetDiscordBot(inet_monitor=inet_monitor)
    
    # Start Discord bot in background
    discord_task = asyncio.create_task(discord_bot.start())
    
    # Wait for Discord bot to be ready
    while not discord_bot.is_ready():
        await asyncio.sleep(1)
    
    print("✓ All components initialized!")
    print()
    
    # Initialize Twitch components
    token_manager = TwitchTokenManager(twitch_refresh_token)
    stream_checker = TwitchStreamChecker(twitch_client_id, twitch_client_secret)
    
    # Main monitoring loop
    twitch_bot = None
    twitch_bot_task = None
    was_live = False
    
    print("="*70)
    print("🎬 STARTING MONITORING LOOP")
    print("="*70)
    print()
    
    try:
        while True:
            # Check if channel is live
            is_live = stream_checker.is_channel_live(twitch_channel)

            if is_live and not was_live:
                print(f'\n🔴 {twitch_channel} is now LIVE! Starting chat monitoring...\n')
                
                # Create and start Twitch bot
                twitch_bot = InetMonitorBot(
                    token_manager=token_manager,
                    channel=twitch_channel,
                    link_template=link_template,
                    inet_monitor=inet_monitor,
                    discord_bot=discord_bot,
                    scrape_interval=scrape_interval
                )
                
                # Start the Twitch bot
                twitch_bot_task = asyncio.create_task(twitch_bot.start())
                was_live = True
                
            elif not is_live and was_live:
                print(f'\n⚫ {twitch_channel} went OFFLINE. Stopping chat monitoring...\n')
                
                # Stop and cleanup Twitch bot
                if twitch_bot:
                    twitch_bot.stop_monitoring()
                    await twitch_bot.close()
                
                if twitch_bot_task and not twitch_bot_task.done():
                    twitch_bot_task.cancel()
                    try:
                        await twitch_bot_task
                    except asyncio.CancelledError:
                        pass
                
                twitch_bot = None
                twitch_bot_task = None
                was_live = False
                
            elif is_live:
                # Channel is still live
                pass
            else:
                # Channel is still offline
                if not was_live:
                    # Only print this occasionally
                    pass
            
            # Wait before next check
            await asyncio.sleep(online_check_interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        
        # Cleanup Twitch bot
        if twitch_bot:
            twitch_bot.stop_monitoring()
            await twitch_bot.close()
        
        if twitch_bot_task and not twitch_bot_task.done():
            twitch_bot_task.cancel()
        
        # Cleanup Discord bot
        await discord_bot.close()
        
        if discord_task and not discord_task.done():
            discord_task.cancel()
        
        print("✓ Cleanup complete. Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
