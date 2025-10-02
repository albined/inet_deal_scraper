# Inet Product Monitor Bot

Autonomous bot that monitors Inet.se Twitch channel for campaign links, scrapes products, and posts them to Discord.

## Features

- 🔴 Detects when Inet Twitch channel goes live
- 💬 Monitors chat for campaign links (`https://www.inet.se/kampanj/*`)
- 🔍 Automatically scrapes product information
- 📤 Posts new products to Discord with rich embeds
- ⏰ Periodic scraping + immediate scraping on new links
- 🎮 Discord commands for control and status

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
| `!status` | Show bot status, Twitch stream, and tracking info |
| `!links` | List all monitored campaign pages |
| `!start` | Enable product notifications |
| `!stop` | Disable product notifications |
| `!resend` | Resend all tracked products |
| `!clear [n]` | Clear last n messages (default: 100) |
| `!help` | Show help message |

## Configuration

Edit `.env`:

```bash
# Twitch
TWITCH_CHANNEL=inet
TWITCH_REFRESH_TOKEN=your_token
TWITCH_CLIENT_ID=your_id
TWITCH_CLIENT_SECRET=your_secret

# Discord
DISCORD_TOKEN_URL=your_bot_token
DISCORD_CHANNEL_ID=your_channel_id

# Inet
INET_EMAIL=your_email
INET_PASSWORD=your_password

# Intervals (seconds)
TWITCH_ONLINE_CHECK_INTERVAL=300
SCRAPE_INTERVAL=120
```

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

1. Monitors Twitch API to detect when Inet goes live
2. Connects to Twitch chat when stream starts
3. Extracts campaign links from chat messages
4. Scrapes products from those campaigns
5. Posts new products to Discord
6. Continues periodic scraping while live
7. Disconnects when stream ends

## License

MIT
