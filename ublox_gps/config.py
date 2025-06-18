"""
Configuration management for u-blox GPS RTK add-in.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for the GPS RTK add-in."""
    
    def __init__(self, config_path: str = "/data/options.json"):
        self.config_path = config_path
        self._config = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from HomeAssistant add-in options."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    import json
                    self._config = json.load(f)
                    logger.info(f"Loaded configuration from {self.config_path}")
            else:
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                self._load_defaults()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._load_defaults()
    
    def _load_defaults(self) -> None:
        """Load default configuration values."""
        self._config = {
            "gps_device": "/dev/ttyUSB0",
            "gps_baudrate": 38400,
            "update_rate_hz": 1,
            "constellation": "GPS+GLONASS+GALILEO+BEIDOU",
            "ntrip_enabled": False,
            "ntrip_host": "",
            "ntrip_port": 2101,
            "ntrip_mountpoint": "",
            "ntrip_username": "",
            "ntrip_password": "",
            "homeassistant_url": "http://supervisor/core",
            "homeassistant_token": ""
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    @property
    def gps_device(self) -> str:
        return self.get("gps_device", "/dev/ttyUSB0")
    
    @property
    def gps_baudrate(self) -> int:
        return self.get("gps_baudrate", 38400)
    
    @property
    def update_rate_hz(self) -> int:
        return self.get("update_rate_hz", 1)
    
    @property
    def constellation(self) -> str:
        return self.get("constellation", "GPS+GLONASS+GALILEO+BEIDOU")
    
    @property
    def ntrip_enabled(self) -> bool:
        return self.get("ntrip_enabled", False)
    
    @property
    def ntrip_host(self) -> str:
        return self.get("ntrip_host", "")
    
    @property
    def ntrip_port(self) -> int:
        return self.get("ntrip_port", 2101)
    
    @property
    def ntrip_mountpoint(self) -> str:
        return self.get("ntrip_mountpoint", "")
    
    @property
    def ntrip_username(self) -> str:
        return self.get("ntrip_username", "")
    
    @property
    def ntrip_password(self) -> str:
        return self.get("ntrip_password", "")
    
    @property
    def homeassistant_url(self) -> str:
        return self.get("homeassistant_url", "http://supervisor/core")
    
    @property
    def homeassistant_token(self) -> str:
        return self.get("homeassistant_token", "")
