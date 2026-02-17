import os
import gspread
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CREDENTIALS_FILE = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')

print(f"DEBUG: Credentials File: {CREDENTIALS_FILE}")
print(f"DEBUG: Sheet ID: {SHEET_ID}")
print(f"DEBUG: Target Sheet Name: {SHEET_NAME}")

def debug_sheet():
    try:
        # Auth
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        if not os.path.exists(CREDENTIALS_FILE):
             print(f"ERROR: Credentials file not found at {CREDENTIALS_FILE}")
             return

        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open Spreadsheet
        print(f"Attempting to open spreadsheet with ID: {SHEET_ID}")
        sh = client.open_by_key(SHEET_ID)
        print(f"SUCCESS: Opened Spreadsheet '{sh.title}'")

        target_ws = None
        
        # Search by Name first
        if SHEET_NAME:
            try:
                target_ws = sh.worksheet(SHEET_NAME)
                print(f"SUCCESS: Found target worksheet '{SHEET_NAME}'")
            except:
                print(f"Warning: Worksheet '{SHEET_NAME}' not found by name.")
        
        # Search by ID if not found (Hardcoded check for user's ID)
        if not target_ws:
            print("Searching via ID 2137131181...")
            for ws in sh.worksheets():
                if str(ws.id) == "2137131181":
                    target_ws = ws
                    print(f"SUCCESS: Found worksheet by ID! Real Name: '{ws.title}'")
                    break
        
        if not target_ws:
             print("WARNING: Target sheet still not found, defaulting to first sheet.")
             target_ws = sh.sheet1
             
        if target_ws:
            print(f"Target Worksheet Title: '{target_ws.title}' (ID: {target_ws.id})")
            print(f"Row Count: {target_ws.row_count}")
            
            # Test Read (Last 5 rows)
            print("Reading last 5 populated rows...")
            all_values = target_ws.get_all_values()
            populated_values = [r for r in all_values if any(r)]
            print(f"Total populated rows: {len(populated_values)}")
            for row in populated_values[-5:]:
                print(row)
                
            # Test Write
            print("\n--- Attempting Test Write ---")
            result = target_ws.append_row(["DEBUG_TEST_ENV", "Test Month 2", "Connection OK"], value_input_option='USER_ENTERED')
            print(f"Write success. Result: {result}")
        
        
        # List Worksheets to File
        with open("sheets_list.txt", "w", encoding="utf-8") as f:
            f.write(f"Spreadsheet Title: {sh.title}\n")
            f.write(f"Spreadsheet ID: {sh.id}\n")
            f.write("-" * 30 + "\n")
            worksheets = sh.worksheets()
            for i, ws in enumerate(worksheets):
                line = f"Index {i}: '{ws.title}' (ID: {ws.id})\n"
                f.write(line)
                # print(line.strip()) # Console output truncated, rely on file
        
        print("Exported sheet list to sheets_list.txt")


    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sheet()
