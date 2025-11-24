import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import asyncio
import re
from subscriber_db import SubscriberDatabase

class InetDiscordBot:
    """
    A Discord bot that posts product notifications from Inet.se
    
    Features:
    - Posts products with embedded images and formatted information
    - Slash commands: /subscribe, /unsubscribe, /status, /help, /links, /resend, /clear, /addlink
    - Subscription-based notifications (channels and DMs)
    - Persistent subscriber storage across restarts
    """
    
    def __init__(self, token: Optional[str] = None, inet_monitor=None, youtube_monitor=None, status_provider=None, db_path: str = "subscribers.json"):
        """
        Initialize the Discord bot
        
        Args:
            token: Discord bot token (loads from .env if not provided)
            inet_monitor: Reference to InetProductMonitor instance (optional)
            youtube_monitor: Reference to YouTubeMonitor instance (optional)
            status_provider: Callable that returns status information (optional)
            db_path: Path to subscriber database file (default: subscribers.json)
        """
        # Load environment variables if not provided
        if token is None:
            load_dotenv()
            token = token or os.getenv('DISCORD_TOKEN_URL')
        
        self.token = token
        self.subscriber_db = SubscriberDatabase(db_path)  # Persistent subscriber storage
        self.inet_monitor = inet_monitor  # Reference to monitor for checking pages
        self.youtube_monitor = youtube_monitor  # Reference to YouTube monitor
        self.status_provider = status_provider  # Function to get additional status info
        
        # Set up Discord bot with message content intent
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
        
        # Register event handlers
        self._register_events()
        self._register_commands()
    
    def _register_events(self):
        """Register bot event handlers"""
        
        @self.bot.event
        async def on_ready():
            print(f'✓ Discord bot logged in as {self.bot.user}')
            print(f'✓ Subscribers loaded: {self.subscriber_db.get_count()}')
            
            # Sync slash commands
            try:
                synced = await self.bot.tree.sync()
                print(f'✓ Synced {len(synced)} slash command(s)')
            except Exception as e:
                print(f'❌ Error syncing commands: {e}')
    
    def _register_commands(self):
        """Register bot slash commands"""
        
        @self.bot.tree.command(name='subscribe', description='Subscribe to product notifications')
        async def subscribe_command(interaction: discord.Interaction):
            """Subscribe the current channel or DM to product notifications"""
            # Get the target ID (channel or DM)
            target_id = interaction.channel_id
            
            # Check if already subscribed
            if self.subscriber_db.is_subscribed(target_id):
                await interaction.response.send_message("✓ This location is already **subscribed** to notifications!")
            else:
                self.subscriber_db.add_subscriber(target_id)
                location_type = "DM" if isinstance(interaction.channel, discord.DMChannel) else "channel"
                await interaction.response.send_message(f"✅ **Subscribed!** This {location_type} will now receive product notifications.")
                print(f"New subscriber: {target_id} ({location_type})")
        
        @self.bot.tree.command(name='unsubscribe', description='Unsubscribe from product notifications')
        async def unsubscribe_command(interaction: discord.Interaction):
            """Unsubscribe the current channel or DM from product notifications"""
            # Get the target ID (channel or DM)
            target_id = interaction.channel_id
            
            # Check if subscribed
            if not self.subscriber_db.is_subscribed(target_id):
                await interaction.response.send_message("✓ This location is not subscribed to notifications.")
            else:
                self.subscriber_db.remove_subscriber(target_id)
                location_type = "DM" if isinstance(interaction.channel, discord.DMChannel) else "channel"
                await interaction.response.send_message(f"✅ **Unsubscribed!** This {location_type} will no longer receive product notifications.")
                print(f"Unsubscribed: {target_id} ({location_type})")
        
        @self.bot.tree.command(name='status', description='Check bot status and system information')
        async def status_command(interaction: discord.Interaction):
            """Check bot status and system information"""
            # Get current channel/DM subscription status
            target_id = interaction.channel_id
            is_subscribed = self.subscriber_db.is_subscribed(target_id)
            
            # Create an embed for better formatting
            embed = discord.Embed(
                title="🤖 Bot Status",
                color=discord.Color.green() if is_subscribed else discord.Color.orange()
            )
            
            # Current location subscription status
            location_type = "DM" if isinstance(interaction.channel, discord.DMChannel) else "channel"
            subscription_status = f"**SUBSCRIBED** ✅" if is_subscribed else f"**NOT SUBSCRIBED** ❌"
            embed.add_field(name=f"This {location_type}", value=subscription_status, inline=False)
            
            # Total subscribers
            total_subscribers = self.subscriber_db.get_count()
            embed.add_field(name="📢 Total Subscribers", value=str(total_subscribers), inline=True)
            
            # Get additional status from provider if available
            if self.status_provider:
                try:
                    status_info = self.status_provider()
                    
                    # Twitch channel status
                    if 'is_live' in status_info:
                        twitch_status = "🔴 **LIVE**" if status_info['is_live'] else "⚫ **OFFLINE**"
                        embed.add_field(name="Twitch Channel", value=twitch_status, inline=True)
                    
                    # Last seen online
                    if 'last_online' in status_info and status_info['last_online']:
                        embed.add_field(name="Last Online", value=status_info['last_online'], inline=True)
                    
                    # Monitoring status
                    if 'is_monitoring' in status_info:
                        monitoring = "✅ Active" if status_info['is_monitoring'] else "⏸️ Paused"
                        embed.add_field(name="Chat Monitoring", value=monitoring, inline=True)
                    
                except Exception as e:
                    print(f"Error getting status info: {e}")
            
            # Product tracking info
            if self.inet_monitor:
                pages_count = len(self.inet_monitor.pages_to_check)
                product_count = self.inet_monitor.get_product_count()
                
                embed.add_field(name="📋 Campaigns", value=str(pages_count), inline=True)
                embed.add_field(name="📦 Products Tracked", value=str(product_count), inline=True)
                embed.add_field(name="📅 Tracking Date", value=str(self.inet_monitor.current_date), inline=True)
            
            # Add timestamp
            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text="Bot Status")
            
            await interaction.response.send_message(embed=embed)
        
        @self.bot.tree.command(name='help', description='Show help information')
        async def help_command(interaction: discord.Interaction):
            """Show help information"""
            help_text = """
**🤖 Inet Product Drop Bot**

I monitor Inet.se for new products and deals, and post them to all subscribed channels and DMs!

**Commands:**
• `/subscribe` - Subscribe this channel/DM to notifications
• `/unsubscribe` - Unsubscribe this channel/DM from notifications
• `/status` - Check subscription status and bot information
• `/links` - Show all campaign links being monitored
• `/addlink <link>` - Manually add a YouTube stream link to monitor
• `/resend` - Resend all tracked products
• `/clear [amount]` - Clear messages (default: 100)
• `/help` - Show this help message

**How it works:**
1. Use `/subscribe` in any channel or DM to receive notifications
2. I'll automatically post new products with:
   ✓ Product name (clickable link)
   ✓ Product image
   ✓ Pricing information
   ✓ Discount percentage (if applicable)
3. Use `/unsubscribe` to stop receiving notifications

**Note:** Subscriptions are saved and persist across bot restarts!

Stay tuned for great deals! 🎉
            """
            await interaction.response.send_message(help_text)
        
        @self.bot.tree.command(name='links', description='Show all campaign links being monitored')
        async def links_command(interaction: discord.Interaction):
            """Show all campaign links being monitored"""
            if not self.inet_monitor:
                await interaction.response.send_message("❌ Monitor not connected.")
                return
            
            pages = self.inet_monitor.pages_to_check
            product_count = self.inet_monitor.get_product_count()
            
            if not pages:
                await interaction.response.send_message("📭 No campaign links are currently being monitored.\n\n*Links are added automatically when posted in the Inet Twitch chat!*")
                return
            
            # Create a formatted list of links
            links_text = f"**📋 Currently Monitoring {len(pages)} Campaign(s)**\n"
            links_text += f"**Total Products Tracked: {product_count}**\n\n"
            
            for i, page in enumerate(pages, 1):
                # Shorten URL for display if too long
                display_url = page
                if len(page) > 60:
                    display_url = page[:57] + "..."
                links_text += f"{i}. {display_url}\n"
            
            links_text += f"\n*Scraping these pages every {os.getenv('SCRAPE_INTERVAL', '120')} seconds*"
            
            await interaction.response.send_message(links_text)
        
        @self.bot.tree.command(name='clear', description='Clear messages in the current channel')
        @app_commands.describe(amount='Number of messages to clear (default: 100, max: 1000)')
        async def clear_command(interaction: discord.Interaction, amount: int = 100):
            """Clear messages in the current channel"""
            try:
                # Check if bot has permission to manage messages
                if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
                    await interaction.response.send_message("❌ I don't have permission to delete messages! Please grant me 'Manage Messages' permission.", ephemeral=True)
                    return
                
                # Limit amount to prevent abuse
                if amount > 1000:
                    await interaction.response.send_message("⚠️ Can only clear up to 1000 messages at a time.", ephemeral=True)
                    amount = 1000
                
                # Defer the response since this might take a while
                await interaction.response.defer(ephemeral=True)
                
                # Delete messages
                deleted = await interaction.channel.purge(limit=amount)
                
                # Send confirmation
                await interaction.followup.send(f"✅ Cleared {len(deleted)} message(s)!", ephemeral=True)
                
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to delete messages!", ephemeral=True)
            except Exception as e:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ Error clearing messages: {e}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Error clearing messages: {e}", ephemeral=True)
        
        @self.bot.tree.command(name='addlink', description='Manually add a YouTube stream link to monitor')
        @app_commands.describe(link='YouTube video/stream URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)')
        async def addlink_command(interaction: discord.Interaction, link: str):
            """Manually add a YouTube stream link to monitor"""
            if not self.youtube_monitor:
                await interaction.response.send_message("❌ YouTube monitoring is not enabled on this bot.", ephemeral=True)
                return
            
            # Extract video ID from various YouTube URL formats
            video_id = None
            
            # Pattern 1: https://www.youtube.com/watch?v=VIDEO_ID
            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', link)
            if match:
                video_id = match.group(1)
            
            # Pattern 2: https://www.youtube.com/live/VIDEO_ID
            if not video_id:
                match = re.search(r'youtube\.com/live/([a-zA-Z0-9_-]{11})', link)
                if match:
                    video_id = match.group(1)
            
            if not video_id:
                await interaction.response.send_message(
                    "❌ **Invalid YouTube URL**\n\n"
                    "Please provide a valid YouTube video/stream URL:\n"
                    "• `https://www.youtube.com/watch?v=VIDEO_ID`\n"
                    "• `https://youtu.be/VIDEO_ID`\n"
                    "• `https://www.youtube.com/live/VIDEO_ID`",
                    ephemeral=True
                )
                return
            
            # Check if already monitoring this video
            if video_id in self.youtube_monitor.active_streams:
                await interaction.response.send_message(
                    f"ℹ️ Already monitoring stream: `{video_id}`\n"
                    f"Link: https://www.youtube.com/watch?v={video_id}",
                    ephemeral=True
                )
                return
            
            # Start monitoring this video
            await interaction.response.send_message(
                f"✅ **Added YouTube stream to monitoring!**\n\n"
                f"Video ID: `{video_id}`\n"
                f"Link: https://www.youtube.com/watch?v={video_id}\n\n"
                f"🔍 Starting chat monitoring for campaign links...",
                ephemeral=False
            )
            
            # Create monitoring task
            asyncio.create_task(self.youtube_monitor._monitor_chat(video_id))
            print(f"📺 [Discord Command] Manually added YouTube video for monitoring: {video_id}")
        
        @self.bot.tree.command(name='resend', description='Resend all currently tracked products')
        async def resend_command(interaction: discord.Interaction):
            """Resend all currently tracked products"""
            if not self.inet_monitor:
                await interaction.response.send_message("❌ Monitor not connected.", ephemeral=True)
                return
            
            all_products = self.inet_monitor.get_all_products()
            
            if not all_products:
                await interaction.response.send_message("📭 No products tracked yet!\n\n*Products are tracked when campaign links are posted in Twitch chat.*", ephemeral=True)
                return
            
            # Defer the response since this will take a while
            await interaction.response.defer()
            
            # Send initial message
            await interaction.followup.send(f"📤 Resending **{len(all_products)}** product(s)...\n*This may take a while!*")
            
            # Send all products
            sent_count = 0
            for product_id, product in all_products.items():
                try:
                    embed = self._create_product_embed(product)
                    await interaction.channel.send(embed=embed)
                    sent_count += 1
                    
                    # Delay to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"   ❌ Error resending product {product_id}: {e}")
            
            await interaction.followup.send(f"✅ Resent {sent_count} product(s)!")
    
    def _create_product_embed(self, product: Dict) -> discord.Embed:
        """
        Create a rich embed message for a product
        
        Args:
            product: Dictionary containing product information
            
        Returns:
            Discord Embed object
        """
        # Determine color based on discount
        if product.get('discount_percent'):
            if product['discount_percent'] >= 50:
                color = discord.Color.red()  # Hot deal!
            elif product['discount_percent'] >= 30:
                color = discord.Color.orange()  # Good deal
            else:
                color = discord.Color.blue()  # Regular discount
        else:
            color = discord.Color.green()  # New product
        
        # Create embed with product name as clickable title
        embed = discord.Embed(
            title=product.get('name', 'Unknown Product'),
            url=product.get('link', ''),
            color=color,
            description="New product available on Inet.se!"
        )
        
        # Set product image
        if product.get('image') and product['image'] != 'N/A':
            embed.set_image(url=product['image'])
        
        # Add price information
        if product.get('new_price'):
            price_text = f"**{product['new_price']:,} kr**".replace(',', ' ')
            
            if product.get('old_price'):
                old_price_text = f"~~{product['old_price']:,} kr~~".replace(',', ' ')
                price_text = f"{old_price_text} → {price_text}"
            
            embed.add_field(name="💰 Price", value=price_text, inline=True)
        
        # Add discount information
        if product.get('discount_percent'):
            embed.add_field(
                name="🔥 Discount", 
                value=f"**{product['discount_percent']}%** OFF!", 
                inline=True
            )
        
        # Add availability status
        availability = "❌ Sold Out" if product.get('sold_out') else "✅ In Stock"
        embed.add_field(name="📦 Availability", value=availability, inline=True)
        
        # Add footer
        embed.set_footer(text=f"Product ID: {product.get('id', 'N/A')}")
        
        return embed
    
    async def send_products(self, products: Dict[str, Dict]):
        """
        Send product notifications to all subscribed channels and DMs
        
        Args:
            products: Dictionary of products (product_id -> product_info)
        """
        if not products:
            print("No products to send.")
            return
        
        # Get all subscribers
        subscribers = self.subscriber_db.get_all_subscribers()
        
        if not subscribers:
            print(f"⚠️  No subscribers yet. {len(products)} product(s) not sent.")
            return
        
        print(f"📤 Sending {len(products)} product(s) to {len(subscribers)} subscriber(s)...")
        
        # Send to each subscriber
        for subscriber_id in subscribers:
            try:
                # Get the channel or user
                channel = self.bot.get_channel(subscriber_id)
                
                # If not a channel, try to get as user (for DMs)
                if not channel:
                    user = await self.bot.fetch_user(subscriber_id)
                    if user:
                        channel = user.dm_channel or await user.create_dm()
                
                if not channel:
                    print(f"   ⚠️  Could not find subscriber {subscriber_id}, skipping")
                    continue
                
                # Send all products to this subscriber
                for product_id, product in products.items():
                    try:
                        embed = self._create_product_embed(product)
                        await channel.send(embed=embed)
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        print(f"   ❌ Error sending product {product_id} to {subscriber_id}: {e}")
                
                print(f"   ✓ Sent {len(products)} product(s) to subscriber {subscriber_id}")
                
            except Exception as e:
                print(f"   ❌ Error accessing subscriber {subscriber_id}: {e}")
    
    def run(self):
        """Start the Discord bot (blocking)"""
        print("🚀 Starting Discord bot...")
        self.bot.run(self.token)
    
    async def start(self):
        """Start the Discord bot (non-blocking, for async usage)"""
        print("🚀 Starting Discord bot (async)...")
        await self.bot.start(self.token)
    
    async def close(self):
        """Close the Discord bot connection"""
        await self.bot.close()
    
    def is_ready(self) -> bool:
        """Check if the bot is ready"""
        return self.bot.is_ready()
    
    def __repr__(self):
        return f"InetDiscordBot(subscribers={self.subscriber_db.get_count()})"


# Example usage
if __name__ == "__main__":
    # Initialize bot (will load credentials from .env)
    bot = InetDiscordBot()
    
    # Example: Manually send test products
    # test_products = {
    #     "123": {
    #         "id": "123",
    #         "name": "Test Product",
    #         "link": "https://www.inet.se/product/123",
    #         "image": "https://example.com/image.jpg",
    #         "old_price": 1000,
    #         "new_price": 799,
    #         "discount_percent": 20.1,
    #         "sold_out": False
    #     }
    # }
    
    # To send products, you need to run in async context:
    # asyncio.run(bot.send_products(test_products))
    
    # Start the bot (this will block)
    bot.run()