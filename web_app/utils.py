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

@st.cache_resource
def get_sheet_service():
    """Connects to Google Sheet using Service Account."""
    config = load_config()
    creds_path = config["GOOGLE_APPLICATION_CREDENTIALS"]
    sheet_id = config["GOOGLE_SHEET_ID"]
    
    if not creds_path or not sheet_id:
        st.error("❌ Missing Configuration: Check .env or Secrets.")
        return None

    # Resolve Path if relative
    if not os.path.isabs(creds_path):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        creds_path = os.path.join(base_dir, creds_path)

    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    try:
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return None
