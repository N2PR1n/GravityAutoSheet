from flask import Flask, render_template, jsonify, request, redirect, g
import os
import sys
import pandas as pd
from dotenv import load_dotenv
import re
import json
import socket



# Cache for /api/orders
order_cache = {
    'data': None,
    'timestamp': 0,
    'sheet_name': None
}
CACHE_TTL = 10 # Seconds

load_dotenv() # Load first!

# Add parent directory to path to import services
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from services.sheet_service import SheetService
from services.drive_service import DriveService
from services.config_service import ConfigService
from services.openai_service import OpenAIService
from services.ai_factory import AIFactory
from routes.bot import bot_bp

# --- CONFIG & INIT ---
app = Flask(__name__)
try:
    app.register_blueprint(bot_bp)
except Exception as e:
    print(f"❌ Error registering blueprint: {e}")

# Config service remains singleton as it is read-only for most parts or file-based
_config_service_instance = None

def get_config_service():
    global _config_service_instance
    if _config_service_instance is None:
        from services.config_service import ConfigService
        _config_service_instance = ConfigService()
    return _config_service_instance

def get_services():
    # Use flask.g to store services per request for thread safety
    if 'sheet_service' in g and 'drive_service' in g:
        sheet_service = g.sheet_service
        drive_service = g.drive_service
        
        cfg = get_config_service()
        sheet_name = cfg.get('ACTIVE_SHEET_NAME', os.getenv('GOOGLE_SHEET_NAME'))
        
        current_sheet = sheet_service.sheet.title if sheet_service.sheet else ""
        if current_sheet != sheet_name:
            print(f"DEBUG: App sheet mismatch. Switching from {current_sheet} to {sheet_name}")
            sheet_service.set_worksheet(sheet_name)
        return sheet_service, drive_service

    # Init Config
    cfg = get_config_service()
    sheet_name = cfg.get('ACTIVE_SHEET_NAME', os.getenv('GOOGLE_SHEET_NAME'))
    
    import services.auth_service as auth_service
    
    try:
        creds_source = auth_service.get_google_credentials()
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        return None, None
    sheet_id = os.getenv('GOOGLE_SHEET_ID')

    try:
        g.sheet_service = SheetService(creds_source, sheet_id, sheet_name)
        g.drive_service = DriveService(creds_source)
        return g.sheet_service, g.drive_service
    except Exception as e:
        print(f"❌ Service Init Failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler for all unexpected exceptions."""
    print(f"🔥 Global Error: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e)
    }), 500

# ...

# --- ROUTES ---

def process_drive_image(link):
    if not link: return ""
    # Extract ID from: 
    # 1. https://drive.google.com/open?id=...
    # 2. https://drive.google.com/file/d/.../view
    
    file_id = None
    # Pattern 1: id=...
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', link)
    if match_id:
        file_id = match_id.group(1)
    
    # Pattern 2: /d/...
    if not file_id:
        match_d = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match_d:
            file_id = match_d.group(1)
            
    if file_id:
        # RETURN PROXY URL
        # This bypasses 403 Forbidden and Referrer issues
        return f"/api/proxy_image/{file_id}"
        
    return link

@app.route('/api/proxy_image/<file_id>')
def proxy_image(file_id):
    _, drive_service = get_services()
    if not drive_service: return jsonify({'error': 'Service unavailable'}), 500
    
    try:
        content = drive_service.get_file_content(file_id)
        if content:
            from flask import send_file
            from io import BytesIO
            return send_file(BytesIO(content), mimetype='image/jpeg') # Assume JPEG for now
        else:
             return "Image not found", 404
    except Exception as e:
        print(f"Proxy Error: {e}")
        return str(e), 500

@app.route('/')
def index():
    print("DEBUG: Index request received")
    return render_template('index_v2.html')

@app.route('/health')
def health():
    return "OK", 200

@app.route('/v2')
def index_v2():
    return render_template('index_v2.html')

@app.route('/api/orders')
def get_orders():
    global order_cache
    
    cfg = get_config_service()
    current_sheet = cfg.get('ACTIVE_SHEET_NAME', os.getenv('GOOGLE_SHEET_NAME'))
    
    import time
    now = time.time()
    
    # Check Cache
    if (order_cache['data'] is not None and 
        order_cache['sheet_name'] == current_sheet and 
        (now - order_cache['timestamp']) < CACHE_TTL):
        print(f"DEBUG: Returning cached orders for {current_sheet}")
        return jsonify(order_cache['data'])

    sheet_service, _ = get_services()
    if not sheet_service:
        return jsonify({'error': 'Services not initialized'}), 500

    try:
        data = sheet_service.get_all_data()
        if not data:
            return jsonify([])
        
        # Extended Logic: Fetch Formulas for Image Links
        image_formulas = sheet_service.get_image_links()
        
        for i, record in enumerate(data):
            formula_idx = i + 1
            if formula_idx < len(image_formulas):
                raw_formula = str(image_formulas[formula_idx])
                match_url = re.search(r'["\'](https?://[^"\']+)["\']', raw_formula)
                if match_url:
                    record['Image Link'] = match_url.group(1)
        
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
            'Location': 'Location', 'location': 'Location', 'ที่อยู่': 'Location', 'ส่งที่ไหน': 'Location',
            'วันรับของ': 'SavedDate', 'delivery_date': 'SavedDate', 'saved_date': 'SavedDate'
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

        # Update Cache
        order_cache['data'] = records
        order_cache['timestamp'] = now
        order_cache['sheet_name'] = current_sheet
        print(f"DEBUG: Cache updated for {current_sheet}")

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
        if success:
            order_cache['data'] = None # Invalidate
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
        if success:
            order_cache['data'] = None # Invalidate
        return jsonify({'success': success})
    except Exception as e:
        print(f"❌ Uncheck Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/find_image/<order_target>')
def find_image(order_target):
    _, drive_service = get_services()
    if not drive_service: return jsonify({'error': 'Service unavailable'}), 500
    
    # Use folder ID for specific sheet
    cfg = get_config_service()
    sheet_name = cfg.get('ACTIVE_SHEET_NAME', os.getenv("GOOGLE_SHEET_NAME"))
    FOLDER_ID = cfg.get_folder_for_sheet(sheet_name)
    
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
    try:
        sheet_service, _ = get_services()
        if not sheet_service:
            return jsonify({'error': 'Service unavailable (Init Failed)'}), 500
        
        sheets = sheet_service.get_worksheets()
        current = sheet_service.sheet.title if sheet_service and sheet_service.sheet else ""
        return jsonify({'sheets': sheets, 'current': current})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc() if os.getenv('FLASK_DEBUG') == '1' else 'Consult logs'
        }), 500

@app.route('/api/set_sheet', methods=['POST'])
def set_sheet():
    sheet_service, _ = get_services()
    if not sheet_service: return jsonify({'error': 'Service unavailable'}), 500
    data = request.json
    sheet_name = data.get('sheet_name')
    if not sheet_name: return jsonify({'error': 'Sheet name required'}), 400
    
    success = sheet_service.set_worksheet(sheet_name)
    if success:
        cfg = get_config_service()
        cfg.set('ACTIVE_SHEET_NAME', sheet_name)
        order_cache['data'] = None # Invalidate
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to switch sheet'}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    cfg = get_config_service()
    # Support optional sheet_name query param
    requested_sheet = request.args.get('sheet_name')
    active_sheet = cfg.get('ACTIVE_SHEET_NAME', os.getenv("GOOGLE_SHEET_NAME"))
    
    target_sheet = requested_sheet if requested_sheet else active_sheet
    
    return jsonify({
        'GOOGLE_DRIVE_FOLDER_ID': cfg.get_folder_for_sheet(target_sheet),
        'ACTIVE_SHEET_NAME': active_sheet,
        'TARGET_SHEET_NAME': target_sheet,
        'AI_PROVIDER': cfg.get('AI_PROVIDER', 'openai')
    })

@app.route('/api/ai_config', methods=['POST'])
def update_ai_config():
    cfg = get_config_service()
    data = request.json
    provider = data.get('provider')
    if provider in ['openai', 'gemini']:
        cfg.set('AI_PROVIDER', provider)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid AI Provider'}), 400

@app.route('/api/config', methods=['POST'])
def update_config():
    cfg = get_config_service()
    data = request.json
    folder_id = data.get('folder_id')
    sheet_name = data.get('sheet_name') # Frontend should send this
    
    if folder_id:
        if not sheet_name:
            sheet_name = cfg.get('ACTIVE_SHEET_NAME', os.getenv("GOOGLE_SHEET_NAME"))
        
        cfg.set_folder_for_sheet(sheet_name, folder_id)
        # Also ensure it's globally updated if it's the current sheet
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid data'}), 400

if __name__ == '__main__':
    # Use 0.0.0.0 to allow access from local network
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False, threaded=True)
