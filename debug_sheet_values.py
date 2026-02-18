from dotenv import load_dotenv
import os
import json
from services.sheet_service import SheetService

load_dotenv()

print("--- Debugging Sheet Values ---")
creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if creds_source and creds_source.strip().startswith('{'):
    creds_source = json.loads(creds_source)

service = SheetService(creds_source, os.getenv('GOOGLE_SHEET_ID'), os.getenv('GOOGLE_SHEET_NAME'))

print(f"Connected to: {service.sheet.title}")

# Fetch raw values (formatted)
print("\n[Raw Values (Formatted)]")
rows = service.sheet.get_values()
if rows:
    headers = rows[0]
    row1 = rows[1] if len(rows) > 1 else []
    print(f"Headers: {headers}")
    print(f"Row 1: {row1}")
else:
    print("No data found.")

# Fetch raw values (formula) for Column A (Image Link)
print("\n[Formula Fetch (Column A)]")
# Get A column
formulas = service.sheet.col_values(1, value_render_option='FORMULA')
print(f"Column A Formulas: {formulas[:5]}") # Print first 5
