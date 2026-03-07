import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from services.drive_service import DriveService

def check_folder():
    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    ds = DriveService(creds_source)
    
    folder_id = "1KdLuDJIyHiyDy6-M-dzU2LyLLOES4x4l"
    print(f"Checking Folder ID: {folder_id}...")
    
    try:
        file = ds.service.files().get(fileId=folder_id, fields="id, name, mimeType, owners, shared, permissions").execute()
        print(json.dumps(file, indent=2))
        
        print("\n--- Testing Upload ---")
        with open("test.txt", "w") as f:
            f.write("Hello World")
            
        uploaded = ds.upload_file("test.txt", folder_id, "test_upload_service_account.txt")
        if uploaded:
            print("Upload successful!")
        else:
            print("Upload returned None.")
        os.remove("test.txt")
        
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    check_folder()
