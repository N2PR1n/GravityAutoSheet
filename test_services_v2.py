import os
import sys
from dotenv import load_dotenv

# Add parent dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.sheet_service import SheetService
from services.drive_service import DriveService

load_dotenv()

def test_services():
    print("--- Testing Services V2 ---")
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    print(f"Creds Path: {creds_path}")
    print(f"Sheet ID: {sheet_id}")
    
    # 1. Test Sheet
    print("\n[1] Testing SheetService...")
    try:
        sheet_service = SheetService(creds_path, sheet_id, sheet_name)
        if sheet_service.sheet:
            print(f"✅ Sheet Connected: {sheet_service.sheet.title}")
            data = sheet_service.get_all_data()
            print(f"✅ Data Fetched: {len(data)} rows")
        else:
            print("❌ Sheet Connection Failed")
    except Exception as e:
        print(f"❌ Sheet Error: {e}")

    # 2. Test Drive
    print("\n[2] Testing DriveService...")
    try:
        # DriveService now uses User OAuth (ignores creds_path args)
        drive_service = DriveService()
        if drive_service.service:
            print("✅ Drive Service Init Success (User OAuth)")
            
            # Create dummy file
            with open("test_upload.txt", "w") as f:
                f.write("Test Upload V2 (OAuth)")
                
            folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            print(f"Uploading to Folder: {folder_id}")
            
            file = drive_service.upload_file("test_upload.txt", folder_id)
            if file:
                print(f"✅ Upload Success! File ID: {file.get('id')}")
                print(f"Link: {file.get('webViewLink')}")
            else:
                print("❌ Upload Failed")
            
            # Cleanup
            if os.path.exists("test_upload.txt"):
                os.remove("test_upload.txt")
        else:
            print("❌ Drive Service Init Failed")
    except Exception as e:
        print(f"❌ Drive Error: {e}")

if __name__ == "__main__":
    test_services()
