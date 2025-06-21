"""
Configuration management for u-blox GPS RTK add-in.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, List

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
            "constellation_gps": True,
            "constellation_glonass": True,
            "constellation_galileo": True,
            "constellation_beidou": True,
            "constellation_qzss": False,
            "constellation_sbas": False,
            "ntrip_enabled": False,
            "ntrip_host": "",
            "ntrip_port": 2101,
            "ntrip_mountpoint": "",
            "ntrip_username": "",
            "ntrip_password": "",
            "homeassistant_url": "http://supervisor/core",
            # ZED-F9R specific options
            "device_type": "ZED-F9P",  # ZED-F9P or ZED-F9R
            "dead_reckoning_enabled": False,
            "dynamic_model_type": "automotive",  # portable, stationary, pedestrian, automotive, sea, airborne_1g, airborne_2g, airborne_4g, wrist
            "sensor_fusion_enabled": False,
            "high_rate_positioning": False,
            "hnr_rate_hz": 10,  # High rate navigation for ZED-F9R (up to 30Hz)
            "disable_nmea_output": True,
            "enable_esf_ins": False,  # Enable inertial sensor fusion data
            "enable_nav_cov": False,  # Enable covariance matrices
            # RTCM filtering and validation options
            "rtcm_filtering_enabled": True,
            "rtcm_message_filter": [1005, 1077, 1087, 1097, 1127],  # Supported message types
            "rtcm_validation_enabled": True,
            "rtcm_max_message_age_seconds": 30,
            "rtcm_statistics_enabled": True,
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
    def constellation(self) -> List[str]:
        """Get constellation list from boolean fields, with backward compatibility for old list format."""
        # Check if old list format exists for backward compatibility
        old_constellation = self.get("constellation", None)
        if old_constellation is not None:
            # Handle backward compatibility with old string and list formats
            if isinstance(old_constellation, str):
                return [const.strip() for const in old_constellation.split('+')]
            elif isinstance(old_constellation, list):
                return old_constellation
        
        # Use new boolean field format
        enabled_constellations = []
        constellation_map = {
            "constellation_gps": "GPS",
            "constellation_glonass": "GLONASS", 
            "constellation_galileo": "GALILEO",
            "constellation_beidou": "BEIDOU",
            "constellation_qzss": "QZSS",
            "constellation_sbas": "SBAS"
        }
        
        for config_key, constellation_name in constellation_map.items():
            if self.get(config_key, False):
                enabled_constellations.append(constellation_name)
        
        # Fallback to default if no constellations enabled
        if not enabled_constellations:
            return ["GPS", "GLONASS", "GALILEO", "BEIDOU"]
        
        return enabled_constellations
    
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
        return os.environ.get("SUPERVISOR_TOKEN")

    @property
    def device_type(self) -> str:
        return self.get("device_type", "ZED-F9P")

    @property
    def dead_reckoning_enabled(self) -> bool:
        return self.get("dead_reckoning_enabled", False)

    @property
    def dynamic_model_type(self) -> str:
        return self.get("dynamic_model_type", "automotive")

    @property
    def sensor_fusion_enabled(self) -> bool:
        return self.get("sensor_fusion_enabled", False)

    @property
    def high_rate_positioning(self) -> bool:
        return self.get("high_rate_positioning", False)

    @property
    def hnr_rate_hz(self) -> int:
        return self.get("hnr_rate_hz", 10)

    @property
    def disable_nmea_output(self) -> bool:
        return self.get("disable_nmea_output", True)

    @property
    def enable_esf_ins(self) -> bool:
        return self.get("enable_esf_ins", False)

    @property
    def enable_nav_cov(self) -> bool:
        return self.get("enable_nav_cov", False)

    @property
    def rtcm_filtering_enabled(self) -> bool:
        return self.get("rtcm_filtering_enabled", True)

    @property
    def rtcm_message_filter(self) -> list:
        return self.get("rtcm_message_filter", [1005, 1077, 1087, 1097, 1127])

    @property
    def rtcm_validation_enabled(self) -> bool:
        return self.get("rtcm_validation_enabled", True)

    @property
    def rtcm_max_message_age_seconds(self) -> int:
        return self.get("rtcm_max_message_age_seconds", 30)

    @property
    def rtcm_statistics_enabled(self) -> bool:
        return self.get("rtcm_statistics_enabled", True)
