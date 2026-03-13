import os
import json
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    """
    Highly flexible authentication:
    1. First, try Service Account (Recommended for Server/Render).
    2. Fallback to User Authentication (token.json).
    """
    creds = None
    
    # --- PHASE 1: SERVICE ACCOUNT (Most Stable for Render) ---
    sa_paths = [
        os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
        '/etc/secrets/credentials.json',
        'credentials.json'
    ]
    
    for path in sa_paths:
        if path and os.path.exists(path):
            try:
                creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
                print(f"DEBUG: Successfully loaded Service Account from {path}")
                return creds
            except Exception as e:
                print(f"Warning: Failed to load Service Account from {path}: {e}")

    # --- PHASE 2: USER TOKEN (Fallback) ---
    token_paths = [
        os.getenv('GOOGLE_TOKEN_PATH', ''),
        '/etc/secrets/token.json',
        'token.json'
    ]
    
    token_path = None
    for path in token_paths:
        if path and os.path.exists(path):
            token_path = path
            break
            
    if token_path:
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print(f"DEBUG: Successfully loaded User Token from {token_path}")
        except Exception as e:
            print(f"Warning: Failed to load User Token from {token_path}: {e}")
            creds = None

    # Refresh User Token if needed
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("DEBUG: Refreshed User Token successfully")
            except Exception as e:
                print(f"Warning: Failed to refresh user token: {e}")
                creds = None

    if creds:
        return creds

    # --- PHASE 3: ERROR HANDLING (Render vs Local) ---
    if os.environ.get('RENDER'):
        raise Exception("❌ [AUTH ERROR] No valid Service Account or Token found on Render. Please update Secret Files.")
    
    # On local machine, if everything fails, we could trigger browser login (optional/manual)
    raise FileNotFoundError("❌ [AUTH ERROR] No credentials.json or token.json found. Please provide them to start.")
