import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.drive_service import DriveService

def main():
    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_source and creds_source.strip().startswith('{'):
        creds_source = json.loads(creds_source)
        
    drive_service = DriveService(creds_source)
    
    # Search globally for 240.jpg
    files = drive_service.service.files().list(
        q="name = '240.jpg' and trashed = false",
        fields="files(id, name, parents)"
    ).execute().get('files', [])
    
    for f in files:
        print(f"Found 240.jpg: ID={f['id']}, Parents={f.get('parents')}")
        
    # Search globally for "เดือน 2/26" folder
    folders = drive_service.service.files().list(
        q="mimeType = 'application/vnd.google-apps.folder' and name = 'เดือน 2/26' and trashed = false",
        fields="files(id, name)"
    ).execute().get('files', [])
    
    for folder in folders:
         print(f"Found folder: {folder['name']} with ID: {folder['id']}")

if __name__ == '__main__':
    main()
