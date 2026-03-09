import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.auth_service import get_google_credentials
from services.sheet_service import SheetService

creds = get_google_credentials()
sheet_name = "โปร coin 3.26"
sheet_id = os.getenv("GOOGLE_SHEET_ID")

sheet = SheetService(creds, sheet_id, sheet_name)
data = sheet.get_all_data()

print(f"Total rows fetched: {len(data)}")
if len(data) > 0:
    first_row = data[0]
    print(f"First row keys: {list(first_row.keys())}")
    
    # Simulate pandas processing from app.py
    import pandas as pd
    df = pd.DataFrame(data)
    print(f"Df columns initially: {list(df.columns)}")
    
    col_map = {
        'Run No': 'Run No', 'run_no': 'Run No', 'ลำดับ': 'Run No', 'Run No.': 'Run No',
        'Name': 'Name', 'receiver_name': 'Name', 'ชื่อลูกค้า': 'Name', 'ชื่อหน้ากล่อง': 'Name',
        'Item': 'Item', 'item_name': 'Item', 'ชื่อของ': 'Item', 'รายการสินค้า': 'Item',
        'Price': 'Price', 'price': 'Price', 'ยอดรวม': 'Price', 'ราคาของ': 'Price',
        'Shop': 'Shop', 'shop': 'Shop', 'shop_name': 'Shop', 'ชื่อร้าน': 'Shop',
        'Status': 'Status', 'status': 'Status', 'สถานะ': 'Status',
        'Order ID': 'Order ID', 'order_id': 'Order ID', 'เลขออเดอร์': 'Order ID', 'เลขอเดอร์': 'Order ID',
        'Image Link': 'Image Link', 'image_link': 'Image Link', 'Link รูป': 'Image Link', 'Link Ima.': 'Image Link',
        'Tracking Number': 'Tracking', 'tracking_number': 'Tracking', 'เลขพัสดุ': 'Tracking',
        'Platform': 'Platform', 'platform': 'Platform',
        'Coins': 'Coins', 'coins': 'Coins', 'เหรียญ': 'Coins',
        'Date': 'Date', 'date': 'Date', 'วันที่ bought': 'Date', 'วันที่': 'Date', 'วันที่ซื้อ': 'Date',
        'Location': 'Location', 'location': 'Location', 'ที่อยู่': 'Location', 'ส่งที่ไหน': 'Location',
        'วันรับของ': 'SavedDate', 'delivery_date': 'SavedDate', 'saved_date': 'SavedDate'
    }
    
    renamed = {}
    for col in df.columns:
        for k, v in col_map.items():
            if k in col: 
                renamed[col] = v
                break
    df.rename(columns=renamed, inplace=True)
    print(f"Df columns renamed: {list(df.columns)}")
    records = df.to_dict(orient='records')
    print(f"Total records after processing: {len(records)}")
    if len(records) > 1:
         print(f"Second record: {records[1]}")
