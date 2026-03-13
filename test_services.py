
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("--- Diagnostics ---")
print(f"GOOGLE_SHEET_ID: {os.getenv('GOOGLE_SHEET_ID')}")
print(f"GOOGLE_SHEET_NAME: {os.getenv('GOOGLE_SHEET_NAME')}")
print(f"RENDER ENV: {os.getenv('RENDER')}")

# Try to import and run get_google_credentials
try:
    from services.auth_service import get_google_credentials
    creds = get_google_credentials()
    if creds:
        print("✅ Google Credentials loaded successfully")
        print(f"   Valid: {creds.valid}")
        print(f"   Expired: {creds.expired}")
    else:
        print("❌ Google Credentials returned None")
except Exception as e:
    print(f"❌ Error loading credentials: {e}")

try:
    from services.sheet_service import SheetService
    from services.auth_service import get_google_credentials
    creds = get_google_credentials()
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    if creds and sheet_id:
        ss = SheetService(creds, sheet_id, sheet_name)
        if ss.sheet:
            print(f"✅ SheetService initialized. Active sheet: {ss.sheet.title}")
            worksheets = ss.get_worksheets()
            print(f"✅ Found {len(worksheets)} visible worksheets: {worksheets}")
        else:
            print("❌ SheetService initialized but sheet is None")
    else:
        print("❌ Missing creds or sheet_id for SheetService test")
except Exception as e:
    print(f"❌ Error in SheetService test: {e}")
