import os
import json
from dotenv import load_dotenv
load_dotenv()

from services.sheet_service import SheetService

def global_find():
    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    order_target = "26021800980PJAUN"
    
    if creds_source and creds_source.strip().startswith('{'):
        creds_source = json.loads(creds_source)
        
    print(f"Global Find for: {order_target}")
    ss = SheetService(creds_source, sheet_id)
    
    # Use gspread find
    spreadsheet = ss.client.open_by_key(sheet_id)
    worksheets = spreadsheet.worksheets()
    
    for ws in worksheets:
        print(f"Searching worksheet: {ws.title}")
        try:
            cell = ws.find(order_target)
            if cell:
                print(f"FOUND in '{ws.title}' at cell {cell.address}")
        except Exception:
            pass

if __name__ == "__main__":
    global_find()
