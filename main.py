"""
Autonomous Inet Product Monitor Bot

This bot monitors the Inet Twitch channel for campaign links,
scrapes products from those campaigns, and posts them to Discord.
"""

import os
import asyncio
import re
import requests
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from twitchio.ext import commands
from fnmatch import fnmatch
import yt_dlp
import pytchat
from pytchat import InvalidVideoIdException
import time

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


class YouTubeMonitor:
    """Monitors YouTube channel for live streams and chat messages containing links"""
    
    def __init__(self, channel_url, link_template, inet_monitor, discord_bot, 
                 stream_check_interval=600, chat_check_interval=5, 
                 inactive_chat_interval=600, inactive_threshold=300):
        """
        Initialize the YouTube monitor
        
        Args:
            channel_url: YouTube channel URL (e.g., "https://www.youtube.com/@inet")
            link_template: Pattern for matching links (e.g., "https://www.inet.se/kampanj/*")
            inet_monitor: Reference to InetProductMonitor instance
            discord_bot: Reference to InetDiscordBot instance
            stream_check_interval: How often to check for streams when not live (seconds)
            chat_check_interval: How often to check chat when active (seconds)
            inactive_chat_interval: How often to check chat when inactive (seconds)
            inactive_threshold: Time without messages before considering chat inactive (seconds)
        """
        self.channel_url = channel_url
        self.link_template = link_template
        self.inet_monitor = inet_monitor
        self.discord_bot = discord_bot
        self.stream_check_interval = stream_check_interval
        self.chat_check_interval = chat_check_interval
        self.inactive_chat_interval = inactive_chat_interval
        self.inactive_threshold = inactive_threshold
        
        # State tracking
        self.seen_links = set()
        self.current_date = date.today()
        self.active_streams = {}  # video_id -> {'chat': pytchat_obj, 'last_message_time': timestamp}
        self.is_monitoring = False
        self.monitor_task = None
        
        # yt-dlp options
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
    
    def _check_date_reset(self):
        """Check if it's a new day and reset seen links if needed"""
        today = date.today()
        if today != self.current_date:
            print(f'📅 New day detected! Resetting YouTube seen links...')
            self.seen_links.clear()
            self.current_date = today
    
    def _get_live_video_id(self):
        """
        Check if the channel is live and return the video ID if so
        
        Returns:
            str or None: Video ID if live, None otherwise
        """
        live_url = f"{self.channel_url}/live"
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(live_url, download=False)
                video_id = info.get('id')
                if video_id:
                    return video_id
        except yt_dlp.utils.DownloadError:
            # Not live or error occurred
            pass
        except Exception as e:
            print(f'⚠️ Error checking YouTube live status: {e}')
        
        return None
    
    def _extract_links(self, message):
        """Extract URLs from message that match the template"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message)
        
        matching_urls = []
        for url in urls:
            if fnmatch(url, self.link_template):
                matching_urls.append(url)
        
        return matching_urls
    
    async def _scrape_and_post(self):
        """Scrape for new products and post to Discord"""
        try:
            print(f'🔍 [YouTube] Scraping for new products...')
            new_products = self.inet_monitor.check_for_new_products()
            
            if new_products:
                print(f'📤 [YouTube] Posting {len(new_products)} new product(s) to Discord...')
                await self.discord_bot.send_products(new_products)
            else:
                print('✓ [YouTube] No new products found')
                
        except Exception as e:
            print(f'❌ [YouTube] Error during scrape: {e}')
    
    async def _monitor_chat(self, video_id):
        """
        Monitor a single video's chat for links
        
        Args:
            video_id: YouTube video ID to monitor
        """
        try:
            # Create chat connection
            chat = pytchat.create(video_id=video_id)
            self.active_streams[video_id] = {
                'chat': chat,
                'last_message_time': time.time()
            }
            
            print(f'💬 [YouTube] Started monitoring chat for video: {video_id}')
            
            while chat.is_alive() and self.is_monitoring:
                try:
                    # Check if it's a new day
                    self._check_date_reset()
                    
                    # Get chat messages
                    data = chat.get()
                    
                    if data.items:
                        # Update last message time
                        self.active_streams[video_id]['last_message_time'] = time.time()
                        
                        for message in data.items:
                            # Extract and process links
                            links = self._extract_links(message.message)
                            
                            if links:
                                print(f'🔗 [YouTube] [{message.author.name}]: Found {len(links)} link(s)')
                                for link in links:
                                    if link not in self.seen_links:
                                        print(f'   🆕 [YouTube] New link: {link}')
                                        self.seen_links.add(link)
                                        self.inet_monitor.add_page(link)
                                        # Trigger immediate scrape
                                        await self._scrape_and_post()
                                    else:
                                        print(f'   ⏭️  [YouTube] Already tracking: {link}')
                                        # Still scrape even if we've seen the link before
                                        await self._scrape_and_post()
                    
                    # Determine sleep interval based on chat activity
                    time_since_last_message = time.time() - self.active_streams[video_id]['last_message_time']
                    
                    if time_since_last_message > self.inactive_threshold:
                        # Chat is inactive, check less frequently
                        await asyncio.sleep(self.inactive_chat_interval)
                    else:
                        # Chat is active, check more frequently
                        await asyncio.sleep(self.chat_check_interval)
                
                except Exception as e:
                    print(f'⚠️ [YouTube] Error processing chat messages: {e}')
                    await asyncio.sleep(self.chat_check_interval)
            
            # Cleanup
            chat.terminate()
            if video_id in self.active_streams:
                del self.active_streams[video_id]
            print(f'💤 [YouTube] Stopped monitoring chat for video: {video_id}')
            
        except InvalidVideoIdException:
            print(f'❌ [YouTube] Invalid video ID: {video_id} - removing from monitoring')
            if video_id in self.active_streams:
                del self.active_streams[video_id]
        except Exception as e:
            print(f'❌ [YouTube] Error setting up chat monitor for {video_id}: {e}')
            if video_id in self.active_streams:
                del self.active_streams[video_id]
    
    async def _monitoring_loop(self):
        """Main monitoring loop for YouTube streams"""
        print(f'🎥 [YouTube] Starting monitoring loop for {self.channel_url}')
        print(f'   Stream check interval: {self.stream_check_interval}s')
        print(f'   Active chat interval: {self.chat_check_interval}s')
        print(f'   Inactive chat interval: {self.inactive_chat_interval}s')
        
        while self.is_monitoring:
            try:
                # Check for date reset
                self._check_date_reset()
                
                # Check if channel is live
                video_id = self._get_live_video_id()
                
                if video_id:
                    # Stream is live
                    if video_id not in self.active_streams:
                        print(f'🔴 [YouTube] Live stream detected! Video ID: {video_id}')
                        # Start monitoring this stream's chat
                        asyncio.create_task(self._monitor_chat(video_id))
                    # If already monitoring, the chat task will continue
                else:
                    # No live stream currently
                    pass
                
                # Wait before checking again
                await asyncio.sleep(self.stream_check_interval)
                
            except Exception as e:
                print(f'❌ [YouTube] Error in monitoring loop: {e}')
                await asyncio.sleep(self.stream_check_interval)
    
    def start_monitoring(self):
        """Start the YouTube monitoring"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_task = asyncio.create_task(self._monitoring_loop())
            print('✓ [YouTube] Monitoring started')
    
    def stop_monitoring(self):
        """Stop the YouTube monitoring"""
        print('⏸️  [YouTube] Stopping monitoring...')
        self.is_monitoring = False
        
        # Terminate all active chat monitors
        for video_id, stream_info in list(self.active_streams.items()):
            try:
                stream_info['chat'].terminate()
            except:
                pass
        
        self.active_streams.clear()
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
        
        print('✓ [YouTube] Monitoring stopped')


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
    
    # YouTube configuration
    youtube_channel_url = os.getenv('YOUTUBE_CHANNEL_URL', 'https://www.youtube.com/@inet')
    youtube_stream_check_interval = int(os.getenv('YOUTUBE_STREAM_CHECK_INTERVAL', 600))
    youtube_chat_check_interval = int(os.getenv('YOUTUBE_CHAT_CHECK_INTERVAL', 5))
    youtube_inactive_chat_interval = int(os.getenv('YOUTUBE_INACTIVE_CHAT_INTERVAL', 600))
    youtube_inactive_threshold = int(os.getenv('YOUTUBE_INACTIVE_THRESHOLD', 300))
    
    inet_email = os.getenv('INET_EMAIL')
    inet_password = os.getenv('INET_PASSWORD')
    
    print("📋 Configuration:")
    print(f"   Twitch Channel: {twitch_channel}")
    print(f"   Twitch Online Check Interval: {online_check_interval}s")
    print(f"   Scrape Interval: {scrape_interval}s")
    print(f"   Link Template: {link_template}")
    print(f"   YouTube Channel: {youtube_channel_url}")
    print(f"   YouTube Stream Check Interval: {youtube_stream_check_interval}s")
    print()
    
    # Initialize components
    print("🚀 Initializing components...")
    
    # Initialize Inet monitor
    inet_monitor = InetProductMonitor(
        email=inet_email,
        password=inet_password
    )
    
    # Shared state for status tracking
    status_state = {
        'is_live': False,
        'is_monitoring': False,
        'last_online': None,
        'channel_name': twitch_channel
    }
    
    # Status provider function for Discord bot
    def get_status():
        """Provide current bot status information"""
        return {
            'is_live': status_state['is_live'],
            'is_monitoring': status_state['is_monitoring'],
            'last_online': status_state['last_online'],
            'channel_name': status_state['channel_name']
        }
    
    # Initialize Discord bot (pass monitor reference and status provider)
    # Note: youtube_monitor will be set after initialization
    discord_bot = InetDiscordBot(
        inet_monitor=inet_monitor,
        status_provider=get_status
    )
    
    # Initialize Twitch components
    token_manager = TwitchTokenManager(twitch_refresh_token)
    stream_checker = TwitchStreamChecker(twitch_client_id, twitch_client_secret)
    
    # Initialize YouTube monitor
    youtube_monitor = YouTubeMonitor(
        channel_url=youtube_channel_url,
        link_template=link_template,
        inet_monitor=inet_monitor,
        discord_bot=discord_bot,
        stream_check_interval=youtube_stream_check_interval,
        chat_check_interval=youtube_chat_check_interval,
        inactive_chat_interval=youtube_inactive_chat_interval,
        inactive_threshold=youtube_inactive_threshold
    )
    
    # Set youtube_monitor reference in Discord bot after initialization
    discord_bot.youtube_monitor = youtube_monitor
    
    # Start Discord bot in background
    discord_task = asyncio.create_task(discord_bot.start())
    
    # Wait for Discord bot to be ready
    while not discord_bot.is_ready():
        await asyncio.sleep(1)
    
    print("✓ All components initialized!")
    print()
    
    # Start YouTube monitoring (runs independently)
    youtube_monitor.start_monitoring()
    
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
            
            # Update status state
            status_state['is_live'] = is_live

            if is_live and not was_live:
                print(f'\n🔴 {twitch_channel} is now LIVE! Starting chat monitoring...\n')
                
                # Update last online timestamp
                from datetime import datetime
                status_state['last_online'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                
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
                status_state['is_monitoring'] = True
                
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
                status_state['is_monitoring'] = False
                
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
        
        # Cleanup YouTube monitor
        youtube_monitor.stop_monitoring()
        
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
