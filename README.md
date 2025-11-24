# Inet Product Monitor Bot

Autonomous bot that monitors Inet.se Twitch and YouTube channels for campaign links, scrapes products, and posts them to Discord.

## Features

- 🔴 **Dual Platform Monitoring**: Monitors both Twitch AND YouTube for redundancy
- 💬 Monitors chat on both platforms for campaign links (`https://www.inet.se/kampanj/*`)
- 🎥 YouTube: Detects live streams every 10 minutes and monitors chat with adaptive intervals
- 🔄 Automatic daily reset of tracked links after midnight
- 🔍 Automatically scrapes product information
- 📤 Posts new products to Discord with rich embeds
- 📢 Subscription system - multiple channels/DMs can subscribe
- 💾 Persistent subscriptions across restarts (JSON storage)
- ⏰ Periodic scraping + immediate scraping on new links
- 🎮 Discord slash commands for control and status

## Quick Start

### Prerequisites
- Python 3.11+ or Docker
- Discord bot token
- Twitch API credentials
- Inet.se account

### Setup
1. Clone and configure:
```bash
git clone <repo-url>
cd inet_drop_bot
cp .env.example .env  # Edit with your credentials
```

2. Run with Docker (recommended):
```bash
docker-compose up -d
docker-compose logs -f
```

Or run locally:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Discord Commands

| Command | Description |
|---------|-------------|
| `/subscribe` | Subscribe current channel/DM to notifications |
| `/unsubscribe` | Unsubscribe current channel/DM from notifications |
| `/status` | Show subscription status, Twitch stream, and tracking info |
| `/links` | List all monitored campaign pages |
| `/addlink <link>` | Manually add a YouTube stream link to monitor (e.g., `/addlink https://www.youtube.com/watch?v=VIDEO_ID`) |
| `/resend` | Resend all tracked products to current channel |
| `/clear [n]` | Clear last n messages (default: 100) |
| `/help` | Show help message |

**Note:** Subscriptions are persistent across bot restarts and stored in `subscribers.json`

## Configuration

Edit `.env`:

```bash
# Twitch
TWITCH_CHANNEL=inet
TWITCH_REFRESH_TOKEN=your_token
TWITCH_CLIENT_ID=your_id
TWITCH_CLIENT_SECRET=your_secret

# YouTube
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@inet
YOUTUBE_STREAM_CHECK_INTERVAL=600
YOUTUBE_CHAT_CHECK_INTERVAL=5
YOUTUBE_INACTIVE_CHAT_INTERVAL=600
YOUTUBE_INACTIVE_THRESHOLD=300

# Discord
DISCORD_TOKEN_URL=your_bot_token

# Inet
INET_EMAIL=your_email
INET_PASSWORD=your_password

# Intervals (seconds)
TWITCH_ONLINE_CHECK_INTERVAL=300
SCRAPE_INTERVAL=120
```

### YouTube Configuration Details

- `YOUTUBE_STREAM_CHECK_INTERVAL`: How often to check if the channel is live (default: 600s = 10 minutes)
- `YOUTUBE_CHAT_CHECK_INTERVAL`: How often to check chat when active (default: 5s)
- `YOUTUBE_INACTIVE_CHAT_INTERVAL`: How often to check chat when inactive (default: 600s = 10 minutes)
- `YOUTUBE_INACTIVE_THRESHOLD`: Time without messages before considering chat inactive (default: 300s = 5 minutes)

## Docker

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Stop
docker-compose down
```

## How It Works

### Twitch Monitoring
1. Monitors Twitch API to detect when Inet goes live
2. Connects to Twitch chat when stream starts
3. Extracts campaign links from chat messages
4. Scrapes products from those campaigns
5. Disconnects when stream ends

### YouTube Monitoring (Runs in Parallel)
1. Checks every 10 minutes if the YouTube channel is live
2. When a live stream is detected, starts monitoring the chat
3. Monitors chat every 5 seconds when active
4. Switches to checking every 10 minutes if no messages for 5 minutes
5. Handles invalid video IDs gracefully by removing them from monitoring
6. Resets tracked links daily after midnight

### Common Flow
1. Both platforms extract campaign links matching the pattern
2. New links trigger immediate product scraping
3. New products are posted to all subscribed Discord channels/DMs
4. Continues periodic scraping while monitoring
5. Subscriptions persist in `subscribers.json` for future restarts

## License

MIT
