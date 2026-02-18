import requests

url = "https://drive.google.com/uc?export=view&id=1CwSMbblTyDLxWdz5YfGygOs8V3evvwHs"
print(f"Testing URL: {url}")
try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Image is public.")
    else:
        print("Failed! Image is private or blocking requests.")
except Exception as e:
    print(f"Error: {e}")
