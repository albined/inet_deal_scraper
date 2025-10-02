# Multi-stage build for smaller final image
# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Create minimal runtime image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/botuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/botuser/.local/bin:$PATH

# Copy application code
COPY --chown=botuser:botuser inet_scraper.py .
COPY --chown=botuser:botuser discord_bot.py .
COPY --chown=botuser:botuser main.py .

# Switch to non-root user
USER botuser

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Health check (optional - checks if process is running)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -q "[p]ython.*main.py" || exit 1

# Run the bot
CMD ["python", "main.py"]
