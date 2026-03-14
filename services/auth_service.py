import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    """
    Robust credential loader. Prioritizes environment variables (JSON) 
    to ensure persistence on Render.
    """
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    
    # helper to clean up accidentally wrapped or escaped JSON
    def clean_json(raw):
        if not raw: return None
        raw = raw.strip()
        if not raw.startswith('{'): return None
        try:
            data = json.loads(raw)
            # handle wrapped debug JSON
            if isinstance(data, dict) and "GOOGLE_TOKEN_JSON_VALUE" in data:
                val = data["GOOGLE_TOKEN_JSON_VALUE"]
                if isinstance(val, str) and val.startswith('{'): return json.loads(val)
                if isinstance(val, dict): return val
            return data
        except: return None

    # 1. Try Service Account JSON (PERMANENT)
    sa_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_json:
        data = clean_json(sa_json)
        if data and data.get('type') == 'service_account':
            try:
                creds = service_account.Credentials.from_service_account_info(data, scopes=SCOPES)
                print("DEBUG: Loaded Service Account from Environment Variable")
                return creds
            except Exception as e:
                print(f"Warning: Failed to load SA from env: {e}")

    # 2. Try User Token JSON (RENEWABLE)
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if token_json:
        data = clean_json(token_json)
        if data:
            try:
                creds = Credentials.from_authorized_user_info(data, SCOPES)
                if creds.valid or (creds.expired and creds.refresh_token):
                    # verify/refresh
                    if not creds.valid:
                        creds.refresh(Request())
                    print("DEBUG: Loaded User Account from GOOGLE_TOKEN_JSON")
                    return creds
            except Exception as e:
                print(f"Warning: Failed to load User Token from env: {e}")

    # 3. Fallback to Local Files
    # User Token Files
    paths = [os.getenv('GOOGLE_TOKEN_PATH', ''), '/etc/secrets/token.json', 'token.json']
    for p in paths:
        if p and os.path.exists(p):
            try:
                creds = Credentials.from_authorized_user_file(p, SCOPES)
                if not creds.valid and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                print(f"DEBUG: Loaded User Account from file: {p}")
                return creds
            except: pass

    # Service Account File
    sa_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
    if os.path.exists(sa_path):
        try:
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
            print(f"DEBUG: Loaded Service Account from file: {sa_path}")
            return creds
        except: pass

    # 4. Final failure or interactive local flow
    if os.environ.get('RENDER'):
        raise Exception("❌ [AUTH ERROR] No valid credentials found in Render Environment. Please set GOOGLE_TOKEN_JSON or GOOGLE_SERVICE_ACCOUNT_JSON.")
    
    # Local Interactive
    client_secret_path = 'client_secret.json'
    if os.path.exists(client_secret_path):
        print("INFO: No credentials found. Starting local auth...")
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
        return creds
    
    raise FileNotFoundError("❌ [AUTH ERROR] No credentials or client_secret.json found.")

def get_auth_flow(redirect_uri, state=None):
    """
    Creates a Flow object for web-based OAuth.
    Prioritizes environment variables, then falls back to files.
    """
    # Priority 1: Full JSON from environment variable (Foolproof)
    oauth_json = os.getenv('GOOGLE_OAUTH_JSON', '').strip()
    if oauth_json and oauth_json.startswith('{'):
        try:
            from google_auth_oauthlib.flow import Flow
            client_config = json.loads(oauth_json)
            # Ensure the redirect_uri we're using is in the list of authorized ones
            if "web" in client_config and "redirect_uris" in client_config["web"]:
                if redirect_uri not in client_config["web"]["redirect_uris"]:
                    client_config["web"]["redirect_uris"].append(redirect_uri)
            
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                state=state
            )
            flow.redirect_uri = redirect_uri
            return flow
        except Exception as e:
            print(f"Warning: Failed to parse GOOGLE_OAUTH_JSON: {e}")

    # Priority 2: Manual environment variables
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    
    if client_id and client_secret:
        from google_auth_oauthlib.flow import Flow
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            state=state
        )
        flow.redirect_uri = redirect_uri
        return flow

    # Fallback to files
    client_secret_path = 'client_secret.json'
    if not os.path.exists(client_secret_path):
        client_secret_path = 'credentials.json'
    
    if os.path.exists(client_secret_path):
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            client_secret_path,
            scopes=SCOPES,
            state=state
        )
        flow.redirect_uri = redirect_uri
        return flow
    else:
        raise FileNotFoundError("❌ [AUTH ERROR] GOOGLE_CLIENT_ID/SECRET env vars OR client_secret.json not found.")

def save_token_from_response(url, state, redirect_uri, code_verifier=None):
    """
    Exchanges code for token and saves to token.json.
    Includes code_verifier for PKCE support.
    """
    flow = get_auth_flow(redirect_uri, state=state)
    flow.fetch_token(authorization_response=url, code_verifier=code_verifier)
    creds = flow.credentials
    
    # Save the token
    token_json_str = creds.to_json()
    token_path = 'token.json'
    with open(token_path, 'w') as token:
        token.write(token_json_str)
    
    print("--- GOOGLE_TOKEN_JSON START ---")
    print(token_json_str)
    print("--- GOOGLE_TOKEN_JSON END ---")
    return creds
