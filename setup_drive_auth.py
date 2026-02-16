from services.auth_service import get_drive_credentials

def main():
    print("--- Google Drive OAuth Setup ---")
    print("This script will open a browser window to login to your Google Account.")
    print("Please make sure 'client_secret.json' is in this folder.")
    print("--------------------------------")
    
    creds = get_drive_credentials()
    
    if creds:
        print("\n✅ Authentication Successful!")
        print("token.json has been created.")
        print("You can now restart the main bot.")
    else:
        print("\n❌ Authentication Failed.")

if __name__ == '__main__':
    main()
