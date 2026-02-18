from services.drive_service import DriveService
import os
from dotenv import load_dotenv

load_dotenv()

# User provided folder ID
FOLDER_ID = "1KdLuDJIyHiyDy6-M-dzU2LyLLOES4x4l"

def list_folder():
    service = DriveService(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
    if not service.service:
        print("Service init failed")
        return

    print(f"Listing files in folder: {FOLDER_ID}")
    
    # List files in this folder
    query = f"'{FOLDER_ID}' in parents and trashed = false"
    token = None
    
    results = service.service.files().list(
        q=query,
        pageSize=20,
        fields="nextPageToken, files(id, name, webViewLink)",
        pageToken=token
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        print("No files found in this folder.")
    else:
        print(f"Found {len(files)} files:")
        for f in files:
            print(f" - Name: {f['name']} (ID: {f['id']})")

if __name__ == "__main__":
    list_folder()
