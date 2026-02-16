import gspread
from google.oauth2 import service_account

class SheetService:
    def __init__(self, credentials_path, sheet_id):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        try:
            self.creds = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=self.scopes)
            self.client = gspread.authorize(self.creds)
            self.sheet = self.client.open_by_key(sheet_id).sheet1 # Default to first sheet
            # self.sheet = self.client.open_by_key(sheet_id).worksheet("TestDogBot")
            print(f"DEBUG: Connected to Sheet '{self.sheet.title}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Warning: SheetService init failed: {e}")
            self.sheet = None

    def check_duplicate(self, order_id):
        """Checks if order_id already exists in Column L (Index 12)."""
        if not self.sheet or not order_id: return False
        try:
            # Get all values in Column L (Order IDs)
            # Row 1 is header, data starts from Row 2
            order_ids = self.sheet.col_values(12)  # Column L = 12
            return str(order_id) in order_ids
        except Exception as e:
            print(f"Warning: Duplicate check failed: {e}")
            return False

    def get_all_data(self):
        """Fetches all records from the sheet."""
        if not self.sheet: return []
        try:
            return self.sheet.get_all_records()
        except Exception as e:
            print(f"Error fetching data: {e}")
            return []

    def get_next_run_no(self):
        """Calculates the next Run No. based on Column D (index 4)."""
        if not self.sheet: return 1
        try:
            # Column D is index 4
            col_values = self.sheet.col_values(4) 
            run_nos = []
            for val in col_values:
                # Filter for numeric values (skip header/text)
                if str(val).isdigit():
                    run_nos.append(int(val))
            
            if not run_nos: return 1
            return max(run_nos) + 1
        except Exception as e:
            print(f"Error getting next run no: {e}")
            return 1

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
            return

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

        # Prepare row data (14 columns A-N)
        row = [""] * 14
        
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

        # IMPORTANT: Use value_input_option='USER_ENTERED' to parse formulas
        result = self.sheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"DEBUG: Data appended result: {result}")
        print(f"DEBUG: Check row number: {result.get('updates', {}).get('updatedRange', 'Unknown')}")
