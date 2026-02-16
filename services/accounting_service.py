import pandas as pd
import os
from datetime import datetime

class AccountingService:
    def __init__(self, sheet_service, drive_service):
        self.sheet_service = sheet_service
        self.drive_service = drive_service
        self.temp_dir = "temp_reports"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def export_report(self, folder_id):
        """
        Fetches data, sorts it, generates Excel, and uploads to Drive.
        Returns: Drive Link
        """
        # 1. Get Data
        print("Fetching data for export...")
        records = self.sheet_service.get_all_data()
        if not records:
            return None

        # 2. Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Expected Columns based on SheetService mapping (approximate)
        # We need to map the header names from the sheet to our logic
        # Run No., Image Link, ชื่อหน้ากล่อง, ส่งที่ไหน, Platform, วันที่ซื้อ, ชื่อร้าน, ราคาของ, เหรียญ, ชื่อของ, เลขออเดอร์, เลขพัสดุ
        
        # Let's check if the dataframe is empty or missing columns
        if df.empty: return None

        # 3. Sort Data: Shop Name (H) -> Item Name (K) -> Price (I)
        # Note: Column headers from get_all_records() are the first row keys
        # We need to ensure we use the correct Thai headers as defined in the sheet
        # H: ชื่อร้าน
        # K: ชื่อของ
        # I: ราคาของ
        
        try:
            # Clean Price for sorting (remove commas)
            if 'ราคาของ' in df.columns:
                df['price_val'] = df['ราคาของ'].astype(str).str.replace(',', '', regex=True)
                df['price_val'] = pd.to_numeric(df['price_val'], errors='coerce').fillna(0)
            else:
                df['price_val'] = 0

            # Sort
            sort_cols = []
            if 'ชื่อร้าน' in df.columns: sort_cols.append('ชื่อร้าน')
            if 'ชื่อของ' in df.columns: sort_cols.append('ชื่อของ')
            sort_cols.append('price_val')
            
            df_sorted = df.sort_values(by=sort_cols)
            
            # Remove helper column
            df_sorted = df_sorted.drop(columns=['price_val'])
            
        except Exception as e:
            print(f"Sorting error: {e}")
            df_sorted = df # Fallback to original order

        # 4. Generate Excel
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Accounting_Report_{date_str}.xlsx"
        file_path = os.path.join(self.temp_dir, filename)
        
        print(f"Saving Excel to {file_path}...")
        df_sorted.to_excel(file_path, index=False, engine='openpyxl')

        # 5. Upload to Drive
        print("Uploading report to Drive...")
        drive_file = self.drive_service.upload_file(file_path, folder_id, custom_name=filename)
        
        if drive_file:
            return drive_file.get('webViewLink', '')
        return None
