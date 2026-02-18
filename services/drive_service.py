from google.oauth2 import service_account
from googleapiclient.discovery import build

class DriveService:
    def __init__(self, credentials_source=None):
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/drive']
        
        if not credentials_source:
            print("Warning: No credentials source provided to DriveService.")
            return

        try:
            creds = None
            if isinstance(credentials_source, dict):
                # Load from Dict
                creds = service_account.Credentials.from_service_account_info(
                    credentials_source, scopes=self.scopes)
            else:
                # Load from File Path
                creds = service_account.Credentials.from_service_account_file(
                    credentials_source, scopes=self.scopes)
            
            self.service = build('drive', 'v3', credentials=creds)
            print("DEBUG: Drive Service Initialized with Service Account!")
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
                fields='id, webViewLink, webContentLink'
            ).execute()
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

