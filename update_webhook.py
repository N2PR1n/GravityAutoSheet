import os
import requests
from dotenv import load_dotenv
load_dotenv()

def update_webhook():
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # CORRECT URL
    new_endpoint = "https://gravity-check-box.onrender.com/callback"
    
    print(f"Updating LINE webhook endpoint to: {new_endpoint}")
    data = {"endpoint": new_endpoint}
    
    r = requests.put("https://api.line.me/v2/bot/channel/webhook/endpoint", headers=headers, json=data)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
    # Also verify it
    print("\nVerifying...")
    v = requests.post("https://api.line.me/v2/bot/channel/webhook/test", headers=headers, json=data)
    print(f"Test Status: {v.status_code}")
    print(f"Test Response: {v.text}")

if __name__ == "__main__":
    update_webhook()
