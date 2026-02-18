import streamlit as st
import pandas as pd
import sys
import os
import time
import re
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import av
import queue

# --- SETUP PATH & IMPORTS ---
# Add parent directory to path to import services
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from services.sheet_service import SheetService
from services.drive_service import DriveService
from dotenv import load_dotenv

# --- CONFIG & INIT ---
st.set_page_config(
    page_title="Gravity Stock Manager",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_dotenv()

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;600&display=swap');
    html, body, [class*="css"]  { font-family: 'Prompt', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .order-card {
        background-color: #1E1E1E; border: 1px solid #333;
        border-radius: 12px; padding: 15px; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .order-card:hover { border-color: #4CAF50; transform: translateY(-2px); }
    .status-badge {
        padding: 4px 10px; border-radius: 8px; font-size: 0.8rem; font-weight: bold;
    }
    .status-checked { background: rgba(76, 175, 80, 0.2); color: #81C784; border: 1px solid #4CAF50; }
    .status-pending { background: rgba(255, 193, 7, 0.2); color: #FFD54F; border: 1px solid #FFC107; } 
    .status-uncheck { background: rgba(255, 235, 59, 0.15); color: #FFF176; border: 1px solid #FDD835; }
</style>
""", unsafe_allow_html=True)

st.title("📦 Gravity Stock Manager")

# --- SERVICE INITIALIZATION ---
@st.cache_resource
def get_services():
    # Load Credentials Path
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    sheet_name = os.getenv('GOOGLE_SHEET_NAME')
    
    # Resolve Path
    if creds_path and not os.path.isabs(creds_path):
        creds_path = os.path.join(parent_dir, creds_path)
        
    if not creds_path or not os.path.exists(creds_path):
        st.error(f"❌ Credentials not found at: {creds_path}")
        return None, None

    try:
        sheet_service = SheetService(creds_path, sheet_id, sheet_name)
        drive_service = DriveService(creds_path)
        return sheet_service, drive_service
    except Exception as e:
        st.error(f"❌ Service Init Failed: {e}")
        return None, None

sheet_service, drive_service = get_services()

if not sheet_service:
    st.stop()

# --- DATA LOADER ---
@st.cache_data(ttl=5) # Short TTL for realtime feel
def load_orders():
    data = sheet_service.get_all_data()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
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
        'Date': 'Date', 'date': 'Date', 'วันที่ bought': 'Date', 'วันที่': 'Date'
    }
    
    renamed = {}
    for col in df.columns:
        for k, v in col_map.items():
            if k in col: # Partial match
                renamed[col] = v
                break
    
    if renamed:
        df.rename(columns=renamed, inplace=True)
    
    return df

# --- UI DIALOGS ---
@st.dialog("Confirm Uncheck")
def dialog_confirm_uncheck(order_id, run_no):
    st.write(f"Are you sure you want to uncheck Order **#{run_no}**?")
    if st.button("Yes, Uncheck", type="primary"):
        if order_id and sheet_service.update_order_status(order_id, "Pending"):
            st.success("Unchecked!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Failed to update.")

@st.dialog("📷 Scan Barcode (Realtime)")
def dialog_scanner():
    mode = st.radio("Mode:", ["Realtime (Fast)", "Native (Stable)"], horizontal=True, label_visibility="collapsed")
    
    if mode == "Native (Stable)":
        st.write("Click 'Take Photo' to scan.")
        img_file = st.camera_input("Scanner", label_visibility="collapsed")
        if img_file:
            bytes_data = img_file.getvalue()
            file_bytes = np.asarray(bytearray(bytes_data), dtype=np.uint8)
            original_img = cv2.imdecode(file_bytes, 1)
            
            # --- Preprocessing Pipeline ---
            attempts = []
            
            # 1. Original
            attempts.append(original_img)
            
            # 2. Grayscale
            gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
            attempts.append(gray)
            
            # 3. Thresholding (Binary)
            _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            attempts.append(thresh)
            
            # 4. Adaptive Thresholding (good for shadows)
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            attempts.append(adaptive)
            
            # 5. Zoom/Crop Center (often helps if barcode is small)
            h, w = gray.shape
            center_h, center_w = h // 2, w // 2
            crop_h, crop_w = h // 2, w // 2
            start_y = max(0, center_h - crop_h // 2)
            start_x = max(0, center_w - crop_w // 2)
            cropped = gray[start_y:start_y+crop_h, start_x:start_x+crop_w]
            attempts.append(cropped)

            found_code = None
            
            for i, img_attempt in enumerate(attempts):
                codes = decode(img_attempt)
                if codes:
                    found_code = codes[0].data.decode("utf-8")
                    break
            
            if found_code:
                st.session_state.search_val = found_code
                st.success(f"✅ Found: {found_code}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("❌ No barcode found. Try moving closer or better lighting.")
                with st.expander("Debug View"):
                    st.image(original_img, caption="Original", channels="BGR")
                    st.image(adaptive, caption="Adaptive Threshold")

    else:
        st.write("Point your camera at a barcode.")
    
        # Shared queue for results
        if 'result_queue' not in st.session_state:
            st.session_state.result_queue = queue.Queue()
            
        result_queue = st.session_state.result_queue
    
        def video_frame_callback(frame):
            img = frame.to_ndarray(format="bgr24")
            
            codes = decode(img)
            if codes:
                for code in codes:
                    data = code.data.decode("utf-8")
                    
                    # Draw Box
                    try:
                        (x, y, w, h) = code.rect
                        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 3)
                        cv2.putText(img, data, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    except: pass
                    
                    # Queue result
                    try:
                        result_queue.put_nowait(data)
                    except:
                        pass
            
            return av.VideoFrame.from_ndarray(img, format="bgr24")
    
        # Use a simpler configuration to avoid 'is_alive' threading race conditions
        # async_processing=False prevents some threading issues but might be slower behavior
        try:
            webrtc_streamer(
                key="barcode-scanner-v4", 
                mode=WebRtcMode.SENDRECV,
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                video_frame_callback=video_frame_callback,
                media_stream_constraints={"video": True, "audio": False},
                async_processing=False, # CHANGED: Set to False to fix threading crash
            )
        except Exception as e:
            st.error(f"Scanner Error: {e}")
            st.info("Try refreshing the page if the camera doesn't start.")
    
        # Check for result
        try:
            if not result_queue.empty():
                data = result_queue.get_nowait()
                st.session_state.search_val = data
                st.success(f"✅ Found: {data}")
                time.sleep(1)
                st.rerun()
        except:
            pass


# --- HELPERS ---
def process_drive_image(link):
    """Converts Drive Viewer Link to Direct Image URL."""
    if not isinstance(link, str): return None
    link = link.strip()
    if not link: return None
    
    # 1. Clean Link
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

# --- MAIN UI ---
if 'search_val' not in st.session_state:
    st.session_state.search_val = ""

# Top Bar
c1, c2 = st.columns([5, 1])
with c1:
    # Realtime search: st.text_input updates on blur usually. 
    # Streamlit doesn't support true key-up event without custom component, 
    # but regular text_input is fast enough for most.
    search_query = st.text_input("🔍 Search (Order ID, Run No, Name, Tracking)", value=st.session_state.search_val, placeholder="Start typing...", label_visibility="collapsed")
    # Auto-rerun on clear (Streamlit handles text_input state well)
    if search_query != st.session_state.search_val:
         st.session_state.search_val = search_query
         st.rerun()

with c2:
    if st.button("📷 Scan", use_container_width=True):
        dialog_scanner()

# Load Data
df = load_orders()

if not df.empty:
    # Filter (Robust substring search)
    if search_query:
        # Create a combined string for searching across multiple interesting columns
        search_cols = ['Order ID', 'Run No', 'Name', 'Tracking', 'Item']
        existing_cols = [c for c in search_cols if c in df.columns]
        
        mask = df[existing_cols].astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df.head(10) # Show latest 10 by default
        
    st.write(f"Found {len(filtered_df)} orders")
    
    # Cards
    for idx, row in filtered_df.iterrows():
        status = row.get('Status', 'Pending')
        status = str(status).strip() if status else 'Pending'
        is_checked = status.lower() == 'checked'
        
        status_style = "status-checked" if is_checked else "status-uncheck" # User requested yellow for uncheck
        # Label: If pending, show 'Pending' (Yellow)
        status_label = status
        
        with st.container():
            col_img, col_detail = st.columns([1, 2])
            
            # --- IMAGE COLUMN ---
            with col_img:
                img_link = row.get('Image Link', '')
                direct_url = process_drive_image(str(img_link))
                
                if direct_url:
                    st.image(direct_url, use_container_width=True)
                else: 
                    # Fallback: Try to find by Order ID in Drive
                    order_id_str = str(row.get('Order ID', '')).strip()
                    if order_id_str and drive_service:
                        found_files = drive_service.find_files_by_name(order_id_str)
                        if found_files:
                            # Use the first match
                            f = found_files[0]
                            new_url = process_drive_image(f.get('webViewLink'))
                            if new_url:
                                st.image(new_url, use_container_width=True)
                                st.caption("📷 Recovered from Drive")
                            else:
                                st.info("No Preview")
                        else:
                             st.info("No Image Found")
                    else:
                        st.info("No Image Info")

            # --- DETAIL COLUMN ---
            with col_detail:
                st.markdown(f"""
                <div class="order-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #444; padding-bottom:10px; margin-bottom:10px;">
                        <span style="font-size:1.4rem; font-weight:bold; color:#4CAF50;">#{row.get('Run No', '-')}</span>
                        <span class="status-badge {status_style}">{status_label}</span>
                    </div>
                    <div style="color:#eee; font-size:1rem;">
                        <div style="margin-bottom:4px;"><b>👤 Name:</b> {row.get('Name', '-')}</div>
                        <div style="margin-bottom:4px;"><b>📦 Item:</b> {row.get('Item', '-')}</div>
                        <div style="margin-bottom:4px;"><b>💰 Price:</b> {row.get('Price', '-')} | <b>🪙 Coins:</b> {row.get('Coins', '0')}</div>
                        <div style="margin-bottom:4px;"><b>🏗️ Platform:</b> {row.get('Platform', '-')} | <b>📅 Date:</b> {row.get('Date', '-')}</div>
                        <div style="font-size:0.85rem; color:#aaa; margin-top:8px;">
                            Order ID: {row.get('Order ID', '-')} <br>
                            Tracking: {row.get('Tracking', '-')}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # --- ACTIONS ---
                # Check / Uncheck
                
                # If Checked -> Show Uncheck Button
                if is_checked:
                    if st.button("❌ Uncheck", key=f"unchk_{idx}", type="secondary", use_container_width=True):
                         dialog_confirm_uncheck(row.get('Order ID'), row.get('Run No'))
                         
                # If Pending -> Show Check Button
                else:
                    if st.button(f"✅ Check", key=f"chk_{idx}", type="primary", use_container_width=True):
                         order_id = row.get('Order ID')
                         if order_id:
                             if sheet_service.update_order_status(order_id, "Checked"):
                                 st.success(f"Updated {order_id}!")
                                 time.sleep(0.5)
                                 st.cache_data.clear()
                                 st.rerun()
                             else:
                                 st.error("Update failed")

else:
    st.info("No data found or Sheet is empty.")
