import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import socket
import requests.packages.urllib3.util.connection as urllib3_cn

# Force IPv4
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Shows basic usage of the Drive v3 API."""
    creds = None
    
    # Resolve paths relative to project root
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
    token_path = os.path.join(base_dir, 'token.json')
    client_secret_path = os.path.join(base_dir, 'client_secret.json')
    
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"Error loading token.json: {e}")
            creds = None

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(client_secret_path):
                raise FileNotFoundError(f"Missing {client_secret_path}. Please download it from Google Cloud Console.")

            print("Initiating new login flow...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            print(f"Token saved to {token_path}")

    return build('drive', 'v3', credentials=creds)
