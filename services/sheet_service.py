import gspread
from google.oauth2 import service_account
import socket
import requests.packages.urllib3.util.connection as urllib3_cn

# Removed monkey patch

class SheetService:
    def __init__(self, credentials_source, sheet_id, sheet_name=None):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        self.client = None
        self.sheet = None
        self.row_index_map = {} # Cache for Order ID -> Row Number
        self.status_col = None  # Cache for Status Column Index
        self.all_data_cache = None
        self.last_fetch_time = 0
        try:
            from google.oauth2.credentials import Credentials as OAuth2Credentials
            from google.oauth2 import service_account as google_service_account
            
            if isinstance(credentials_source, OAuth2Credentials) or isinstance(credentials_source, google_service_account.Credentials):
                self.creds = credentials_source
            elif isinstance(credentials_source, dict):
                # Load from Dict (Service Account)
                self.creds = google_service_account.Credentials.from_service_account_info(
                    credentials_source, scopes=self.scopes)
            else:
                # Load from File Path (Service Account)
                self.creds = google_service_account.Credentials.from_service_account_file(
                    credentials_source, scopes=self.scopes)
            
            self.client = gspread.authorize(self.creds)
            
            if sheet_name:
                try:
                    self.sheet = self.client.open_by_key(sheet_id).worksheet(sheet_name)
                    print(f"DEBUG: Connected to Sheet (Tab): '{self.sheet.title}'")
                except gspread.exceptions.WorksheetNotFound:
                    print(f"Warning: Worksheet '{sheet_name}' not found. Falling back to default.")
                    self.sheet = self.client.open_by_key(sheet_id).sheet1
            else:
                self.sheet = self.client.open_by_key(sheet_id).sheet1 # Default to first sheet
            
            print(f"DEBUG: Active Sheet Title: '{self.sheet.title}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Warning: SheetService init failed: {e}")
            self.sheet = None

    def get_worksheets(self):
        """Returns a list of all worksheet titles."""
        if not self.client: return []
        try:
            # Re-open spreadsheet to ensure fresh list
            spreadsheet = self.client.open_by_key(self.sheet.spreadsheet.id)
            return [ws.title for ws in spreadsheet.worksheets()]
        except Exception as e:
            print(f"Error getting worksheets: {e}")
            return []

    def set_worksheet(self, sheet_name):
        """Switches the active worksheet."""
        if not self.client: return False
        try:
            spreadsheet = self.client.open_by_key(self.sheet.spreadsheet.id)
            self.sheet = spreadsheet.worksheet(sheet_name)
            print(f"DEBUG: Switched to Sheet: '{self.sheet.title}'")
            return True
        except Exception as e:
            print(f"Error switching worksheet: {e}")
            return False

    def check_duplicate(self, order_id):
        """Checks if order_id already exists using local map or API fallback."""
        if not self.sheet or not order_id: return False
        
        order_id_str = str(order_id)
        # Use local row map if available (populated by get_all_data)
        if self.row_index_map:
            return order_id_str in self.row_index_map
            
        try:
            # Fallback to API if map is empty
            order_ids = self.sheet.col_values(12)  # Column L = 12
            return order_id_str in order_ids
        except Exception as e:
            print(f"Warning: Duplicate check failed: {e}")
            return False

    def get_all_data(self):
        """Fetches all records from the sheet, handling duplicate or empty headers."""
        if not self.sheet: return []
        try:
            # Use get_values() to get raw data
            rows = self.sheet.get_values()
            if not rows:
                return []
            
            headers = rows[0]
            data_rows = rows[1:]
            
            # Sanitize headers to handle duplicates and empties
            clean_headers = []
            header_counts = {}
            for i, h in enumerate(headers):
                h = str(h).strip()
                if not h:
                    h = f"unnamed_{i}"
                
                if h in header_counts:
                    header_counts[h] += 1
                    clean_headers.append(f"{h}_{header_counts[h]}")
                else:
                    header_counts[h] = 0
                    clean_headers.append(h)
            
            # Convert to list of dicts
            records = []
            self.row_index_map = {}
            for i, row in enumerate(data_rows):
                # Pad row with empty strings if it's shorter than headers
                row_extended = row + [""] * (len(clean_headers) - len(row))
                record = dict(zip(clean_headers, row_extended))
                records.append(record)
                
                # Build Row Map (Index starts at 1, Header is row 1, Data is row 2+)
                order_id = str(record.get('Order ID') or record.get('order_id') or record.get('เลขออเดอร์') or "")
                if order_id:
                    self.row_index_map[order_id] = i + 2
                
            self.all_data_cache = records
            import time
            self.last_fetch_time = time.time()
            return records
        except Exception as e:
            print(f"Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_image_links(self):
        """Fetches Column A formulas to extract real links."""
        if not self.sheet: return []
        try:
            # Fetch Column A (Index 1) as formulas
            return self.sheet.col_values(1, value_render_option='FORMULA')
        except Exception as e:
            print(f"Error fetching image links: {e}")
            return []

    def get_next_run_no(self):
        """Calculates next Run No. by finding the first missing integer starting from 1."""
        if not self.sheet: return 1
        
        import time
        run_nos_set = set()
        
        # Try to use cache if it's fresh (< 60s)
        if self.all_data_cache and (time.time() - self.last_fetch_time < 60):
            for r in self.all_data_cache:
                val = r.get('Run No') or r.get('run_no') or r.get('ลำดับ') or r.get('Run No.')
                if val and str(val).isdigit():
                    run_nos_set.add(int(val))
        else:
            try:
                # Column D is index 4
                col_values = self.sheet.col_values(4) 
                for val in col_values:
                    if str(val).isdigit():
                        run_nos_set.add(int(val))
            except Exception as e:
                print(f"Error getting run nos from API: {e}")
        
        # Find first missing number starting from 1
        next_no = 1
        while next_no in run_nos_set:
            next_no += 1
            
        return next_no

    def append_data(self, data_dict, run_no=None):
        """
        Appends a row to the sheet based on the dictionary.
        Mapped Columns:
        A: Image Link (Renamed to RunNo.jpg)
        ...
        D: Run No. (New)
        ...
        """
        if not self.sheet:
            print("Sheet service not connected.")
            return False

        # Helper to format float string
        def fmt_float(val):
            try:
                # Remove comma if present, convert to float, then format
                if isinstance(val, str):
                    val = val.replace(',', '')
                if val == '-' or val == '': return "0.00"
                return "{:,.2f}".format(float(val))
            except:
                return str(val)

        # Prepare row data (15 columns A-O)
        row = [""] * 15
        
        # Fill data
        # A: Image Link with Filename
        link = data_dict.get('image_link', '')
        # filename = f"{run_no}.jpg" if run_no else "image.jpg"
        # User requested: "Check Order [Run No]"
        label = f"Check Order {run_no}" if run_no else "Check Order"
        row[0] = f'=HYPERLINK("{link}", "{label}")' if link else "" 

        row[1] = data_dict.get('receiver_name', '')   # B
        row[2] = data_dict.get('location', '')        # C
        
        # D: Run No.
        row[3] = run_no if run_no else ""             # D
        
        row[4] = "" # E: Hidden
        row[5] = data_dict.get('platform', '')        # F
        row[6] = data_dict.get('date', '')            # G (Mapped from 'date' in prompt)
        row[7] = data_dict.get('shop_name', '')       # H
        row[8] = fmt_float(data_dict.get('price', 0)) # I
        row[9] = fmt_float(data_dict.get('coins', 0)) # J
        row[10] = data_dict.get('item_name', '')      # K
        row[11] = str(data_dict.get('order_id', ''))  # L
        
        # Tracking Number Logic: Only fill if provided (Amaze), otherwise leave blank.
        row[12] = str(data_dict.get('tracking_number', '')) # M

        row[13] = ""           # N: Delivery Date
        
        # O: Status (New Default: Pending)
        row[14] = "Pending"

        # IMPORTANT: Use value_input_option='USER_ENTERED' to parse formulas
        try:
            result = self.sheet.append_row(row, value_input_option='USER_ENTERED')
            print(f"DEBUG: Data appended result: {result}")
            return True
        except Exception as e:
            print(f"Error appending data to sheet: {e}")
            return False

    def update_order_status(self, order_id, status="Checked"):
        """Updates the status of an order using optimized row mapping."""
        if not self.sheet: return False
        try:
            order_id_str = str(order_id)
            row_idx = self.row_index_map.get(order_id_str)
            
            # Fallback to search if map is empty/missing (e.g. newly appended)
            if not row_idx:
                print(f"DEBUG: Row map miss for {order_id}, searching...")
                cell = self.sheet.find(order_id_str)
                if not cell: return False
                row_idx = cell.row
                # Update map for next time
                self.row_index_map[order_id_str] = row_idx

            # Find/Cache Status Column
            if not self.status_col:
                headers = self.sheet.row_values(1)
                if "Status" in headers:
                    self.status_col = headers.index("Status") + 1
                elif "สถานะ" in headers:
                    self.status_col = headers.index("สถานะ") + 1
                else:
                    return False
            
            # Update (Single API Call)
            self.sheet.update_cell(row_idx, self.status_col, status)
            return True
        except Exception as e:
            print(f"Error updating status: {e}")
            return False
