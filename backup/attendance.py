import os
import requests
import json
from datetime import datetime
import sys
import platform
import time

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL","https://office.encoderit.net/backend/public")  # Replace with your actual API base URL
EMAIL = os.getenv("EMAIL", "your-email@example.com")
PASSWORD = os.getenv("PASSWORD", "your-password")

# State file to track if we're on break
STATE_FILE = os.path.join(os.path.expanduser("~"), ".attendance_break_state")

def is_weekend():
    """Check if today is Saturday or Sunday"""
    return datetime.now().weekday() >= 5

def login():
    """Login and get bearer token"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        
        token = data.get("token") or data.get("access_token") or data.get("bearer_token")
        
        if not token:
            print("Error: Token not found in login response")
            print(f"Response: {data}")
            return None
            
        return token
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        return None

def start_break(token):
    """Start break"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/breaks/start",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
        )
        response.raise_for_status()
        print(f"✓ Break started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save state
        with open(STATE_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Break start failed: {e}")
        return False

def end_break(token):
    """End break"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/breaks/end",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        print(f"✓ Break ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Clear state
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Break end failed: {e}")
        return False

def is_on_break():
    """Check if currently on break"""
    return os.path.exists(STATE_FILE)

def main():
    # Check if it's weekend
    if is_weekend():
        print("Today is weekend. Skipping break tracking.")
        sys.exit(0)
    
    # Determine action based on command line argument
    action = sys.argv[1] if len(sys.argv) > 1 else None
    
    if action == "lock":
        # Screen locked - start break
        if is_on_break():
            print("Already on break, skipping...")
            sys.exit(0)
        
        token = login()
        if token:
            start_break(token)
    
    elif action == "unlock":
        # Screen unlocked - end break
        if not is_on_break():
            print("Not on break, skipping...")
            sys.exit(0)
        
        token = login()
        if token:
            end_break(token)
    
    else:
        print("Usage: python break_monitor.py [lock|unlock]")
        sys.exit(1)

if __name__ == "__main__":
    main()