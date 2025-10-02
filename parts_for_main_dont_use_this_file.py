import os
from dotenv import load_dotenv
from twitchio.ext import commands

# Load environment variables
load_dotenv()


import requests
from datetime import datetime, timedelta
import json

class TwitchTokenManager:
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
                # Update refresh token if a new one is provided
                if 'refresh' in data:
                    self.refresh_token = data.get('refresh')
                # Set expiration date to 59 days from now
                self.expiration_date = datetime.now() + timedelta(days=59)
                print(f"Token refreshed successfully. Expires on: {self.expiration_date}")
            else:
                raise Exception("Token refresh failed")
                
        except requests.RequestException as e:
            print(f"Error refreshing token: {e}")
            raise
    
    def get_token(self):
        """Get the current token, refreshing if expired"""
        if self.expiration_date is None or datetime.now() >= self.expiration_date:
            print("Token expired or not set, refreshing...")
            self._refresh_token()
        return self.token
    
    def __str__(self):
        """Return the token value when the instance is used as a string"""
        return self.get_token()
    
    def __repr__(self):
        return f"TwitchTokenManager(expires: {self.expiration_date})"

class Bot(commands.Bot):
    def __init__(self, token_manager):
        # TwitchIO 2.x uses token parameter for IRC authentication
        super().__init__(
            token=str(token_manager),
            prefix='!',
            initial_channels=[os.getenv('TWITCH_CHANNEL')]
        )
    
    async def event_ready(self):
        """Called once when the bot goes online"""
        print(f'✓ Logged in as | {self.nick}')
        print(f'✓ Monitoring chat in #{os.getenv("TWITCH_CHANNEL")}')
        print(f'✓ Bot is ready and waiting for messages...')

    async def event_message(self, message):
        """Called for every message in chat"""
        # Don't print our own messages
        if message.echo:
            return
        
        # Print every message with timestamp
        print(f'[{message.author.name}]: {message.content}')

# Create and start the bot
bot = Bot(token_manager)
await bot.start()


import requests
import os

# --- Configuration ---
# It's best practice to use environment variables for your credentials
# You can get these from the Twitch Developer Console: https://dev.twitch.tv/console
from dotenv import load_dotenv
load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID") 
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET") 

TARGET_CHANNEL = "inet" # The channel you want to check

# --- Step 1: Get an App Access Token ---
def get_app_access_token():
    """Gets an app access token from Twitch."""
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        response = requests.post("https://id.twitch.tv/oauth2/token", params=params)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        access_token = response.json()["access_token"]
        return access_token
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {e}")
        return None



def is_channel_live(access_token, channel_name):
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    params = {"user_login": channel_name}
    try:
        response = requests.get("https://api.twitch.tv/helix/streams", params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return bool(data.get("data"))
    except requests.exceptions.RequestException:
        return False

# --- Main Execution ---
if __name__ == "__main__":
    token = get_app_access_token()
    print(is_channel_live(token, TARGET_CHANNEL))