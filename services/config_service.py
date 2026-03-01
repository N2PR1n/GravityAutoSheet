import json
import os

class ConfigService:
    def __init__(self, config_file='config.json'):
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', config_file))
        self.default_config = {
            "GOOGLE_DRIVE_FOLDER_ID": os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
            "ACTIVE_SHEET_NAME": os.getenv("GOOGLE_SHEET_NAME", "Sheet1"),
            "SHEET_FOLDER_MAP": {}
        }
        self._cached_config = None
        self.config = self._load_config()

    def _load_config(self):
        # Return cache if available and not explicitly clearing
        if self._cached_config is not None:
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
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        # Use cached config instead of reloading from disk every time
        return self.config.get(key, default)

    def set(self, key, value):
        self.config = self._load_config() # Sync before writing
        self.config[key] = value
        self._save_config(self.config)
        return True

    def get_folder_for_sheet(self, sheet_name):
        """Returns the specific folder ID for a sheet, or the default fallback."""
        self.config = self._load_config()
        folder_map = self.config.get("SHEET_FOLDER_MAP", {})
        
        # If specific mapping exists and is not empty
        if sheet_name in folder_map and folder_map[sheet_name]:
            return folder_map[sheet_name]
            
        # Fallback to global config
        return self.get("GOOGLE_DRIVE_FOLDER_ID", os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""))

    def set_folder_for_sheet(self, sheet_name, folder_id):
        """Sets the folder ID for a specific sheet and syncs with global if active."""
        self.config = self._load_config()
        if "SHEET_FOLDER_MAP" not in self.config:
            self.config["SHEET_FOLDER_MAP"] = {}
            
        self.config["SHEET_FOLDER_MAP"][sheet_name] = folder_id
        
        # If this is the active sheet, also sync the global default
        # to ensure the UI (Settings Modal) stays consistent.
        if self.config.get('ACTIVE_SHEET_NAME') == sheet_name:
            self.config["GOOGLE_DRIVE_FOLDER_ID"] = folder_id
            
        self._save_config(self.config)
        return True
