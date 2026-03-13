import gspread
import socket

import requests.packages.urllib3.util.connection as urllib3_cn

# Removed monkey patch

class SheetService:
    def __init__(self, credentials_source, sheet_id, sheet_name=None):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        self.client = None
        self.sheet = None
        self.sheet_id = sheet_id
        self.row_index_map = {} # Cache for Order ID -> Row Number
        self.status_col = None  # Cache for Status Column Index
        self.all_data_cache = None
        self.all_rows_raw = None # Raw list of lists
        self.last_fetch_time = 0
        try:
            # We now exclusively expect Credentials from User Authentication
            self.creds = credentials_source
            self.client = gspread.authorize(self.creds)

            
            if sheet_name:
                try:
                    self.spreadsheet = self.client.open_by_key(sheet_id)
                    self.sheet = self.spreadsheet.worksheet(sheet_name)
                    print(f"DEBUG: Connected to Sheet (Tab): '{self.sheet.title}'")
                except gspread.exceptions.WorksheetNotFound:
                    print(f"Warning: Worksheet '{sheet_name}' not found. Falling back to default.")
                    self.spreadsheet = self.client.open_by_key(sheet_id)
                    self.sheet = self.spreadsheet.sheet1
            else:
                self.spreadsheet = self.client.open_by_key(sheet_id)
                self.sheet = self.spreadsheet.sheet1 # Default to first sheet
            
            print(f"DEBUG: Active Sheet Title: '{self.sheet.title}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Warning: SheetService init failed: {e}")
            self.sheet = None

    def get_worksheets(self):
        """Returns a list of all visible worksheet titles."""
        if not self.client or not self.spreadsheet: return []
        try:
            # Filter worksheets where hidden is False
            return [ws.title for ws in self.spreadsheet.worksheets() if not ws.hidden]
        except Exception as e:
            print(f"Error getting worksheets: {e}")
            return []

    def set_worksheet(self, sheet_name):
        """Switches the active worksheet and clears cache."""
        if not self.client or not self.sheet_id: return False
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            self.sheet = spreadsheet.worksheet(sheet_name)
            
            # Clear cache for the new worksheet
            self.all_rows_raw = None
            self.all_data_cache = None
            self.row_index_map = {}
            self.last_fetch_time = 0
            
            print(f"DEBUG: Switched to Sheet: '{self.sheet.title}' and cleared cache")
            return True
        except Exception as e:
            print(f"Error switching worksheet: {e}")
            return False

    def _ensure_data_loaded(self, force=False):
        """Ensures that sheet data is loaded into memory. Returns raw rows."""
        import time
        now = time.time()
        # Cache for 30 seconds to stay fresh but reduce calls
        if not force and self.all_rows_raw and (now - self.last_fetch_time < 30):
            return self.all_rows_raw

        if not self.sheet: return []
        
        try:
            print(f"DEBUG: Fetching all values from Sheet '{self.sheet.title}' for optimization...")
            rows = self.sheet.get_all_values()
            if not rows:
                self.all_rows_raw = []
                self.all_data_cache = []
                self.row_index_map = {}
                return []

            self.all_rows_raw = rows
            self.last_fetch_time = now
            
            # Re-process cache and index map
            headers = rows[0]
            data_rows = rows[1:]
            
            clean_headers = []
            header_counts = {}
            for i, h in enumerate(headers):
                h = str(h).strip()
                if not h: h = f"unnamed_{i}"
                if h in header_counts:
                    header_counts[h] += 1
                    clean_headers.append(f"{h}_{header_counts[h]}")
                else:
                    header_counts[h] = 0
                    clean_headers.append(h)
            
            records = []
            self.row_index_map = {}
            for i, row in enumerate(data_rows):
                row_extended = row + [""] * (len(clean_headers) - len(row))
                record = dict(zip(clean_headers, row_extended))
                records.append(record)
                
                # Column L (Order ID) is index 11
                order_id = str(record.get('Order ID') or record.get('order_id') or record.get('เลขออเดอร์') or "")
                if order_id:
                    self.row_index_map[order_id] = i + 2
            
            self.all_data_cache = records
            return self.all_rows_raw
        except Exception as e:
            print(f"Error in _ensure_data_loaded: {e}")
            return self.all_rows_raw or []

    def check_duplicate(self, order_id):
        """Checks if order_id already exists using local map."""
        if not order_id: return False
        self._ensure_data_loaded()
        return str(order_id) in self.row_index_map

    def get_all_data(self):
        """Returns the dictionary-style records from memory cache."""
        self._ensure_data_loaded()
        return self.all_data_cache or []

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
        """Calculates next Run No. from memory cache."""
        self._ensure_data_loaded()
        run_nos_set = set()
        for r in (self.all_data_cache or []):
            val = r.get('Run No') or r.get('run_no') or r.get('ลำดับ') or r.get('Run No.')
            if val and str(val).isdigit():
                run_nos_set.add(int(val))
        
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

        # OPTIMIZED: Use cached all_rows_raw to find gap
        target_row_idx = None
        all_rows = self._ensure_data_loaded()
        for i in range(1, len(all_rows)):
            row_data = all_rows[i]
            if len(row_data) < 4 or not str(row_data[3]).strip():
                target_row_idx = i + 1
                break

        # IMPORTANT: Use value_input_option='USER_ENTERED' to parse formulas
        try:
            if target_row_idx:
                # Update existing empty row
                # Range A[idx]:O[idx]
                range_label = f"A{target_row_idx}:O{target_row_idx}"
                self.sheet.update(range_name=range_label, values=[row], value_input_option='USER_ENTERED')
                print(f"DEBUG: Data updated in gap at row {target_row_idx}")
            else:
                # Append to bottom if no gap found
                result = self.sheet.append_row(row, value_input_option='USER_ENTERED')
                print(f"DEBUG: Data appended to bottom: {result}")
            return True
        except Exception as e:
            print(f"Error saving data to sheet: {e}")
            return False

    def find_row_by_order_id(self, order_id):
        """
        Returns (row_index, current_row_data) for a given order_id.
        row_index is 1-indexed for gspread.
        """
        if not self.sheet or not order_id: return None, None
        
        order_id_str = str(order_id)
        # Ensure cache is populated
        if not self.row_index_map:
            self.get_all_data()
            
        row_idx = self.row_index_map.get(order_id_str)
        if not row_idx: return None, None

        try:
            row_data = self.all_rows_raw[row_idx - 1]
            return row_idx, row_data
        except Exception as e:
            print(f"Error fetching existing row from cache: {e}")
            return row_idx, None

    def update_existing_data(self, row_idx, data_dict, run_no):
        """
        Updates specific columns in an existing row.
        Targeting: A (Image), B (Receiver), C (Location), F (Platform), G (Date), 
                  H (Shop), I (Price), J (Coins), K (Item), M (Tracking).
        """
        if not self.sheet or not row_idx: return False

        def fmt_float(val):
            try:
                if isinstance(val, str): val = val.replace(',', '')
                if val == '-' or val == '': return "0.00"
                return "{:,.2f}".format(float(val))
            except:
                return str(val)

        try:
            # Fetch current row from cache
            current_row = self.all_rows_raw[row_idx - 1]
            # Ensure it's at least 15 columns
            row = current_row + [""] * (15 - len(current_row))

            # A: Image Link
            link = data_dict.get('image_link', '')
            label = f"Check Order {run_no}" if run_no else "Check Order"
            row[0] = f'=HYPERLINK("{link}", "{label}")' if link else row[0]

            # B, C
            row[1] = data_dict.get('receiver_name', row[1])
            row[2] = data_dict.get('location', row[2])

            # D (Run No): Should NOT change usually, but we ensure it's set if missing
            if not row[3]: row[3] = run_no if run_no else ""

            # F-K
            row[5] = data_dict.get('platform', row[5])
            row[6] = data_dict.get('date', row[6])
            row[7] = data_dict.get('shop_name', row[7])
            row[8] = fmt_float(data_dict.get('price', row[8]))
            row[9] = fmt_float(data_dict.get('coins', row[9]))
            row[10] = data_dict.get('item_name', row[10])

            # M (Tracking)
            new_tracking = data_dict.get('tracking_number')
            if new_tracking:
                row[12] = str(new_tracking)

            # O: Reset Status to Pending for re-verification
            row[14] = "Pending"

            # Update Range A-O
            range_label = f"A{row_idx}:O{row_idx}"
            self.sheet.update(range_name=range_label, values=[row], value_input_option='USER_ENTERED')
            print(f"DEBUG: Successfully updated row {row_idx} for order {data_dict.get('order_id')}")
            return True
        except Exception as e:
            print(f"Error updating existing data: {e}")
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
