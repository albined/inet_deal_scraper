# Inet Product Monitor Bot - Docker Setup

This project can be run using Docker and Docker Compose.

## Prerequisites

- Docker installed
- Docker Compose installed
- `.env` file configured with your credentials

## Quick Start

### 1. Build and start the container:
```bash
docker-compose up -d
```

### 2. View logs:
```bash
docker-compose logs -f
```

### 3. Stop the container:
```bash
docker-compose down
```

## Docker Commands Cheatsheet

### Building and Running
```bash
# Build and start in detached mode
docker-compose up -d --build

# Start without rebuilding
docker-compose up -d

# View real-time logs
docker-compose logs -f inet-bot

# View last 100 lines of logs
docker-compose logs --tail=100 inet-bot
```

### Management
```bash
# Stop the container
docker-compose stop

# Start stopped container
docker-compose start

# Restart the container
docker-compose restart

# Stop and remove container
docker-compose down

# Stop, remove, and delete volumes
docker-compose down -v
```

### Debugging
```bash
# Execute commands inside the running container
docker-compose exec inet-bot /bin/bash

# View container resource usage
docker stats inet-product-monitor

# Inspect container
docker inspect inet-product-monitor
```

### Image Management
```bash
# Remove old/dangling images
docker image prune

# View images
docker images

# Remove specific image
docker rmi inet_drop_bot-inet-bot
```

## Configuration

### Environment Variables
All configuration is loaded from the `.env` file in the same directory.

Required variables:
- `TWITCH_CHANNEL`
- `TWITCH_REFRESH_TOKEN`
- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`
- `DISCORD_TOKEN_URL`
- `DISCORD_CHANNEL_ID`
- `INET_EMAIL`
- `INET_PASSWORD`

Optional variables:
- `TWITCH_ONLINE_CHECK_INTERVAL` (default: 300)
- `SCRAPE_INTERVAL` (default: 120)
- `LINK_TEMPLATE` (default: https://www.inet.se/kampanj/*)

### Resource Limits
The `docker-compose.yml` includes resource limits:
- CPU: 0.25-0.5 cores
- Memory: 256-512 MB

Adjust these in `docker-compose.yml` if needed.

## Troubleshooting

### Container keeps restarting
```bash
# Check logs for errors
docker-compose logs inet-bot

# Check if .env file is present and valid
cat .env
```

### Out of memory
Increase memory limits in `docker-compose.yml`:
```yaml
limits:
  memory: 1G
```

### Need to rebuild after code changes
```bash
docker-compose up -d --build
```

## Image Size Optimization

The Dockerfile uses a multi-stage build to minimize the final image size:
- **Builder stage**: Installs build dependencies and compiles packages
- **Runtime stage**: Only includes runtime dependencies and application code
- **Non-root user**: Runs as `botuser` for security
- **Slim base image**: Uses `python:3.11-slim` instead of full Python image

Expected final image size: ~150-200 MB (vs 900+ MB for standard Python image)
