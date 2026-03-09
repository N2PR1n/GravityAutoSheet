import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    """
    Exclusively uses User Authentication (token.json).
    Prioritizes /etc/secrets/token.json for Render.
    """
    creds = None
    
    # Paths to check for the user token
    paths_to_check = [
        os.getenv('GOOGLE_TOKEN_PATH', ''), # Manual override
        '/etc/secrets/token.json',         # Render Secret File
        'token.json'                       # Local fallback
    ]
    
    token_path = None
    for path in paths_to_check:
        if path and os.path.exists(path):
            token_path = path
            break
            
    if token_path:
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print(f"DEBUG: Successfully loaded User Account from {token_path}")
        except Exception as e:
            print(f"Warning: Failed to load token from {token_path}: {e}")
            creds = None

    # Handle Expiry or Missing Token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("DEBUG: Refreshed User Token successfully")
            except Exception as e:
                print(f"Failed to refresh user token: {e}")
                creds = None
        
        if not creds:
            # Look for client_secret.json in the same directory as token_path or root
            secret_dir = os.path.dirname(token_path) if (token_path and os.path.dirname(token_path)) else '.'
            client_secret_path = os.path.join(secret_dir, 'client_secret.json')
            
            if not os.path.exists(client_secret_path) and not os.path.exists('client_secret.json'):
                 # On Render, we can't do interactive auth
                 if os.environ.get('RENDER'):
                     raise Exception("❌ [AUTH ERROR] token.json is missing or expired on Render. Please update it in the Dashboard.")
                 else:
                     raise FileNotFoundError("❌ client_secret.json not found. Place it in the root to perform initial login.")

            # If local and missing token, trigger browser login
            print("INFO: Token missing or invalid. Starting browser authentication...")
            actual_secret = client_secret_path if os.path.exists(client_secret_path) else 'client_secret.json'
            flow = InstalledAppFlow.from_client_secrets_file(actual_secret, SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save the new token (if writable)
            try:
                save_path = token_path if token_path else 'token.json'
                with open(save_path, 'w') as token:
                    token.write(creds.to_json())
                print(f"INFO: Saved new token to {save_path}")
            except:
                print("WARNING: Could not save new token. Using only for this session.")

    return creds
