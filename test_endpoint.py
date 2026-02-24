import requests

urls = [
    "https://gravity-check-box.onrender.com/bot/callback",
    "https://gravity-check-box.onrender.com/callback",
]

for url in urls:
    print(f"Testing POST to {url}...")
    try:
        r = requests.post(url, timeout=10)
        print(f"Status: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
