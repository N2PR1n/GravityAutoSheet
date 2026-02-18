from flask import Flask, render_template, jsonify, request, redirect
import os
import sys
import pandas as pd
from dotenv import load_dotenv
import re

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
app.register_blueprint(bot_bp)
# load_dotenv() # Moved to top

# Service Instances
sheet_service = None
drive_service = None

def get_services():
    global sheet_service, drive_service
    
    if sheet_service and drive_service:
        return sheet_service, drive_service

    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    # Resolve Path
    if creds_path and not os.path.isabs(creds_path):
        creds_path = os.path.abspath(os.path.join(current_dir, creds_path))
        
    print(f"DEBUG: Loading credentials from {creds_path}")

    if not creds_path or not os.path.exists(creds_path):
        print(f"❌ Credentials not found at: {creds_path}")
        return None, None

    try:
        sheet_service = SheetService(creds_path, sheet_id, sheet_name)
        drive_service = DriveService(creds_path)
        return sheet_service, drive_service
    except Exception as e:
        print(f"❌ Service Init Failed: {e}")
        return None, None

# Initialize on startup
get_services()

# --- HELPERS ---
def process_drive_image(link):
    """Converts Drive Viewer Link to Direct Image URL."""
    if not isinstance(link, str): return None
    link = link.strip()
    if not link: return None
    
    # Check if it's already a direct link or something else
    if "lh3.googleusercontent.com" in link:
        return link

    # Extract ID
    # 1. Cleaner Regex
    match = re.search(r'"(http[^"]+)"', link)
    url = match.group(1) if match else link
    
    if not url.startswith('http'): return None

    # 2. Extract File ID
    file_id = None
    match_id = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if not match_id:
        match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        
    if match_id:
        file_id = match_id.group(1)
            
    if file_id:
        # Return lh3 link which acts as a direct image proxy
        return f"https://lh3.googleusercontent.com/d/{file_id}=s1000"

    return url

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/orders')
def get_orders():
    if not sheet_service:
        return jsonify({'error': 'Services not initialized'}), 500

    try:
        data = sheet_service.get_all_data()
        if not data:
            return jsonify([])
        
        df = pd.DataFrame(data)
        
        # Normalize Columns
        col_map = {
            'Run No': 'Run No', 'run_no': 'Run No', 'ลำดับ': 'Run No',
            'Name': 'Name', 'receiver_name': 'Name', 'ชื่อลูกค้า': 'Name', 'ชื่อหน้ากล่อง': 'Name',
            'Item': 'Item', 'item_name': 'Item', 'ชื่อของ': 'Item', 'รายการสินค้า': 'Item',
            'Price': 'Price', 'price': 'Price', 'ยอดรวม': 'Price', 'ราคาของ': 'Price',
            'Status': 'Status', 'status': 'Status', 'สถานะ': 'Status',
            'Order ID': 'Order ID', 'order_id': 'Order ID', 'เลขออเดอร์': 'Order ID',
            'Image Link': 'Image Link', 'image_link': 'Image Link', 'Link รูป': 'Image Link',
            'Tracking Number': 'Tracking', 'tracking_number': 'Tracking', 'เลขพัสดุ': 'Tracking',
            'Platform': 'Platform', 'platform': 'Platform',
            'Coins': 'Coins', 'coins': 'Coins', 'เหรียญ': 'Coins',
            'Date': 'Date', 'date': 'Date', 'วันที่ bought': 'Date', 'วันที่': 'Date',
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

if __name__ == '__main__':
    # Use 0.0.0.0 to allow access from local network
    app.run(host='0.0.0.0', port=5001, debug=True)
