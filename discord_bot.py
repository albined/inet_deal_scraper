import discord
from discord.ext import commands
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import asyncio

class InetDiscordBot:
    """
    A Discord bot that posts product notifications from Inet.se
    
    Features:
    - Posts products with embedded images and formatted information
    - Commands: !start, !stop, !status, !help (!h, !?)
    - Can be toggled on/off without restarting
    """
    
    def __init__(self, token: Optional[str] = None, channel_id: Optional[int] = None, inet_monitor=None, status_provider=None):
        """
        Initialize the Discord bot
        
        Args:
            token: Discord bot token (loads from .env if not provided)
            channel_id: Discord channel ID to post to (loads from .env if not provided)
            inet_monitor: Reference to InetProductMonitor instance (optional)
            status_provider: Callable that returns status information (optional)
        """
        # Load environment variables if not provided
        if token is None or channel_id is None:
            load_dotenv()
            token = token or os.getenv('DISCORD_TOKEN_URL')
            channel_id = channel_id or int(os.getenv('DISCORD_CHANNEL_ID'))
        
        self.token = token
        self.channel_id = channel_id
        self.enabled = True  # Bot starts enabled
        self.inet_monitor = inet_monitor  # Reference to monitor for checking pages
        self.status_provider = status_provider  # Function to get additional status info
        
        # Set up Discord bot with message content intent
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
        
        # Register event handlers
        self._register_events()
        self._register_commands()
    
    def _register_events(self):
        """Register bot event handlers"""
        
        @self.bot.event
        async def on_ready():
            print(f'✓ Discord bot logged in as {self.bot.user}')
            print(f'✓ Target channel ID: {self.channel_id}')
            print(f'✓ Bot is {"ENABLED" if self.enabled else "DISABLED"}')
    
    def _register_commands(self):
        """Register bot commands"""
        
        @self.bot.command(name='start')
        async def start_command(ctx):
            """Enable the bot to send product notifications"""
            if self.enabled:
                await ctx.send("✓ Bot is already **enabled** and sending notifications!")
            else:
                self.enabled = True
                await ctx.send("✅ Bot **enabled**! Will now send product notifications.")
                print("Bot enabled by user command")
        
        @self.bot.command(name='stop')
        async def stop_command(ctx):
            """Disable the bot from sending product notifications"""
            if not self.enabled:
                await ctx.send("✓ Bot is already **disabled**.")
            else:
                self.enabled = False
                await ctx.send("⏸️ Bot **disabled**. Product notifications paused.")
                print("Bot disabled by user command")
        
        @self.bot.command(name='status')
        async def status_command(ctx):
            """Check bot status and system information"""
            # Create an embed for better formatting
            embed = discord.Embed(
                title="🤖 Bot Status",
                color=discord.Color.green() if self.enabled else discord.Color.red()
            )
            
            # Bot notification status
            bot_status = "**ENABLED** ✅" if self.enabled else "**DISABLED** ⏸️"
            embed.add_field(name="Notifications", value=bot_status, inline=False)
            
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
            
            await ctx.send(embed=embed)
        
        @self.bot.command(name='help', aliases=['h', '?'])
        async def help_command(ctx):
            """Show help information"""
            help_text = """
**🤖 Inet Product Drop Bot**

I monitor Inet.se for new products and deals, and post them here automatically!

**Commands:**
• `!start` - Enable product notifications
• `!stop` - Disable product notifications
• `!status` - Check if bot is enabled/disabled
• `!links` - Show all campaign links being monitored
• `!resend` - Resend all tracked products
• `!clear [amount]` - Clear messages (default: 100)
• `!help` (or `!h`, `!?`) - Show this help message

**How it works:**
When enabled, I'll automatically post new products with:
✓ Product name (clickable link)
✓ Product image
✓ Pricing information
✓ Discount percentage (if applicable)

Stay tuned for great deals! 🎉
            """
            await ctx.send(help_text)
        
        @self.bot.command(name='links')
        async def links_command(ctx):
            """Show all campaign links being monitored"""
            if not self.inet_monitor:
                await ctx.send("❌ Monitor not connected.")
                return
            
            pages = self.inet_monitor.pages_to_check
            product_count = self.inet_monitor.get_product_count()
            
            if not pages:
                await ctx.send("📭 No campaign links are currently being monitored.\n\n*Links are added automatically when posted in the Inet Twitch chat!*")
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
            
            await ctx.send(links_text)
        
        @self.bot.command(name='clear')
        async def clear_command(ctx, amount: int = 100):
            """Clear messages in the current channel"""
            try:
                # Check if bot has permission to manage messages
                if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                    await ctx.send("❌ I don't have permission to delete messages! Please grant me 'Manage Messages' permission.")
                    return
                
                # Limit amount to prevent abuse
                if amount > 1000:
                    await ctx.send("⚠️ Can only clear up to 1000 messages at a time.")
                    amount = 1000
                
                # Delete messages
                deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
                
                # Send confirmation (will auto-delete after 5 seconds)
                confirmation = await ctx.send(f"✅ Cleared {len(deleted) - 1} message(s)!")
                await asyncio.sleep(5)
                await confirmation.delete()
                
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to delete messages!")
            except Exception as e:
                await ctx.send(f"❌ Error clearing messages: {e}")
        
        @self.bot.command(name='resend')
        async def resend_command(ctx):
            """Resend all currently tracked products"""
            if not self.inet_monitor:
                await ctx.send("❌ Monitor not connected.")
                return
            
            all_products = self.inet_monitor.get_all_products()
            
            if not all_products:
                await ctx.send("📭 No products tracked yet!\n\n*Products are tracked when campaign links are posted in Twitch chat.*")
                return
            
            # Ask for confirmation
            await ctx.send(f"📤 Resending **{len(all_products)}** product(s)...\n*This may take a while!*")
            
            # Send all products
            sent_count = 0
            for product_id, product in all_products.items():
                try:
                    embed = self._create_product_embed(product)
                    await ctx.channel.send(embed=embed)
                    sent_count += 1
                    
                    # Delay to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"   ❌ Error resending product {product_id}: {e}")
            
            await ctx.send(f"✅ Resent {sent_count} product(s)!")
    
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
        Send product notifications to Discord
        
        Args:
            products: Dictionary of products (product_id -> product_info)
        """
        if not self.enabled:
            print(f"⏸️  Bot is disabled. Skipping {len(products)} product(s).")
            return
        
        if not products:
            print("No products to send.")
            return
        
        # Get the target channel
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"❌ Could not find channel with ID {self.channel_id}")
            return
        
        print(f"📤 Sending {len(products)} product(s) to Discord...")
        
        for product_id, product in products.items():
            try:
                embed = self._create_product_embed(product)
                await channel.send(embed=embed)
                print(f"   ✓ Sent: {product.get('name', 'Unknown')}")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Error sending product {product_id}: {e}")
    
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
        return f"InetDiscordBot(channel_id={self.channel_id}, enabled={self.enabled})"


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