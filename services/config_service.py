import json
import os

class ConfigService:
    def __init__(self, config_file='config.json'):
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', config_file))
        self.default_config = {
            "GOOGLE_DRIVE_FOLDER_ID": os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
            "ACTIVE_SHEET_NAME": os.getenv("GOOGLE_SHEET_NAME", "Sheet1"),
            "AI_PROVIDER": "openai",
            "SHEET_FOLDER_MAP": {}
        }
        self._cached_config = None
        self.config = self._load_config()

    def _load_config(self, force_reload=False):
        # Return cache if available and not explicitly clearing
        if not force_reload and self._cached_config is not None:
            return self._cached_config

        if not os.path.exists(self.config_path):
            self._save_config(self.default_config)
            self._cached_config = self.default_config
            return self.default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "SHEET_FOLDER_MAP" not in data:
                    data["SHEET_FOLDER_MAP"] = {}
                self._cached_config = data
                return data
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config

    def _save_config(self, config_data):
        self._cached_config = config_data # Update cache
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        # Reload from disk every time to ensure fresh values across workers/threads
        self.config = self._load_config(force_reload=True)
        return self.config.get(key, default)

    def set(self, key, value):
        self.config = self._load_config(force_reload=True) # Sync before writing
        self.config[key] = value
        self._save_config(self.config)
        return True

    def get_folder_for_sheet(self, sheet_name):
        """Returns the specific folder ID for a sheet, or the default fallback."""
        if not sheet_name:
            sheet_name = self.get('ACTIVE_SHEET_NAME', os.getenv("GOOGLE_SHEET_NAME"))
            
        self.config = self._load_config(force_reload=True)
        folder_map = self.config.get("SHEET_FOLDER_MAP", {})
        
        # If specific mapping exists and is not empty
        if sheet_name in folder_map and folder_map[sheet_name]:
            return folder_map[sheet_name]
            
        # Fallback to global config (which might be the last used folder ID)
        return self.get("GOOGLE_DRIVE_FOLDER_ID", os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""))

    def set_folder_for_sheet(self, sheet_name, folder_id):
        """Sets the folder ID for a specific sheet and syncs with global if active."""
        self.config = self._load_config()
        if "SHEET_FOLDER_MAP" not in self.config:
            self.config["SHEET_FOLDER_MAP"] = {}
            
        self.config["SHEET_FOLDER_MAP"][sheet_name] = folder_id
        
        # If this is the active sheet, also sync the global default
        if self.config.get('ACTIVE_SHEET_NAME') == sheet_name:
            self.config["GOOGLE_DRIVE_FOLDER_ID"] = folder_id
            
        self._save_config(self.config)
        return True

    # ─── Google Sheets Persistence ───────────────────────────────────────────────
    CONFIG_SHEET_NAME = "_GravityConfig"

    def sync_from_gsheets(self, gspread_client, sheet_id):
        """
        โหลด SHEET_FOLDER_MAP จาก worksheet _GravityConfig ใน Google Sheets
        เรียกตอน startup เพื่อดึงค่าล่าสุดมา override local config
        """
        try:
            spreadsheet = gspread_client.open_by_key(sheet_id)
            try:
                ws = spreadsheet.worksheet(self.CONFIG_SHEET_NAME)
            except Exception:
                print(f"DEBUG: No {self.CONFIG_SHEET_NAME} worksheet found, skipping sync.")
                return False

            rows = ws.get_all_values()  # [[Key, Value], ...]
            if not rows:
                return False

            self.config = self._load_config(force_reload=True)
            if "SHEET_FOLDER_MAP" not in self.config:
                self.config["SHEET_FOLDER_MAP"] = {}

            updated = False
            for row in rows:
                if len(row) >= 2 and row[0].startswith("SHEET_FOLDER_MAP_"):
                    sheet_name = row[0][len("SHEET_FOLDER_MAP_"):]
                    folder_id = row[1].strip()
                    if sheet_name and folder_id:
                        self.config["SHEET_FOLDER_MAP"][sheet_name] = folder_id
                        updated = True

            if updated:
                self._save_config(self.config)
                print(f"DEBUG: Config synced from GSheets ({len(self.config['SHEET_FOLDER_MAP'])} mappings)")
            return True
        except Exception as e:
            print(f"DEBUG: sync_from_gsheets failed: {e}")
            return False

    def sync_to_gsheets(self, gspread_client, sheet_id):
        """
        เขียน SHEET_FOLDER_MAP ลง worksheet _GravityConfig ใน Google Sheets
        เรียกหลังจาก set_folder_for_sheet เพื่อให้ค่าคงอยู่ข้าม Deploy
        """
        try:
            spreadsheet = gspread_client.open_by_key(sheet_id)

            # หา worksheet หรือสร้างใหม่ถ้ายังไม่มี
            try:
                ws = spreadsheet.worksheet(self.CONFIG_SHEET_NAME)
            except Exception:
                ws = spreadsheet.add_worksheet(title=self.CONFIG_SHEET_NAME, rows=50, cols=2)
                print(f"DEBUG: Created new worksheet: {self.CONFIG_SHEET_NAME}")

            self.config = self._load_config(force_reload=True)
            folder_map = self.config.get("SHEET_FOLDER_MAP", {})

            # สร้าง rows [["Key", "Value"], ...]
            rows = [["Key", "Value"]]
            for sname, fid in folder_map.items():
                rows.append([f"SHEET_FOLDER_MAP_{sname}", fid])

            ws.clear()
            ws.update(range_name="A1", values=rows)
            print(f"DEBUG: Config synced to GSheets ({len(folder_map)} mappings)")
            return True
        except Exception as e:
            print(f"DEBUG: sync_to_gsheets failed: {e}")
            return False
