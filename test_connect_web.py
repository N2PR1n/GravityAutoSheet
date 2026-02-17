from web_app.utils import get_sheet_service
import pandas as pd

print("Testing Connection...")
try:
    # We can't use st.cache_resource here, but we can import the function.
    # Wait, st.cache_resource decorator might fail if run without streamlit.
    # We should copy the logic or import the undecorated function.
    # But streamlit decorators usually just pass through if not in streamlit context? 
    # Actually no, they might complain.
    # Let's just copy the logic to be safe and exact.
    
    import os
    import sys
    import gspread
    from google.oauth2 import service_account
    from dotenv import load_dotenv
    
    load_dotenv()
    
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    print(f"Creds: {creds_path}")
    print(f"Sheet ID: {sheet_id}")
    
    if not os.path.isabs(creds_path):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        creds_path = os.path.join(base_dir, creds_path)
    
    print(f"Abs Path: {creds_path}")
    
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1
    
    print("✅ Connection Successful!")
    data = sheet.get_all_records()
    print(f"✅ Can read data: {len(data)} rows found.")
    
except Exception as e:
    print(f"❌ Error: {e}")
