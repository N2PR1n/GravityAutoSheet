import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    creds = None
    # Use environment variable if provided, otherwise default to local 'token.json'
    token_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'token.json')
    
    # Infer client_secret_path from token_path directory
    secret_dir = os.path.dirname(token_path) if os.path.dirname(token_path) else '.'
    client_secret_path = os.path.join(secret_dir, 'client_secret.json')
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh token: {e}")
                creds = None
                
        if not creds:
            if not os.path.exists(client_secret_path):
                raise FileNotFoundError(f"{client_secret_path} not found. Cannot perform OAuth 2.0 Auth.")
            
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return creds
