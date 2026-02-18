from dotenv import load_dotenv
import os
import time
import json
from services.sheet_service import SheetService
from services.drive_service import DriveService

load_dotenv()

print("--- Starting Connection Debug ---")
start_time = time.time()

# 1. Parse Creds
print("[1] Parsed Credentials...")
creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if creds_source and creds_source.strip().startswith('{'):
    try:
        creds_source = json.loads(creds_source)
        print("    -> Using JSON Content")
    except:
        print("    -> Failed to parse JSON")
else:
    print(f"    -> Using File Path: {creds_source}")

# 2. Sheet Service
print(f"[2] Connecting to SheetService... ({time.time() - start_time:.2f}s)")
try:
    sheet_service = SheetService(creds_source, os.getenv('GOOGLE_SHEET_ID'), os.getenv('GOOGLE_SHEET_NAME'))
    print(f"    -> Connected! Sheet: {sheet_service.sheet.title if sheet_service.sheet else 'None'} ({time.time() - start_time:.2f}s)")
except Exception as e:
    print(f"    -> Failed: {e}")

# 3. Drive Service
print(f"[3] Connecting to DriveService... ({time.time() - start_time:.2f}s)")
try:
    drive_service = DriveService(creds_source)
    print(f"    -> Connected! Service: {drive_service.service is not None} ({time.time() - start_time:.2f}s)")
except Exception as e:
    print(f"    -> Failed: {e}")

print(f"--- Finished in {time.time() - start_time:.2f}s ---")
