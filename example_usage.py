"""
Example usage of InetProductMonitor with InetDiscordBot

This demonstrates how to integrate the Inet scraper with Discord bot
to automatically post new products.
"""

import asyncio
from inet_scraper import InetProductMonitor
from discord_bot import InetDiscordBot
import os
from dotenv import load_dotenv

async def main():
    """Main function to run the monitor and bot together"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize Inet monitor
    monitor = InetProductMonitor(
        email=os.getenv('INET_EMAIL'),
        password=os.getenv('INET_PASSWORD'),
        pages=(
            'https://www.inet.se/kampanj/10114/racing-drops-251002',
            'https://www.inet.se/kampanj/25/inet-25-ar-jubileum',
            # Add more pages to monitor here
        )
    )
    
    # Initialize Discord bot
    bot = InetDiscordBot()
    
    # Start the Discord bot (non-blocking)
    asyncio.create_task(bot.start())
    
    # Wait for bot to be ready
    while not bot.is_ready():
        await asyncio.sleep(1)
    
    print("✓ Bot is ready!")
    print("✓ Starting monitoring loop...")
    
    # Main monitoring loop
    try:
        while True:
            print(f"\n🔍 Checking for new products... (Total tracked: {monitor.get_product_count()})")
            
            # Check for new products
            new_products = monitor.check_for_new_products()
            
            # Send to Discord if any new products found
            if new_products:
                await bot.send_products(new_products)
            
            # Wait before next check (e.g., 5 minutes)
            print(f"⏰ Waiting 5 minutes before next check...")
            await asyncio.sleep(300)  # 5 minutes
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
