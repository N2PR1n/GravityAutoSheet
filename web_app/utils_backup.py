import streamlit as st
import os
import sys
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path to import services if needed (optional)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_config():
    """Loads environment variables."""
    return {
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "GOOGLE_SHEET_ID": os.getenv("GOOGLE_SHEET_ID"),
    }

# @st.cache_resource(ttl=600)
def get_sheet_service():
    print("DEBUG: [1] Starting get_sheet_service...")
    """Connects to Google Sheet using Service Account."""
    # Reload dotenv inside to be sure - REMOVED to avoid I/O blocking
    # load_dotenv()
    
    print("DEBUG: [2] Loading config...")
    config = load_config()
    creds_path = config["GOOGLE_APPLICATION_CREDENTIALS"]
    sheet_id = config["GOOGLE_SHEET_ID"]
    print(f"DEBUG: [3] Config Loaded. Path: {creds_path}, ID: {sheet_id}")
    
    if not creds_path or not sheet_id:
        st.error("❌ Missing Configuration: Check .env or Secrets.")
        return None

    # Resolve Path if relative
    print("DEBUG: [4] Resolving Path...")
    if not os.path.isabs(creds_path):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        creds_path = os.path.join(base_dir, creds_path)
    print(f"DEBUG: [5] Absolute Path: {creds_path}")

    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    if os.path.exists(creds_path):
        print("DEBUG: [6] File EXISTS.")
    else:
        print("DEBUG: [6] File NOT FOUND.")

    try:
        print("DEBUG: [7] Creating Credentials object...")
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
        print("DEBUG: 2. Authorizing Client...")
        client = gspread.authorize(creds)
        print(f"DEBUG: 3. Opening Sheet (ID: {sheet_id[:5]}...)...")
        sheet = client.open_by_key(sheet_id).sheet1
        print("DEBUG: 4. Sheet connected successfully!")
        return sheet
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return None
