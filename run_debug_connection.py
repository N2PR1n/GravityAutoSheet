import os
import sys
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv
import time

# Load env
load_dotenv()

def test_connection():
    print("--- STARTING DEBUG SCRIPT ---")
    
    # 1. Check Config
    print("[1] Checking Configuration...")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    print(f"    - Creds Path: {creds_path}")
    print(f"    - Sheet ID: {sheet_id}")
    
    if not creds_path or not sheet_id:
        print("❌ MISSING CONFIG")
        return

    if not os.path.exists(creds_path):
        # Try absolute path resolution similar to app
        base_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(base_dir, creds_path)
        print(f"    - Resolved Path: {creds_path}")
        
    if os.path.exists(creds_path):
        print("    ✅ File Exists")
    else:
        print("    ❌ File NOT Found")
        return

    # 2. Auth
    print("\n[2] Authenticating with Google...")
    start_time = time.time()
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)
        print(f"    ✅ Authenticated in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"    ❌ Auth Failed: {e}")
        return

    # 3. Open Sheet
    print("\n[3] Opening Spreadsheet by ID...")
    start_time = time.time()
    try:
        sh = client.open_by_key(sheet_id)
        print(f"    ✅ Spreadsheet Opened: '{sh.title}' in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"    ❌ Open Spreadsheet Failed: {e}")
        return

    # 4. Get Data
    print("\n[4] Fetching Data from Sheet1...")
    start_time = time.time()
    try:
        sheet = sh.sheet1
        data = sheet.get_all_records()
        print(f"    ✅ Fetched {len(data)} records in {time.time() - start_time:.2f} seconds")
        print(f"    - First Record: {data[0] if data else 'Empty'}")
    except Exception as e:
        print(f"    ❌ Fetch Data Failed: {e}")
        return

    print("\n--- DEBUG SUCCESSFUL ---")

if __name__ == "__main__":
    test_connection()
