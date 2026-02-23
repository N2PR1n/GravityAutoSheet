import json
import os

class ConfigService:
    def __init__(self, config_file='config.json'):
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', config_file))
        self.default_config = {
            "GOOGLE_DRIVE_FOLDER_ID": os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
            "ACTIVE_SHEET_NAME": os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
        }
        self.config = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            self._save_config(self.default_config)
            return self.default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config

    def _save_config(self, config_data):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._save_config(self.config)
        return True
