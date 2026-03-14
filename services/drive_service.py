from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

class DriveService:
    def __init__(self, credentials=None):
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/drive']
        
        if not credentials:
            print("Warning: No credentials provided to DriveService.")
            return

        try:
            # Directly use the authorized user credentials
            self.service = build('drive', 'v3', credentials=credentials)
            print("DEBUG: Drive Service Initialized (User Identity)")
        except Exception as e:
            print(f"Warning: DriveService init failed: {e}")
            self.service = None

    def upload_file(self, file_path, folder_id=None, custom_name=None, overwrite=True):
        if not self.service:
            print("Drive service not initialized.")
            return None

        file_name = custom_name if custom_name else os.path.basename(file_path)
        
        # --- Handle Overwrite Logic ---
        if overwrite and file_name:
            try:
                existing_files = self.find_files_by_name(file_name, folder_id=folder_id)
                for existing in existing_files:
                    print(f"DEBUG: Found existing file {file_name} (ID: {existing['id']}). Deleting for overwrite.")
                    self.delete_file(existing['id'])
            except Exception as e:
                print(f"DEBUG: Error during overwrite check: {e}")

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
            
            # Make public so we don't need auth to view in front-end
            self.make_public(file['id'])
            
            return file
        except Exception as e:
            print(f"Upload Error: {e}")
            raise  # Re-raise so caller can report real error to user

    def delete_file(self, file_id):
        """Permanently deletes a file by ID."""
        if not self.service or not file_id: return
        try:
            self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
            print(f"DEBUG: Successfully deleted file {file_id}")
        except Exception as e:
            print(f"Delete Error for {file_id}: {e}")

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
            query_parts = [f"name = '{name_query}'", "trashed = false"]
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            query = " and ".join(query_parts)
            results = self.service.files().list(
                q=query,
                pageSize=1,
                fields="files(id, name, webViewLink, thumbnailLink)",
                supportsAllDrives=True
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    def list_images_in_folder(self, folder_id):
        """Lists all image files in a specific folder."""
        if not self.service or not folder_id: return []
        try:
            query = f"'{folder_id}' in parents and trashed = false and mimeType contains 'image/'"
            results = self.service.files().list(
                q=query,
                pageSize=1000,
                fields="files(id, name)",
                supportsAllDrives=True
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"Error listing folder contents: {e}")
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
