import streamlit as st
import os
import sys
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
import io
import requests.packages.urllib3.util.connection as urllib3_cn

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

from google.auth.transport.requests import AuthorizedSession

@st.cache_data(ttl=3600, show_spinner=False)
def download_image_from_drive(file_id):
    """Downloads image bytes from Drive using Requests (Avoids httplib2 hangs)."""
    if not file_id: return None
    
    config = load_config()
    creds_path = config["GOOGLE_APPLICATION_CREDENTIALS"]
    scope = ['https://www.googleapis.com/auth/drive.readonly']
    
    try:
        # Force IPv4 (Ensure patch is active before creating session)
        import socket
        def allowed_gai_family():
            family = socket.AF_INET
            return family
        urllib3_cn.allowed_gai_family = allowed_gai_family

        # Create Creds & Session
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
        authed_session = AuthorizedSession(creds)
        
        # Drive API Media Download URL
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        
        # Request (Timeout typically 5-10s)
        response = authed_session.get(url, timeout=10)
        
        # st.write(f"DEBUG: Drive API Status for {file_id}: {response.status_code}")
        
        if response.status_code == 200:
            return response.content
        else:
            # st.warning(f"Failed to fetch image {file_id}: Status {response.status_code}")
            return None
            
    except Exception as e:
        # st.error(f"Image Download Error: {e}")
        return None

# @st.cache_resource(ttl=600) <--- DISABLED CACHE TO FIX HANG
def connect_to_sheet():
    # st.write("DEBUG Utils: [START] Inside connect_to_sheet function")
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
    
    if not os.path.exists(creds_path):
        st.error(f"❌ Creds file not found at: {creds_path}")
        return None

    try:
        # Force IPv4 to prevent macOS IPv6 hangs
        import socket
        
        def allowed_gai_family():
            family = socket.AF_INET
            return family

        urllib3_cn.allowed_gai_family = allowed_gai_family
        
        # st.write("DEBUG: [1] IPv4 Forced. Initializing Credentials...")
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
        
        # st.write("DEBUG: [2] Authorizing Client...")
        client = gspread.authorize(creds)
        
        # st.write(f"DEBUG: [3] Opening Sheet ID: {sheet_id[:5]}...")
        sh = client.open_by_key(sheet_id)
        
        # st.write(f"DEBUG: [4] Selecting Worksheet...")
        sheet = sh.sheet1
        
        # st.write("DEBUG: [5] Connection Successful!")
        return sheet
    except Exception as e:
        # st.error(f"DEBUG: [ERROR] {e}")
        st.error(f"❌ Connection Failed: {e}")
        return None
