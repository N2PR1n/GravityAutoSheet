from flask import Flask, render_template, jsonify, request, redirect
import os
import sys
import pandas as pd
from dotenv import load_dotenv
import re
import json

load_dotenv() # Load first!

# Add parent directory to path to import services
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from services.sheet_service import SheetService
from services.drive_service import DriveService
from routes.bot import bot_bp

# --- CONFIG & INIT ---
app = Flask(__name__)
try:
    app.register_blueprint(bot_bp)
except Exception as e:
    print(f"❌ Error registering blueprint: {e}")

# Service Instances
sheet_service = None
drive_service = None

def get_services():
    global sheet_service, drive_service
    
    if sheet_service and drive_service:
        return sheet_service, drive_service

    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

# ... (rest of imports)

# ...

def get_services():
    global sheet_service, drive_service
    
    if sheet_service and drive_service:
        return sheet_service, drive_service

    creds_source = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    # Check if creds_source is a file path or JSON string
    if creds_source:
        if creds_source.strip().startswith('{'):
            try:
                print("DEBUG: Detected JSON string for credentials.")
                creds_source = json.loads(creds_source)
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing GOOGLE_APPLICATION_CREDENTIALS as JSON: {e}")
                return None, None
        else:
            # Assume File Path
            if not os.path.isabs(creds_source):
                creds_source = os.path.abspath(os.path.join(current_dir, creds_source))
            
            print(f"DEBUG: Loading credentials from file: {creds_source}")
            if not os.path.exists(creds_source):
                print(f"❌ Credentials file not found at: {creds_source}")
                return None, None

    if not creds_source:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set.")
        return None, None

    try:
        sheet_service = SheetService(creds_source, sheet_id, sheet_name)
        drive_service = DriveService(creds_source) # Drive might ignore it but passing anyway
        return sheet_service, drive_service
    except Exception as e:
        print(f"❌ Service Init Failed: {e}")
        return None, None

# ...

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/v2')
def index_v2():
    return render_template('index_v2.html')

@app.route('/api/orders')
def get_orders():
    sheet_service, _ = get_services()
    if not sheet_service:
        return jsonify({'error': 'Services not initialized'}), 500

    try:
        data = sheet_service.get_all_data()
        if not data:
            return jsonify([])
        
        df = pd.DataFrame(data)
        
        # Normalize Columns
        col_map = {
            'Run No': 'Run No', 'run_no': 'Run No', 'ลำดับ': 'Run No', 'Run No.': 'Run No',
            'Name': 'Name', 'receiver_name': 'Name', 'ชื่อลูกค้า': 'Name', 'ชื่อหน้ากล่อง': 'Name',
            'Item': 'Item', 'item_name': 'Item', 'ชื่อของ': 'Item', 'รายการสินค้า': 'Item',
            'Price': 'Price', 'price': 'Price', 'ยอดรวม': 'Price', 'ราคาของ': 'Price',
            'Shop': 'Shop', 'shop': 'Shop', 'shop_name': 'Shop', 'ชื่อร้าน': 'Shop',
            'Status': 'Status', 'status': 'Status', 'สถานะ': 'Status',
            'Order ID': 'Order ID', 'order_id': 'Order ID', 'เลขออเดอร์': 'Order ID', 'เลขอเดอร์': 'Order ID',
            'Image Link': 'Image Link', 'image_link': 'Image Link', 'Link รูป': 'Image Link',
            'Tracking Number': 'Tracking', 'tracking_number': 'Tracking', 'เลขพัสดุ': 'Tracking',
            'Platform': 'Platform', 'platform': 'Platform',
            'Coins': 'Coins', 'coins': 'Coins', 'เหรียญ': 'Coins',
            'Date': 'Date', 'date': 'Date', 'วันที่ bought': 'Date', 'วันที่': 'Date', 'วันที่ซื้อ': 'Date',
            'Location': 'Location', 'location': 'Location', 'ที่อยู่': 'Location', 'ส่งที่ไหน': 'Location'
        }
        
        renamed = {}
        for col in df.columns:
            for k, v in col_map.items():
                if k in col: 
                    renamed[col] = v
                    break
        
        if renamed:
            df.rename(columns=renamed, inplace=True)
            
        # Process Image Links
        records = df.to_dict(orient='records')
        for r in records:
            raw_link = str(r.get('Image Link', ''))
            r['DirectImage'] = process_drive_image(raw_link)
            r['RawImageLink'] = raw_link

        return jsonify(records)
    except Exception as e:
        print(f"❌ API Error /api/orders: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/check', methods=['POST'])
def check_order():
    sheet_service, _ = get_services()
    if not sheet_service: return jsonify({'error': 'Service unavailable'}), 500
    
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id: return jsonify({'error': 'Order ID required'}), 400
    
    try:
        success = sheet_service.update_order_status(order_id, "Checked")
        return jsonify({'success': success})
    except Exception as e:
        print(f"❌ Check Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/uncheck', methods=['POST'])
def uncheck_order():
    sheet_service, _ = get_services()
    if not sheet_service: return jsonify({'error': 'Service unavailable'}), 500
    
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id: return jsonify({'error': 'Order ID required'}), 400
    
    try:
        success = sheet_service.update_order_status(order_id, "Pending")
        return jsonify({'success': success})
    except Exception as e:
        print(f"❌ Uncheck Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/find_image/<order_target>')
def find_image(order_target):
    _, drive_service = get_services()
    if not drive_service: return jsonify({'error': 'Service unavailable'}), 500
    
    # User provided folder ID
    FOLDER_ID = "1KdLuDJIyHiyDy6-M-dzU2LyLLOES4x4l"
    
    try:
        # Search by exact name "1.jpg", "2.jpg" etc. 
        target_name = str(order_target).strip()
        possible_names = [f"{target_name}.jpg", target_name]
        
        found_file = None
        for name in possible_names:
            files = drive_service.find_files_by_name(name, folder_id=FOLDER_ID)
            if files:
                found_file = files[0]
                break
        
        if found_file:
            url = process_drive_image(found_file.get('webViewLink'))
            return jsonify({'found': True, 'url': url})
            
        return jsonify({'found': False})
    except Exception as e:
        print(f"❌ Find Image Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sheets', methods=['GET'])
def get_sheets():
    sheet_service, _ = get_services()
    if not sheet_service: return jsonify({'error': 'Service unavailable'}), 500
    try:
        sheets = sheet_service.get_worksheets()
        current = sheet_service.sheet.title if sheet_service.sheet else ""
        return jsonify({'sheets': sheets, 'current': current})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/set_sheet', methods=['POST'])
def set_sheet():
    sheet_service, _ = get_services()
    if not sheet_service: return jsonify({'error': 'Service unavailable'}), 500
    data = request.json
    sheet_name = data.get('sheet_name')
    if not sheet_name: return jsonify({'error': 'Sheet name required'}), 400
    
    success = sheet_service.set_worksheet(sheet_name)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to switch sheet'}), 500

if __name__ == '__main__':
    # Use 0.0.0.0 to allow access from local network
    app.run(host='0.0.0.0', port=5001, debug=True)
