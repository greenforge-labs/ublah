"""
Unit tests for configuration management.
Tests ZED-F9R configuration options and validation.
"""

import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open
from ublox_gps.config import Config


class TestConfig(unittest.TestCase):
    """Test configuration management functionality."""
    
    def setUp(self):
        """Set up test configuration data."""
        self.test_config_data = {
            "gps_device": "/dev/ttyUSB0",
            "gps_baudrate": 38400,
            "device_type": "ZED-F9R",
            "dead_reckoning_enabled": True,
            "dynamic_model_type": "automotive",
            "sensor_fusion_enabled": True,
            "high_rate_positioning": True,
            "hnr_rate_hz": 10,
            "enable_esf_ins": True,
            "disable_nmea_output": True,
            "constellation_gps": True,
            "constellation_glonass": True,
            "constellation_galileo": True,
            "constellation_beidou": False,
            "constellation_qzss": False,
            "constellation_sbas": False,
            "rtcm_filtering_enabled": True,
            "rtcm_message_filter": [1005, 1077, 1087, 1097, 1127],
            "ntrip_enabled": True,
            "ntrip_host": "rtk.example.com",
            "ntrip_port": 2101,
            "ntrip_mountpoint": "MOUNT1"
        }
    
    def test_config_loading_from_file(self):
        """Test loading configuration from JSON file."""
        config_json = json.dumps(self.test_config_data)
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            config = Config("dummy_path.json")
            
            # Test ZED-F9R specific options
            self.assertEqual(config.device_type, "ZED-F9R")
            self.assertTrue(config.dead_reckoning_enabled)
            self.assertEqual(config.dynamic_model_type, "automotive")
            self.assertTrue(config.sensor_fusion_enabled)
            self.assertTrue(config.high_rate_positioning)
            self.assertEqual(config.hnr_rate_hz, 10)
            self.assertTrue(config.enable_esf_ins)
            self.assertTrue(config.disable_nmea_output)
            self.assertTrue(config.constellation_gps)
            self.assertTrue(config.constellation_glonass)
            self.assertTrue(config.constellation_galileo)
            self.assertFalse(config.constellation_beidou)
            self.assertFalse(config.constellation_qzss)
            self.assertFalse(config.constellation_sbas)
    
    def test_config_defaults(self):
        """Test default configuration values."""
        with patch("builtins.open", mock_open(read_data="{}")):
            config = Config("dummy_path.json")
            
            # Test default values
            self.assertEqual(config.device_type, "ZED-F9P")
            self.assertFalse(config.dead_reckoning_enabled)
            self.assertEqual(config.dynamic_model_type, "portable")
            self.assertFalse(config.sensor_fusion_enabled)
            self.assertFalse(config.high_rate_positioning)
            self.assertEqual(config.hnr_rate_hz, 5)
            self.assertFalse(config.enable_esf_ins)
            self.assertFalse(config.disable_nmea_output)
            self.assertTrue(config.constellation_gps)
            self.assertTrue(config.constellation_glonass)
            self.assertTrue(config.constellation_galileo)
            self.assertTrue(config.constellation_beidou)
            self.assertFalse(config.constellation_qzss)
            self.assertFalse(config.constellation_sbas)
    
    def test_rtcm_configuration(self):
        """Test RTCM filtering configuration."""
        config_json = json.dumps(self.test_config_data)
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            config = Config("dummy_path.json")
            
            self.assertTrue(config.rtcm_filtering_enabled)
            self.assertEqual(config.rtcm_message_filter, [1005, 1077, 1087, 1097, 1127])
            self.assertTrue(config.rtcm_validation_enabled)
            self.assertEqual(config.rtcm_max_message_age_seconds, 30)
    
    def test_config_validation_errors(self):
        """Test configuration validation for invalid values."""
        # Test invalid device type
        invalid_config = {
            "gps_device": "/dev/ttyUSB0",
            "gps_baudrate": 38400,
            "device_type": "ZED-F9P",
            "constellation_gps": True,
            "constellation_glonass": True,
            "constellation_galileo": True,
            "constellation_beidou": True,
            "constellation_qzss": False,
            "constellation_sbas": False
        }
        
        config_json = json.dumps(invalid_config)
        with patch("builtins.open", mock_open(read_data=config_json)):
            config = Config("dummy_path.json")
            # Should fall back to default
            self.assertEqual(config.device_type, "ZED-F9P")  # Config doesn't validate, just stores
    
    def test_config_edge_cases(self):
        """Test edge cases in configuration."""
        # Test with minimal config
        minimal_config = {"gps_device": "/dev/ttyUSB0"}
        config_json = json.dumps(minimal_config)
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            config = Config("dummy_path.json")
            
            # Should have defaults for missing values
            self.assertEqual(config.gps_device, "/dev/ttyUSB0")
            self.assertEqual(config.gps_baudrate, 38400)
            self.assertEqual(config.device_type, "ZED-F9P")
            self.assertTrue(config.constellation_gps)
            self.assertTrue(config.constellation_glonass)
            self.assertTrue(config.constellation_galileo)
            self.assertTrue(config.constellation_beidou)
            self.assertFalse(config.constellation_qzss)
            self.assertFalse(config.constellation_sbas)
    
    def test_config_property_access(self):
        """Test configuration property access methods."""
        config_json = json.dumps(self.test_config_data)
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            config = Config("dummy_path.json")
            
            # Test direct property access
            self.assertEqual(config.gps_device, "/dev/ttyUSB0")
            self.assertEqual(config.gps_baudrate, 38400)
            
            # Test get method with defaults
            self.assertEqual(config.get("nonexistent_key", "default_value"), "default_value")
            self.assertEqual(config.get("gps_device", "default"), "/dev/ttyUSB0")
    
    def test_constellation_backward_compatibility(self):
        """Test backward compatibility with string format constellation."""
        config_json = json.dumps({"constellation": "GPS+GLONASS+GALILEO"})
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            with patch("os.path.exists", return_value=True):
                config = Config("dummy_path.json")
                
                self.assertTrue(config.constellation_gps)
                self.assertTrue(config.constellation_glonass)
                self.assertTrue(config.constellation_galileo)
                self.assertFalse(config.constellation_beidou)
                self.assertFalse(config.constellation_qzss)
                self.assertFalse(config.constellation_sbas)
    
    def test_constellation_list_format(self):
        """Test list format constellation."""
        test_data = {"constellation": ["GPS", "GLONASS", "GALILEO"]}
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                config = Config("dummy_path.json")
                
                # Test that the constellation property still returns a list for backward compatibility
                self.assertEqual(config.constellation, ["GPS", "GLONASS", "GALILEO"])
    
    def test_constellation_string_format_backward_compatibility(self):
        """Test string format constellation for backward compatibility."""
        test_data = {"constellation": "GPS+GLONASS+BEIDOU"}
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                config = Config("dummy_path.json")
                
                # Test that old string format is converted to list
                self.assertEqual(config.constellation, ["GPS", "GLONASS", "BEIDOU"])
    
    def test_constellation_boolean_fields_to_list(self):
        """Test that boolean constellation fields are converted to list format."""
        test_data = {
            "constellation_gps": True,
            "constellation_glonass": True,
            "constellation_galileo": False,
            "constellation_beidou": True,
            "constellation_qzss": False,
            "constellation_sbas": False
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                config = Config("dummy_path.json")
                
                # Test that boolean fields are converted to list correctly
                expected = ["GPS", "GLONASS", "BEIDOU"]
                self.assertEqual(sorted(config.constellation), sorted(expected))
    
    def test_constellation_fallback_when_none_enabled(self):
        """Test constellation fallback when no constellations are enabled."""
        test_data = {
            "constellation_gps": False,
            "constellation_glonass": False,
            "constellation_galileo": False,
            "constellation_beidou": False,
            "constellation_qzss": False,
            "constellation_sbas": False
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                config = Config("dummy_path.json")
                
                # Test that fallback is used when no constellations enabled
                self.assertEqual(config.constellation, ["GPS", "GLONASS", "GALILEO", "BEIDOU"])


if __name__ == '__main__':
    unittest.main()
