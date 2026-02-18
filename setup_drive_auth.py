import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.auth_service import get_drive_service

def setup_auth():
    print("--- Setup Drive Authentication ---")
    print("This script will open a browser window to login to Google.")
    print("Please login with the account that owns the Drive Folder.")
    print("----------------------------------")
    
    try:
        service = get_drive_service()
        if service:
            print("\n✅ Authentication Successful!")
            print("Token saved to 'token.json'. You are good to go.")
    except Exception as e:
        print(f"\n❌ Authentication Failed: {e}")

if __name__ == "__main__":
    setup_auth()
