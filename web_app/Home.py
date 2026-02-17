import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import math
from sheet_utils import connect_to_sheet, download_image_from_drive

st.set_page_config(
    page_title="Gravity Stock Manager",
    page_icon="📦",
    layout="wide"
)
# st.error("DEBUG: Home.py is running! If you see this, the file is correct.")

# Custom CSS for Premium Look (Mobile & Desktop)
st.markdown("""
<style>
    /* Global Font & Theme */
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;600&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Prompt', sans-serif;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }

    /* Card Design */
    .order-card {
        background-color: #1E1E1E; /* Dark Mode Bg */
        color: #E0E0E0;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
        border: 1px solid #333;
        transition: transform 0.2s;
    }
    
    .order-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
        border-color: #4CAF50;
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        border-bottom: 1px solid #333;
        padding-bottom: 8px;
    }

    .run-no {
        font-size: 1.2rem;
        font-weight: 600;
        color: #4CAF50; /* Green Accent */
    }

    .status-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-checked {
        background-color: rgba(76, 175, 80, 0.2);
        color: #81C784;
        border: 1px solid #4CAF50;
    }
    .status-pending {
        background-color: rgba(255, 193, 7, 0.2);
        color: #FFD54F;
        border: 1px solid #FFC107;
    }

    .card-body p {
        margin: 4px 0;
        font-size: 0.95rem;
        color: #B0B0B0;
    }
    .card-body b {
        color: #FFFFFF;
    }

    /* Button Styling */
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 44px;
    }
    
    /* Search Bar */
    .stTextInput input {
        border-radius: 10px;
    }

</style>
""", unsafe_allow_html=True)

st.title("📦 Gravity Stock Manager")

# Reset button to clear cache if needed
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# st.write("DEBUG: 0. Calling connect_to_sheet()...")
with st.spinner("⏳ Connecting to Google Sheets (Please wait 10-20s)..."):
    sheet = connect_to_sheet()
# st.write(f"DEBUG: 5. Service Returned: {sheet}")

import re
import math

# Helper to clean headers
def clean_headers(df):
    df.columns = df.columns.str.strip()
    return df

# Cached Data Loading (TTL = 5 minutes, or manual refresh)
@st.cache_data(ttl=300, show_spinner=False)
def load_data(_sheet):
    # Fetch raw formulas to extract HYPERLINKs
    try:
        raw_data = _sheet.get_all_values(value_render_option='FORMULA')
        if len(raw_data) < 2:
            return pd.DataFrame()
        
        headers = raw_data[0]
        df = pd.DataFrame(raw_data[1:], columns=headers)
        df = clean_headers(df)
        return df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame()

if sheet:
    try:
        # Load Data
        df = load_data(sheet)
        
        if df.empty:
            st.warning("No data found or empty sheet.")
        else:
            # Helper to extract and CONVERT URL from =HYPERLINK("url", "label")
            def extract_image_url(cell_value):
                if not isinstance(cell_value, str): return ""
                
                url = ""
                # Regex for =HYPERLINK("URL", "Label")
                match = re.search(r'=HYPERLINK\s*\(\s*["\']([^"\']+)["\']', cell_value, re.IGNORECASE)
                if match:
                    url = match.group(1)
                elif cell_value.startswith('http'):
                    url = cell_value
                
                # Convert Drive View Link -> Direct Image Link
                # Pattern: https://drive.google.com/file/d/{FILE_ID}/view...
                if "drive.google.com" in url and "/d/" in url:
                    file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
                    if file_id_match:
                        file_id = file_id_match.group(1)
                        # Use thumbnail link for speed and better embedding success
                        return f"https://lh3.googleusercontent.com/d/{file_id}=w1000"
                        # Alternative: f"https://drive.google.com/uc?export=view&id={file_id}"
                
                return url

            df['Clean_Image_Link'] = df['Image Link'].apply(extract_image_url) if 'Image Link' in df.columns else ""

            # --- SEARCH & FILTER ---
            search_query = st.text_input("🔍 Search Order", placeholder="Type Order ID, Name, or Run No...").strip()
            
            filtered_df = pd.DataFrame()
            
            if search_query:
                mask = (
                    df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
                )
                filtered_df = df[mask]
                filtered_df = filtered_df.iloc[::-1] # Newest first
            else:
                # Default: Newest First
                filtered_df = df.iloc[::-1] 
            
            # --- PAGINATION ---
            TOTAL_ITEMS = len(filtered_df)
            ITEMS_PER_PAGE = 20
            TOTAL_PAGES = math.ceil(TOTAL_ITEMS / ITEMS_PER_PAGE)
            
            if TOTAL_PAGES > 1:
                # Center the Pagination
                c1, c2, c3 = st.columns([2, 3, 2])
                with c2:
                    current_page = st.number_input(
                        "Page", min_value=1, max_value=TOTAL_PAGES, value=1, step=1
                    )
                st.caption(f"Showing page {current_page} of {TOTAL_PAGES} ({TOTAL_ITEMS} total orders)")
            else:
                current_page = 1
                if TOTAL_ITEMS > 0:
                    st.caption(f"Showing all {TOTAL_ITEMS} orders")
            
            start_idx = (current_page - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            
            # Slice the dataframe for current page
            page_df = filtered_df.iloc[start_idx:end_idx]

            # --- DISPLAY CARDS ---
            st.markdown("---")
            
            if not page_df.empty:
                for index, row in page_df.iterrows():
                    # Extract Data (Handle missing columns gracefully)
                    run_no = row.get('Run No.', 'N/A')
                    name = row.get('ชื่อหน้ากล่อง', row.get('receiver_name', '-'))
                    item = row.get('ชื่อของ', 'N/A')
                    price = row.get('ราคาของ', '0') # Column I
                    # If 'ราคาของ' is empty, try 'ราคาสุดท้าย' or just show what we have
                    
                    coins = row.get('เหรียญ', '0')
                    order_id = row.get('เลขออเดอร์', '-')
                    tracking = row.get('เลขพัสดุ', '-')
                    platform = row.get('Platform', '-')
                    status = str(row.get('สถานะ', '')).strip()
                    image_link = row.get('Clean_Image_Link', '')

                    # Determine Badge
                    status_class = "status-checked" if "checked" in status.lower() else "status-pending"
                    status_text = "✅ Checked" if "checked" in status.lower() else "⏳ Pending"
                    
                    # Layout
                    with st.container():
                        st.markdown(f"""<div class="order-card">""", unsafe_allow_html=True)
                        
                        col_img, col_detail = st.columns([1, 2])
                        
                        with col_img:
                            # Image Handling: Server-Side Fetch
                            # 1. Extract File ID from Clean_Image_Link
                            # Link is: https://lh3.googleusercontent.com/d/{file_id}=w1000 OR https://drive.google.com/file/d/{file_id}...
                            # We used regex before to get 'Clean_Image_Link'. 
                            # If we used the lh3 format in previous step, we can extract ID easily.
                            
                            file_id = None
                            if image_link:
                                # Try simple extraction if it contains /d/
                                match = re.search(r'/d/([a-zA-Z0-9_-]+)', image_link)
                                if match:
                                    file_id = match.group(1)
                            
                            image_bytes = None
                            if file_id:
                                # Fetch bytes (Cached)
                                image_bytes = download_image_from_drive(file_id)
                            
                            if image_bytes:
                                st.image(image_bytes, use_container_width=True)
                            else:
                                # Component for No Image
                                st.markdown("""
                                <div style="background-color: #2D2D2D; height: 160px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 8px; color: #666; border: 2px dashed #444;">
                                    <span style="font-size: 2rem;">📷</span>
                                    <span style="font-size: 0.8rem;">No Image</span>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        with col_detail:
                            st.markdown(f"""
                            <div class="card-header" style="margin-top: 0; padding-top: 0;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span class="run-no">#{run_no}</span>
                                    <span style="font-size: 0.8rem; color: #888; background: #333; padding: 2px 8px; border-radius: 4px;">{platform}</span>
                                </div>
                                <span class="status-badge {status_class}">{status_text}</span>
                            </div>
                            <div class="card-body">
                                <p><b>Name:</b> {name}</p>
                                <p><b>Item:</b> {item}</p>
                                <div style="display: flex; gap: 15px; margin: 4px 0;">
                                    <p><b>💰 Price:</b> <span style="color: #4CAF50;">{price}</span></p>
                                    <p><b>🪙 Coins:</b> <span style="color: #FFC107;">{coins}</span></p>
                                </div>
                                <p style="font-size: 0.85rem; color: #777; margin-top: 8px;">Order ID: {order_id}</p>
                                <p style="font-size: 0.85rem; color: #777;">Tracking: {tracking}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Action Button
                            if 'checked' not in status.lower():
                                if st.button(f"✅ Mark as Checked", key=f"btn_{index}", use_container_width=True):
                                    try:
                                        cell = sheet.find(str(order_id))
                                        if cell:
                                            sheet.update_cell(cell.row, 15, "Checked") 
                                            st.toast(f"Updated #{run_no}!", icon="🎉")
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error("Order ID not found.")
                                    except Exception as ex:
                                        st.error(f"Failed: {ex}")

                        st.markdown("</div>", unsafe_allow_html=True) # End Card

            else:
                st.info("No orders found.")
                
    except Exception as e:
        st.error(f"⚡ Error processing data: {e}")
        st.write("Debug info:", e)
else:
    st.warning("⚠️ No connection to Google Sheets.")
