from services.drive_service import DriveService
import os

def test_upload():
    print("Testing Drive Upload...")
    
    # Initialize Drive Service (will use token.json automatically)
    drive_service = DriveService()
    
    if not drive_service.service:
        print("❌ Failed to initialize Drive Service.")
        return

    # Create a dummy file to upload
    dummy_file = "test_upload_oauth.txt"
    with open(dummy_file, "w") as f:
        f.write("This is a test upload from the bot using OAuth.")
        
    try:
        # Upload
        print(f"Uploading {dummy_file}...")
        file = drive_service.upload_file(dummy_file)
        
        if file:
            print(f"✅ Upload Successful!")
            print(f"File ID: {file.get('id')}")
            print(f"Web Link: {file.get('webViewLink')}")
            
            # Cleanup (Optional: Delete the file from local)
            os.remove(dummy_file)
        else:
            print("❌ Upload failed (returned None).")
            
    except Exception as e:
        print(f"❌ Upload failed with error: {e}")

if __name__ == "__main__":
    test_upload()
