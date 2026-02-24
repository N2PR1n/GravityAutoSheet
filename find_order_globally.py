import os
import json
from dotenv import load_dotenv
load_dotenv()

from services.sheet_service import SheetService

def diagnostic():
    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    order_target = "26021800980PJAUN"
    
    if creds_source and creds_source.strip().startswith('{'):
        creds_source = json.loads(creds_source)
        
    print(f"Searching for Order ID: {order_target}")
    ss = SheetService(creds_source, sheet_id)
    
    sheets = ss.get_worksheets()
    print(f"Sheets found: {sheets}")
    
    for s_name in sheets:
        print(f"Checking sheet: {s_name}...")
        ss.set_worksheet(s_name)
        # We look specifically in Column L (12)
        try:
            order_ids = ss.sheet.col_values(12)
            if order_target in order_ids:
                row_idx = order_ids.index(order_target) + 1
                print(f"MATCH FOUND in '{s_name}' at row {row_idx}!")
        except Exception as e:
            print(f"Error checking {s_name}: {e}")

if __name__ == "__main__":
    diagnostic()
