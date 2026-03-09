import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    creds = None
    token_path = None

    # Priority 1: Check for User Auth Token (token.json) in common paths
    paths_to_check = [
        'token.json',
        '/etc/secrets/token.json',
        os.getenv('GOOGLE_TOKEN_PATH', '')
    ]
    
    for path in paths_to_check:
        if path and os.path.exists(path):
            try:
                import json
                with open(path, 'r') as f:
                    data = json.load(f)
                
                # Check if it is a User Token (Authorized User)
                if 'refresh_token' in data or 'token' in data:
                    print(f"DEBUG: Found User Token at {path}")
                    creds = Credentials.from_authorized_user_file(path, SCOPES)
                    token_path = path
                    break
            except Exception as e:
                print(f"Warning: Failed to load user token at {path}: {e}")

    # Priority 2: Fallback to Service Account if no valid user token found
    if not creds:
        creds_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
        
        # Check if it's a JSON string instead of a path
        clean_creds = creds_env.strip()
        if clean_creds.startswith('{') and clean_creds.endswith('}'):
            try:
                import json
                from google.oauth2 import service_account
                creds_data = json.loads(clean_creds)
                if creds_data.get('type') == 'service_account':
                    print("DEBUG: Using Service Account from environment JSON")
                    return service_account.Credentials.from_service_account_info(creds_data, scopes=SCOPES)
            except Exception as e:
                print(f"Error parsing GOOGLE_APPLICATION_CREDENTIALS as JSON: {e}")
        
        token_path = creds_env if creds_env else 'credentials.json'
        
    if not token_path:
        token_path = 'token.json' # Final fallback path for saving update tokens

    # Infer client_secret_path from token_path directory
    secret_dir = os.path.dirname(token_path) if os.path.dirname(token_path) else '.'
    client_secret_path = os.path.join(secret_dir, 'client_secret.json')
    
    if os.path.exists(token_path):
        import json
        try:
            with open(token_path, 'r') as f:
                creds_data = json.load(f)
            
            if creds_data.get('type') == 'service_account':
                from google.oauth2 import service_account
                return service_account.Credentials.from_service_account_file(token_path, scopes=SCOPES)
            else:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"Warning: Failed to load {token_path}: {e}")
            creds = None
        
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
            
            # Detect headless environment (Render) to avoid hanging workers
            if os.environ.get('RENDER'):
                raise Exception(
                    f"OAuth Token is expired or missing at {token_path}! "
                    "Cannot run browser auth on a headless Render server. "
                    "Please run the bot locally to generate a fresh token.json, then replace it on Render."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        try:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print("INFO: Saved updated token.")
        except IOError:
            print("WARNING: Could not save token (file system might be read-only, e.g. /etc/secrets on Render). Authentication will still proceed for this session.")
            
    return creds
