import os
import certifi
import json
import csv
import socket
from services.drive_service import DriveService
from services.config_service import ConfigService
from services.auth_service import get_google_credentials
from services.ai_factory import AIFactory
import time

# Ensure certs and set global socket timeout to prevent Drive API hangs
os.environ['SSL_CERT_FILE'] = certifi.where()
socket.setdefaulttimeout(15)

def run_full_accuracy_test():
    print("--- 🚀 Starting Full AI Extraction Accuracy Test ---")
    
    creds = get_google_credentials()
    drive_service = DriveService(creds)
    config_service = ConfigService()
    
    ai_provider = config_service.get('AI_PROVIDER', 'openai')
    openai_key = os.getenv('OPENAI_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    ai_service = AIFactory.get_service(ai_provider, openai_key, gemini_key)
    
    print(f"Using AI Provider: {ai_provider.upper()}")
    
    from services.sheet_service import SheetService
    sheet_name = config_service.get('ACTIVE_SHEET_NAME', 'เดือน 3/26')
    sheet_service = SheetService(creds, os.getenv('GOOGLE_SHEET_ID'), sheet_name)
    sheet_data = sheet_service.get_all_data()
    
    expected_data = {}
    for row in sheet_data:
         run_no = str(row.get('Run No.', '')).strip()
         if run_no:
             expected_data[run_no] = {
                 'coins': str(row.get('เหรียญ', '')).strip(),
                 'price': str(row.get('ราคาสุดท้าย', row.get('ราคาของ', ''))).strip(),
                 'shop': str(row.get('ชื่อร้าน', '')).strip(),
                 'receiver': str(row.get('ชื่อหน้ากล่อง', '')).strip()
             }
             
    folder_id = config_service.get_folder_for_sheet(sheet_name)
    print(f"\nTarget Folder ID: {folder_id} ({sheet_name})")
    
    print("Fetching image list from Google Drive...")
    all_images = drive_service.list_images_in_folder(folder_id)
    image_files = [f for f in all_images if any(f['name'].lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png'])]
    
    # Process only the 30 most recent images to prevent API hangs and excessive wait times.
    image_files = image_files[:30]
    print(f"Total image files found: {len(all_images)} | Testing latest {len(image_files)} files\n")
    
    temp_dir = "temp_images"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    csv_file_path = "ai_accuracy_report.csv"
    
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["RunNo", "Filename", "Status", "AI_Shop", "Sheet_Shop", "AI_Coins", "Sheet_Coins", "Coin_Match", "AI_Price", "Sheet_Price", "Price_Match", "AI_Receiver", "Sheet_Receiver"])
        
        for index, image in enumerate(image_files):
            filename = image['name']
            file_id = image['id']
            run_no = filename.lower().replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
            
            print(f"[{index+1}/{len(image_files)}] Processing Run No: {run_no} ({filename})...")
            
            sheet_info = expected_data.get(run_no, {})
            if not sheet_info:
                print(f"  > Warning: Run No {run_no} not found in Sheet.")
            
            sheet_coins = sheet_info.get('coins', 'N/A')
            sheet_price = sheet_info.get('price', 'N/A')
            sheet_shop = sheet_info.get('shop', 'N/A')
            sheet_receiver = sheet_info.get('receiver', 'N/A')
            
            try:
                image_content = drive_service.get_file_content(file_id)
                if not image_content:
                    print(f"  > DL FAILED")
                    writer.writerow([run_no, filename, "DL_FAILED", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
                    continue
                    
                local_path = os.path.join(temp_dir, f"test_{filename}")
                with open(local_path, "wb") as f:
                    f.write(image_content)
                    
                # Strict 4.5 second delay to stay under OpenAI 30k TPM rate limit
                time.sleep(4.5)
                
                # Retry wrapper
                data = None
                for attempt in range(5):
                    try:
                        data = ai_service.extract_data_from_image(local_path)
                        if data is None:
                            raise Exception("AI returned None (probable Rate Limit)")
                        break
                    except Exception as e:
                        if attempt == 4:
                            print(f"  > AI Exception: {str(e)[:50]}")
                        else:
                            time.sleep(8) # Extended backoff
                
                if data:
                    ai_shop = str(data.get('shop_name', ''))
                    ai_coins = str(data.get('coins', ''))
                    ai_price = str(data.get('price', ''))
                    ai_receiver = str(data.get('receiver_name', ''))
                    
                    try:
                         ai_c_val = abs(float(ai_coins))
                         sh_c_val = float(sheet_coins.replace(',', '')) if sheet_coins != 'N/A' and sheet_coins else 0.0
                         coin_match = "TRUE" if abs(ai_c_val - sh_c_val) < 0.01 else "FALSE"
                    except:
                         coin_match = "ERROR"

                    try:
                         ai_p_val = abs(float(ai_price))
                         sh_p_val = float(sheet_price.replace(',', '')) if sheet_price != 'N/A' and sheet_price else 0.0
                         price_match = "TRUE" if abs(ai_p_val - sh_p_val) < 0.01 else "FALSE"
                    except:
                         price_match = "ERROR"
                         
                    writer.writerow([run_no, filename, "SUCCESS", ai_shop, sheet_shop, ai_coins, sheet_coins, coin_match, ai_price, sheet_price, price_match, ai_receiver, sheet_receiver])
                    print(f"  > Done | Coins Match: {coin_match} | Price Match: {price_match}")
                else:
                    writer.writerow([run_no, filename, "AI_FAILED", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
                    print(f"  > AI FAILED")
                    
                os.remove(local_path)
                
            except Exception as e:
                print(f"  > ERROR: {str(e)[:40]}")
                writer.writerow([run_no, filename, "ERROR", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"])

    # Flush output aggressively
    print("-" * 80)
    print(f"--- ✅ Full Test Completed. Report saved to {csv_file_path} ---")

    print("-" * 80)
    print(f"--- ✅ Full Test Completed. Report saved to {csv_file_path} ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_full_accuracy_test()
