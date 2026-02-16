from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from services.auth_service import get_drive_credentials
import os

class DriveService:
    def __init__(self, credentials_path=None): # credentials_path is no longer used but kept for compatibility
        try:
            # Use the new OAuth Flow (User Credentials)
            self.creds = get_drive_credentials()
            
            if self.creds:
                self.service = build('drive', 'v3', credentials=self.creds)
                print("DEBUG: Drive Service Initialized with OAuth!")
            else:
                print("Warning: Could not get Drive credentials.")
                self.service = None
                
        except Exception as e:
            print(f"Warning: DriveService init failed: {e}")
            self.service = None

    def upload_file(self, file_path, folder_id=None, custom_name=None):
        if not self.service:
            print("Drive service not initialized.")
            return None

        file_name = custom_name if custom_name else os.path.basename(file_path)
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype='image/jpeg')
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        # Make file public (or readable by anyone with link) so Gemini/User can access?
        # Actually Gemini sends bytes directly usually, but we need link for Sheet.
        self.make_public(file['id'])

        return file

    def make_public(self, file_id):
        if not self.service: return
        user_permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        self.service.permissions().create(
            fileId=file_id,
            body=user_permission,
            fields='id',
        ).execute()
