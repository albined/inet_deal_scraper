"""
Persistent subscriber storage for Discord bot

Manages subscriber information with JSON-based persistence.
Stores channel IDs and user DM IDs that should receive notifications.
"""

import json
import os
from typing import Set
from pathlib import Path


class SubscriberDatabase:
    """
    Manages subscriber persistence using JSON file storage
    
    Stores subscriber IDs (can be channel IDs or user DM IDs)
    and persists them across bot restarts.
    """
    
    def __init__(self, db_path: str = "data/subscribers.json"):
        """
        Initialize the subscriber database
        
        Args:
            db_path: Path to the JSON file for storing subscribers
        """
        # Ensure the data directory exists
        data_dir = os.path.dirname(db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        
        self.db_path = db_path
        self.subscribers: Set[int] = set()
        self._load()
    
    def _load(self):
        """Load subscribers from the JSON file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.subscribers = set(data.get('subscribers', []))
                print(f"✓ Loaded {len(self.subscribers)} subscriber(s) from {self.db_path}")
            except Exception as e:
                print(f"❌ Error loading subscribers: {e}")
                self.subscribers = set()
        else:
            print(f"⚠️  No existing subscriber database found. Creating new one at {self.db_path}")
            self.subscribers = set()
            self._save()
    
    def _save(self):
        """Save subscribers to the JSON file"""
        try:
            data = {
                'subscribers': list(self.subscribers)
            }
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Saved {len(self.subscribers)} subscriber(s) to {self.db_path}")
        except Exception as e:
            print(f"❌ Error saving subscribers: {e}")
    
    def add_subscriber(self, subscriber_id: int) -> bool:
        """
        Add a subscriber
        
        Args:
            subscriber_id: Discord channel ID or user DM ID
            
        Returns:
            True if subscriber was added, False if already existed
        """
        if subscriber_id in self.subscribers:
            return False
        
        self.subscribers.add(subscriber_id)
        self._save()
        return True
    
    def remove_subscriber(self, subscriber_id: int) -> bool:
        """
        Remove a subscriber
        
        Args:
            subscriber_id: Discord channel ID or user DM ID
            
        Returns:
            True if subscriber was removed, False if didn't exist
        """
        if subscriber_id not in self.subscribers:
            return False
        
        self.subscribers.remove(subscriber_id)
        self._save()
        return True
    
    def is_subscribed(self, subscriber_id: int) -> bool:
        """
        Check if a channel/user is subscribed
        
        Args:
            subscriber_id: Discord channel ID or user DM ID
            
        Returns:
            True if subscribed, False otherwise
        """
        return subscriber_id in self.subscribers
    
    def get_all_subscribers(self) -> Set[int]:
        """
        Get all subscriber IDs
        
        Returns:
            Set of all subscriber IDs
        """
        return self.subscribers.copy()
    
    def get_count(self) -> int:
        """
        Get the number of subscribers
        
        Returns:
            Number of subscribers
        """
        return len(self.subscribers)
    
    def clear_all(self):
        """Clear all subscribers (use with caution!)"""
        self.subscribers.clear()
        self._save()
    
    def __repr__(self):
        return f"SubscriberDatabase(subscribers={len(self.subscribers)}, path='{self.db_path}')"


# Example usage
if __name__ == "__main__":
    # Create a test database
    db = SubscriberDatabase("test_subscribers.json")
    
    # Add some test subscribers
    db.add_subscriber(123456789)
    db.add_subscriber(987654321)
    
    print(f"Total subscribers: {db.get_count()}")
    print(f"Is 123456789 subscribed? {db.is_subscribed(123456789)}")
    print(f"Is 111111111 subscribed? {db.is_subscribed(111111111)}")
    
    # Remove a subscriber
    db.remove_subscriber(123456789)
    print(f"After removal: {db.get_count()} subscribers")
