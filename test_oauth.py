import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import gspread

def test_oauth():
    token_path = 'token.json'
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets'])
        if creds.expired and creds.refresh_token:
            print("Refreshing token...")
            creds.refresh(Request())
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        print(f"Token Scopes: {creds.scopes}")
        
        try:
            drive_service = build('drive', 'v3', credentials=creds)
            print("Drive Service Authenticated.")
            
            client = gspread.authorize(creds)
            print("Gspread Authenticated.")
            
            # test drive
            results = drive_service.files().list(pageSize=1).execute()
            print(f"Drive works, found {len(results.get('files', []))} files.")
            
            # test sheets
            sheet_id = os.getenv("GOOGLE_SHEET_ID", "16T1rQfmBwdT5_AZf8uaL7Ws6ReW-RuIPgx0nTYbKFe4")
            sh = client.open_by_key(sheet_id)
            print(f"Sheets works, opened '{sh.title}'")
            
        except Exception as e:
            print(f"Test Failed: {e}")
    else:
        print("token.json not found.")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    test_oauth()
