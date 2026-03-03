from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

class DriveService:
    def __init__(self, credentials_source=None):
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/drive']
        
        if not credentials_source:
            print("Warning: No credentials source provided to DriveService.")
            return

        try:
            from google.oauth2.credentials import Credentials as OAuth2Credentials
            from google.oauth2 import service_account as google_service_account
            creds = None
            
            # 1. Direct object check
            if hasattr(credentials_source, 'token') or hasattr(credentials_source, 'service_account_email'):
                creds = credentials_source
            # 2. Dict check
            elif isinstance(credentials_source, dict):
                if credentials_source.get('type') == 'service_account':
                    creds = google_service_account.Credentials.from_service_account_info(
                        credentials_source, scopes=self.scopes)
                else:
                    creds = OAuth2Credentials.from_authorized_user_info(credentials_source, self.scopes)
            # 3. File Path check
            elif isinstance(credentials_source, str) and os.path.exists(credentials_source):
                import json
                with open(credentials_source, 'r') as f:
                    data = json.load(f)
                if data.get('type') == 'service_account':
                    creds = google_service_account.Credentials.from_service_account_file(
                        credentials_source, scopes=self.scopes)
                else:
                    creds = OAuth2Credentials.from_authorized_user_file(credentials_source, self.scopes)
            
            if not creds:
                raise ValueError("Could not determine credential type from source")

            self.service = build('drive', 'v3', credentials=creds)
            print("DEBUG: Drive Service Initialized!")
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
        
        try:
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink',
                supportsAllDrives=True
            ).execute()
            
            # Make public so we don't need auth to view
            self.make_public(file['id'])
            
            return file
        except Exception as e:
            print(f"Upload Error: {e}")
            return None

    def make_public(self, file_id):
        if not self.service: return
        try:
            user_permission = {
                'type': 'anyone',
                'role': 'reader',
            }
            self.service.permissions().create(
                fileId=file_id,
                body=user_permission,
                fields='id',
            ).execute()
        except Exception as e:
            print(f"Permission Error: {e}")

    def transfer_ownership(self, file_id, email_address):
        if not self.service: return
        try:
            user_permission = {
                'type': 'user',
                'role': 'owner',
                'emailAddress': email_address
            }
            self.service.permissions().create(
                fileId=file_id,
                body=user_permission,
                transferOwnership=True,
                fields='id',
            ).execute()
        except Exception as e:
            print(f"Ownership Transfer Error: {e}")

    def find_files_by_name(self, name_query, folder_id=None):
        """Search for files in Drive. Optional: Restrict to folder."""
        if not self.service: return []
        
        try:
            # Prioritize exact match for stability
            # If folder_id is provided, limit scope
            query_parts = [f"name = '{name_query}'", "trashed = false"]
            
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            query = " and ".join(query_parts)
            
            results = self.service.files().list(
                q=query,
                pageSize=1,
                fields="files(id, name, webViewLink, thumbnailLink)"
            ).execute()
            
            files = results.get('files', [])
            if files: return files

            # Fallback: Contains (only if no folder strictness or if exact failed?)
            # For now, let's stick to exact match which is safer for "1.jpg"
            return []
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    def get_file_content(self, file_id):
        """Downloads file content as bytes."""
        if not self.service: return None
        try:
            from io import BytesIO
            from googleapiclient.http import MediaIoBaseDownload
            
            request = self.service.files().get_media(fileId=file_id)
            fh = BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            return fh.getvalue()
        except Exception as e:
            print(f"Error downloading file content: {e}")
            return None

    def get_folder_name(self, folder_id):
        """Retrieves folder name from ID."""
        if not self.service or not folder_id: return "Unknown Folder"
        try:
            folder = self.service.files().get(
                fileId=folder_id,
                fields='name',
                supportsAllDrives=True
            ).execute()
            return folder.get('name', 'Unknown Folder')
        except Exception as e:
            print(f"Error getting folder name: {e}")
            return f"Error: {str(e)}"

    def get_about(self):
        """Returns info about current identity."""
        if not self.service: return "Not Connected"
        try:
            about = self.service.about().get(fields="user(emailAddress)").execute()
            return about.get('user', {}).get('emailAddress', 'Unknown User')
        except:
            return "Unable to fetch identity"

