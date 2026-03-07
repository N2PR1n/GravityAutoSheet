import os
import certifi
import json
from services.drive_service import DriveService
from services.config_service import ConfigService
from services.auth_service import get_google_credentials
from services.ai_factory import AIFactory
import time

# Ensure certs
os.environ['SSL_CERT_FILE'] = certifi.where()

def run_bulk_test():
    print("--- 🚀 Starting Bulk AI Extraction Test ---")
    
    # 1. Setup Services
    creds = get_google_credentials()
    drive_service = DriveService(creds)
    config_service = ConfigService()
    
    ai_provider = config_service.get('AI_PROVIDER', 'openai')
    openai_key = os.getenv('OPENAI_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    ai_service = AIFactory.get_service(ai_provider, openai_key, gemini_key)
    
    print(f"Using AI Provider: {ai_provider.upper()}")
    
    # Initialize Sheet Service
    from services.sheet_service import SheetService
    sheet_name = config_service.get('ACTIVE_SHEET_NAME', 'เดือน 3/26')
    sheet_service = SheetService(creds, os.getenv('GOOGLE_SHEET_ID'), sheet_name)
    sheet_data = sheet_service.get_all_data()
    
    # Map sheet data by Run No
    expected_data = {}
    for row in sheet_data:
         run_no = str(row.get('Run No.', '')).strip()
         if run_no:
             expected_data[run_no] = {
                 'coins': str(row.get('เหรียญ', '')).strip(),
                 'price': str(row.get('ราคาสุดท้าย', row.get('ราคาของ', ''))).strip()
             }
             
    # Target files based on user input
    target_files = ["20.jpg", "12.jpg", "90.jpg", "103.jpg", "141.jpg", "107.jpg", "157.jpg", "48.jpg", "147.jpg", "125.jpg", "64.jpg", "86.jpg"]
    
    # Folder ID for "เดือน 3/26"
    folder_id = config_service.get_folder_for_sheet(sheet_name)
    
    print(f"\nTarget Folder ID: {folder_id} ({sheet_name})")
    print(f"Files to test: {len(target_files)} files\n")
    print("-" * 110)
    print(f"{'RunNo':<6} | {'Shop (AI)':<15} | {'Coins (AI)':<10} | {'Coins (Sheet)':<13} | {'Diff?':<6} | {'Price (AI)':<10} | {'Price (Sheet)':<13}")
    print("-" * 110)
    
    temp_dir = "temp_images"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    for filename in target_files:
        run_no = filename.replace('.jpg', '')
        try:
            # Search for file in Drive
            files = drive_service.find_files_by_name(filename, folder_id)
            if not files:
                print(f"{run_no:<6} | {'NOT FOUND':<15} | {'-':<10} | {'-':<13} | {'-':<6} | {'-':<10} | {'-':<13}")
                continue
                
            file_id = files[0]['id']
            
            # Download file
            image_content = drive_service.get_file_content(file_id)
            if not image_content:
                print(f"{run_no:<6} | {'DL FAILED':<15} | {'-':<10} | {'-':<13} | {'-':<6} | {'-':<10} | {'-':<13}")
                continue
                
            local_path = os.path.join(temp_dir, f"test_{filename}")
            with open(local_path, "wb") as f:
                f.write(image_content)
                
            # Run AI Extraction
            time.sleep(1)
            
            data = ai_service.extract_data_from_image(local_path)
            
            if data:
                shop = str(data.get('shop_name', ''))[:15]
                ai_coins = str(data.get('coins', ''))
                ai_price = str(data.get('price', ''))
                
                sheet_coins = expected_data.get(run_no, {}).get('coins', 'N/A')
                sheet_price = expected_data.get(run_no, {}).get('price', 'N/A')
                
                # Try to parse to float for comparison if possible
                try:
                     ai_c_val = abs(float(ai_coins))
                     sh_c_val = float(sheet_coins.replace(',', '')) if sheet_coins != 'N/A' and sheet_coins else 0.0
                     coin_diff = "❌" if abs(ai_c_val - sh_c_val) > 0.01 else "✅"
                except:
                     coin_diff = "?"

                print(f"{run_no:<6} | {shop:<15} | {ai_coins:<10} | {sheet_coins:<13} | {coin_diff:<6} | {ai_price:<10} | {sheet_price:<13}")
            else:
                print(f"{run_no:<6} | {'AI FAILED':<15} | {'-':<10} | {'-':<13} | {'-':<6} | {'-':<10} | {'-':<13}")
                
            # Cleanup temp file
            os.remove(local_path)
            
        except Exception as e:
            print(f"{run_no:<6} | ERROR: {str(e)[:10]:<15} | {'-':<10} | {'-':<13} | {'-':<6} | {'-':<10} | {'-':<13}")

    print("-" * 110)
    print("--- ✅ Bulk Test Completed ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_bulk_test()
