import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

with open('token.json', 'r') as f:
    creds_data = json.load(f)

creds = Credentials.from_authorized_user_info(creds_data)

print(f"Valid: {creds.valid}")
print(f"Expired: {creds.expired}")

if creds.expired:
    print("Attempting to refresh...")
    try:
        creds.refresh(Request())
        print(f"Refresh success, new expiry: {creds.expiry}")
    except Exception as e:
        print(f"Refresh failed: {e}")
