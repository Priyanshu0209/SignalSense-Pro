import os
import json
import time
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional

CONFIG_DIR = Path.home() / ".signalsense"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FILE = CONFIG_DIR / ".key"

class ConfigManager:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._key = self._load_or_create_key()
        self._fernet = Fernet(self._key)

    def _load_or_create_key(self) -> bytes:
        if KEY_FILE.exists():
            return KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
            return key

    def load_config(self) -> dict:
        if not CONFIG_FILE.exists():
            return {}
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                
            # Decrypt password if it exists
            if "encrypted_password" in config:
                try:
                    encrypted_pwd = config["encrypted_password"].encode()
                    config["password"] = self._fernet.decrypt(encrypted_pwd).decode()
                except Exception:
                    config["password"] = ""
            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def save_config(self, router_ip: str, username: str, password: str, adapter_type: str = "SSH", router_brand: str = "Unknown", mac_address: str = "", connection_status: str = "Disconnected", last_connected: str = "") -> bool:
        encrypted_pwd = self._fernet.encrypt(password.encode()).decode() if password else ""
        
        # Merge with existing to keep other fields if any
        config = self.load_config()
        
        config.update({
            "router_ip": router_ip,
            "username": username,
            "encrypted_password": encrypted_pwd,
            "adapter_type": adapter_type,
            "router_brand": router_brand,
            "mac_address": mac_address,
            "connection_status": connection_status,
            "last_connected": last_connected,
            "configured": True
        })
        
        # Remove plaintext password from dictionary before saving
        if "password" in config:
            del config["password"]
            
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def edit_config(self, **kwargs) -> bool:
        """Update specific fields in the config."""
        config = self.load_config()
        if not config:
            return False
            
        if "password" in kwargs:
            pwd = kwargs.pop("password")
            if pwd:
                kwargs["encrypted_password"] = self._fernet.encrypt(pwd.encode()).decode()

        config.update(kwargs)
        
        if "password" in config:
            del config["password"]
            
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error editing config: {e}")
            return False

    def forget_config(self) -> bool:
        """Clear all configuration and delete the config file."""
        try:
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            return True
        except Exception as e:
            print(f"Error forgetting config: {e}")
            return False

    def is_configured(self) -> bool:
        config = self.load_config()
        return config.get("configured", False)

    def get_connection_info(self) -> Dict[str, Any]:
        """Returns non-sensitive connection info for UI display."""
        config = self.load_config()
        return {
            "router_ip": config.get("router_ip", ""),
            "router_brand": config.get("router_brand", "Unknown"),
            "adapter_type": config.get("adapter_type", ""),
            "mac_address": config.get("mac_address", ""),
            "connection_status": config.get("connection_status", "Disconnected"),
            "last_connected": config.get("last_connected", "")
        }

config_manager = ConfigManager()
