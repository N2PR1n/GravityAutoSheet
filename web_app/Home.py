import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_sheet_service

st.set_page_config(
    page_title="Gravity Stock Manager",
    page_icon="📦",
    layout="wide"
)

# Custom CSS for better mobile view
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        height: 3em;
        font-weight: bold;
        background-color: #00C853;
        color: white;
    }
    .order-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #2196F3;
    }
    .metric-box {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("📦 Gravity Stock Manager")

# Reset button to clear cache if needed
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

sheet = get_sheet_service()

if sheet:
    try:
        # Load Data
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Ensure Column O exists (Status)
        # GSheet headers might have trailing spaces, clean them
        df.columns = df.columns.str.strip()
        
        # Verify required columns exist
        required_cols = ['Run No.', 'Leik Order', 'Received Name', 'Status'] 
        # Note: Actual headers from user screenshot: 
        # "Image Link", "ชื่อหน้ากล่อง", "ส่งที่ไหน", ..., "เลขออเดอร์", "เลขพัสดุ", "วันรับของ", "สถานะ"
        # We need to map English DataFrame columns to these Thai headers if get_all_records uses first row.
        # Let's inspect the headers from the screenshot mapping.
        # A: Image Link
        # B: ชื่อหน้ากล่อง
        # C: ส่งที่ไหน
        # D: Run No. (Hidden in screenshot? Or user didn't show it? SheetService writes to Col D as Run No)
        # Let's assume standard names based on SheetService
        
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

    # Search Bar (Auto-focus if possible, but Streamlit limit)
    search_query = st.text_input("🔍 Search (Order ID / Name / Tracking / Run No)", placeholder="Scan Barcode or Type...").strip()

    if search_query:
        # Filter Logic (Case Insensitive)
        # We look into multiple columns
        mask = (
            df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        )
        results = df[mask]
        
        st.write(f"Found {len(results)} matching orders:")
        
        for index, row in results.iterrows():
            # Create a Card View
            # Using Thai headers based on previous context or assumptions. 
            # We'll rely on column content rather than exact header names if possible, but exact names are better.
            # Updated: Based on screenshot
            # Col B: ชื่อหน้ากล่อง
            # Col I: ราคาของ
            # Col K: ชื่อของ
            # Col L: เลขออเดอร์
            # Col M: เลขพัสดุ
            # Col O: สถานะ
            
            # Map Row Dictionary to Variables
            run_no = row.get('Run No.', row.get('Run No', '')) # Need to verify exact header of Col D
            # Actually SheetService writes headers? No, SheetService APPENDS data.
            # We assume the user has headers.
            # Let's try to access by generic names if standard headers aren't guaranteed.
            # But usually `get_all_records` uses the first row.
            
            # Let's show all relevant info in a nice layout
            with st.container():
                st.markdown(f"""
                <div class="order-card">
                    <h3>📦 Run No: {row.get('Run No.', 'N/A')}</h3>
                    <p><b>Name:</b> {row.get('ชื่อหน้ากล่อง', row.get('receiver_name', '-'))}</p>
                    <p><b>Item:</b> {row.get('ชื่อของ', row.get('item_name', '-'))}</p>
                    <p><b>Price:</b> {row.get('ราคาของ', row.get('price', '-'))}</p>
                    <p><b>Order ID:</b> {row.get('เลขออเดอร์', row.get('order_id', '-'))}</p>
                    <p><b>Status:</b> {row.get('สถานะ', row.get('Status', '-'))}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Action Button
                # Check status
                current_status = str(row.get('สถานะ', row.get('Status', ''))).lower()
                
                col_btn1, col_btn2 = st.columns([1, 1])
                
                if 'checked' in current_status:
                    st.success("✅ Already Checked")
                else:
                    if st.button(f"✅ CONFIRM CHECK (Run {row.get('Run No.', '')})", key=f"btn_{index}"):
                        # Update Google Sheet
                        try:
                            # 1. Find the actual row number in the sheet
                            # sheet row = index + 2 (1-based index + 1 for header)
                            # BUT `get_all_records` might skip empty rows? 
                            # Safe way: match Unique ID (Order ID)
                            
                            cell = sheet.find(str(row.get('เลขออเดอร์', row.get('order_id', ''))))
                            if cell:
                                # Update Column "สถานะ" (Column O -> Index 15)
                                sheet.update_cell(cell.row, 15, "Checked") # Col O
                                
                                st.toast(f"Updated Order {row.get('เลขออเดอร์', '')} to Checked!")
                                st.rerun()
                            else:
                                st.error("Could not find row in sheet to update.")
                        except Exception as ex:
                            st.error(f"Update failed: {ex}")

    else:
        st.info("👆 Enter Order ID, Name, or scan barcode to search.")
        
        # Show Summary Stats
        st.markdown("---")
        st.subheader("📊 Summary")
        if 'สถานะ' in df.columns:
            received = len(df[df['สถานะ'] == 'Checked'])
            total = len(df)
            st.metric("Total Checked", f"{received} / {total}")

else:
    st.warning("Please configure .env with CREDENTIALS.")
