import os
import requests
from dotenv import load_dotenv
load_dotenv()

def check_webhook():
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    
    print("Checking LINE webhook endpoint...")
    r = requests.get("https://api.line.me/v2/bot/channel/webhook/endpoint", headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")

if __name__ == "__main__":
    check_webhook()
