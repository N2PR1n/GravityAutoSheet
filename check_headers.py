import os
from dotenv import load_dotenv
from services.sheet_service import SheetService
import json

load_dotenv()

def check():
    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_source.startswith('{'):
        creds_source = json.loads(creds_source)
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    ss = SheetService(creds_source, sheet_id, sheet_name)
    headers = ss.sheet.row_values(1)
    print(f"Headers: {headers}")
    if len(headers) >= 14:
        print(f"Column 14 (N) Header: {headers[13]}")
    else:
        print("Sheet has fewer than 14 columns.")
        
    all_data = ss.get_all_data()
    if all_data:
        print(f"Sample Row 1: {all_data[0]}")

if __name__ == "__main__":
    check()
