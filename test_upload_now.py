import os
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
from services.auth_service import get_google_credentials
from services.drive_service import DriveService

def main():
    creds = get_google_credentials()
    drive = DriveService(creds)
    folder_id = "1uUbaCs9CNAIZJj-tdX-3uHg1MZmPaLPY"
    print(f"Trying to upload to folder: {folder_id}")

    try:
        # Create a dummy image
        with open("dummy.jpg", "wb") as f:
            f.write(b"fake image content")
        
        print(f"Folder name: {drive.get_folder_name(folder_id)}")
        result = drive.upload_file("dummy.jpg", folder_id, "test_upload.jpg")
        if result:
            print(f"SUCCESS: {result.get('webViewLink')}")
        else:
            print("FAILED")
    except Exception as e:
        print(f"CRASH: {e}")

if __name__ == '__main__':
    main()
