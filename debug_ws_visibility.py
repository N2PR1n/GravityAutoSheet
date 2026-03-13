
import os
from services.auth_service import get_google_credentials
from services.sheet_service import SheetService
from dotenv import load_dotenv

load_dotenv()

def debug_worksheets():
    creds = get_google_credentials()
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    
    if not creds or not sheet_id:
        print("Missing credentials or Sheet ID")
        return

    try:
        import gspread
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        
        print(f"Spreadsheet: {spreadsheet.title}")
        worksheets = spreadsheet.worksheets()
        print(f"Total worksheets found: {len(worksheets)}")
        
        for ws in worksheets:
            # Check properties
            is_hidden = getattr(ws, 'hidden', 'N/A')
            print(f"- Sheet: '{ws.title}', Hidden: {is_hidden}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_worksheets()
