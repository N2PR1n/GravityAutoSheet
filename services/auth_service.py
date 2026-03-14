import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_credentials():
    """
    User OAuth Token loader. ใช้ Account ส่วนตัวของผู้ใช้เท่านั้น
    (ไม่ใช้ Service Account เพราะไม่มี Drive storage)
    """
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

    # 1. Try User Token JSON from Environment (for Render)
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if token_json:
        print(f"DEBUG AUTH: GOOGLE_TOKEN_JSON found (length={len(token_json)})")
        data = clean_json(token_json)
        if data:
            # Check if it's accidentally a service account
            if data.get('type') == 'service_account':
                print("⚠️ AUTH WARNING: GOOGLE_TOKEN_JSON contains a Service Account JSON!")
                print("   Please replace with the content from token.json")
            else:
                try:
                    creds = Credentials.from_authorized_user_info(data, SCOPES)
                    print(f"DEBUG AUTH: Token created. valid={creds.valid}, expired={creds.expired}, has_refresh={bool(creds.refresh_token)}")
                    # Always try to refresh if not valid
                    if not creds.valid and creds.refresh_token:
                        print("DEBUG AUTH: Refreshing token...")
                        creds.refresh(Request())
                    if creds.valid:
                        print("DEBUG AUTH: ✅ Loaded User Account from GOOGLE_TOKEN_JSON")
                        return creds
                    else:
                        print("DEBUG AUTH: ❌ Token still not valid after refresh attempt")
                except Exception as e:
                    print(f"Warning: Failed to load User Token from env: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("DEBUG AUTH: GOOGLE_TOKEN_JSON could not be parsed as JSON")
    else:
        print("DEBUG AUTH: GOOGLE_TOKEN_JSON env var not found")

    # 2. Fallback to Local Token Files
    paths = [os.getenv('GOOGLE_TOKEN_PATH', ''), '/etc/secrets/token.json', 'token.json']
    for p in paths:
        if p and os.path.exists(p):
            print(f"DEBUG AUTH: Trying token file: {p}")
            try:
                creds = Credentials.from_authorized_user_file(p, SCOPES)
                if not creds.valid and creds.refresh_token:
                    creds.refresh(Request())
                if creds.valid:
                    print(f"DEBUG AUTH: ✅ Loaded User Account from file: {p}")
                    return creds
                else:
                    print(f"DEBUG AUTH: Token from {p} is not valid")
            except Exception as e:
                print(f"DEBUG AUTH: Failed to load from {p}: {e}")
                import traceback
                traceback.print_exc()

    # 3. Final failure or interactive local flow
    if os.environ.get('RENDER'):
        raise Exception("❌ [AUTH ERROR] No valid credentials found. Please set GOOGLE_TOKEN_JSON environment variable.")
    
    # Local Interactive OAuth
    client_secret_path = 'client_secret.json'
    if os.path.exists(client_secret_path):
        print("INFO: No credentials found. Starting local auth...")
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
        return creds
    
    raise FileNotFoundError("❌ [AUTH ERROR] No token.json or client_secret.json found.")

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
