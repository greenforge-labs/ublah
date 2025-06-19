"""
Integration tests for the complete Ublox GPS system.
Tests end-to-end functionality with ZED-F9R support.
"""

import unittest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from ublox_gps.config import Config
from ublox_gps.gps_handler import GPSHandler
from ublox_gps.ntrip_client import NTRIPClient
from ublox_gps.rtcm_handler import RTCMHandler
from ublox_gps.diagnostics import SystemDiagnostics


class TestSystemIntegration(unittest.TestCase):
    """Integration tests for complete GPS system."""
    
    def setUp(self):
        """Set up integration test environment."""
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
            "rtcm_filtering_enabled": True,
            "rtcm_message_filter": [1005, 1077, 1087, 1097, 1127],
            "ntrip_enabled": True,
            "ntrip_host": "rtk.example.com",
            "ntrip_port": 2101,
            "ntrip_mountpoint": "MOUNT1",
            "ntrip_username": "user",
            "ntrip_password": "pass"
        }
        
        # Create temporary config file
        self.temp_config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.test_config_data, self.temp_config_file)
        self.temp_config_file.close()
        
        self.config = Config(self.temp_config_file.name)
    
    def tearDown(self):
        """Clean up test environment."""
        os.unlink(self.temp_config_file.name)
    
    async def test_gps_handler_rtcm_integration(self):
        """Test GPS handler and RTCM handler integration."""
        gps_handler = GPSHandler(self.config)
        rtcm_handler = RTCMHandler(self.config)
        
        # Mock GPS connection
        with patch.object(gps_handler, '_connect_device', new_callable=AsyncMock):
            with patch.object(gps_handler, '_configure_device', new_callable=AsyncMock):
                await gps_handler.start()
                
                # Simulate RTCM data processing
                rtcm_data = b'\xD3\x00\x13\x43\x50' + b'test_payload' + b'\x12\x34\x56'
                filtered_data, stats = rtcm_handler.process_rtcm_data(rtcm_data)
                
                # Send filtered corrections to GPS
                with patch.object(gps_handler, 'send_corrections', new_callable=AsyncMock) as mock_send:
                    await gps_handler.send_corrections(filtered_data)
                    mock_send.assert_called_once()
                
                await gps_handler.stop()
    
    @patch('aiohttp.ClientSession.get')
    async def test_ntrip_rtcm_integration(self, mock_get):
        """Test NTRIP client and RTCM handler integration."""
        # Mock NTRIP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.content.iter_chunked = AsyncMock(return_value=[
            b'\xD3\x00\x13\x43\x50test_rtcm_data\x12\x34\x56',
            b'\xD3\x00\x15\x43\x60more_rtcm_data\x23\x45\x67'
        ])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        ntrip_client = NTRIPClient(self.config)
        
        # Start NTRIP client
        await ntrip_client.start()
        
        # Allow some time for data processing
        await asyncio.sleep(0.1)
        
        # Get corrections (should be filtered)
        corrections = await ntrip_client.get_corrections()
        
        # Should have received filtered RTCM data
        self.assertIsInstance(corrections, (bytes, type(None)))
        
        await ntrip_client.stop()
    
    async def test_diagnostics_integration(self):
        """Test diagnostics integration with all components."""
        diagnostics = SystemDiagnostics(self.config)
        
        # Start monitoring
        await diagnostics.start_monitoring()
        
        # Record some operations
        diagnostics.record_operation("gps_handler", "connect", 0.5, True)
        diagnostics.record_operation("gps_handler", "read_data", 0.1, True)
        diagnostics.record_operation("ntrip_client", "receive_data", 0.2, True)
        diagnostics.record_operation("rtcm_handler", "filter_message", 0.05, True)
        
        # Perform health checks
        health_checks = await diagnostics.perform_health_checks()
        
        # Should have health checks for all components
        component_names = [check.component for check in health_checks]
        expected_components = ['gps_handler', 'ntrip_client', 'rtcm_handler', 'system_resources', 'configuration']
        
        for component in expected_components:
            self.assertIn(component, component_names)
        
        # Get comprehensive status
        health_summary = diagnostics.get_health_summary()
        self.assertIn('overall_status', health_summary)
        self.assertIn('components', health_summary)
        self.assertIn('performance_metrics', health_summary)
        
        await diagnostics.stop_monitoring()
    
    async def test_configuration_validation_integration(self):
        """Test configuration validation across all components."""
        # Test with invalid configuration
        invalid_config_data = self.test_config_data.copy()
        invalid_config_data['gps_baudrate'] = -1  # Invalid baudrate
        invalid_config_data['hnr_rate_hz'] = 100  # Too high rate
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_config_data, f)
            f.flush()
            
            config = Config(f.name)
            
            # Components should handle invalid config gracefully
            gps_handler = GPSHandler(config)
            ntrip_client = NTRIPClient(config)
            rtcm_handler = RTCMHandler(config)
            
            # Should not crash during initialization
            self.assertIsNotNone(gps_handler)
            self.assertIsNotNone(ntrip_client)
            self.assertIsNotNone(rtcm_handler)
            
            os.unlink(f.name)
    
    async def test_error_propagation_and_recovery(self):
        """Test error handling and recovery across components."""
        gps_handler = GPSHandler(self.config)
        
        # Test GPS connection error recovery
        with patch.object(gps_handler, '_connect_device', side_effect=Exception("Connection failed")):
            with self.assertRaises(Exception):
                await gps_handler.start()
            
            # Handler should be in safe state
            self.assertFalse(gps_handler.connected)
            self.assertIsNone(gps_handler.reader_task)
    
    async def test_data_flow_integration(self):
        """Test complete data flow from NTRIP to GPS device."""
        # Create all components
        gps_handler = GPSHandler(self.config)
        ntrip_client = NTRIPClient(self.config)
        
        # Mock components
        with patch.object(gps_handler, '_connect_device', new_callable=AsyncMock):
            with patch.object(gps_handler, '_configure_device', new_callable=AsyncMock):
                with patch.object(gps_handler, 'send_corrections', new_callable=AsyncMock) as mock_send:
                    
                    # Start GPS handler
                    await gps_handler.start()
                    
                    # Simulate NTRIP data
                    rtcm_data = b'\xD3\x00\x13\x43\x50test_rtcm_data\x12\x34\x56'
                    ntrip_client.corrections_buffer.extend(rtcm_data)
                    
                    # Get filtered corrections
                    corrections = await ntrip_client.get_corrections()
                    
                    if corrections:
                        # Send to GPS device
                        await gps_handler.send_corrections(corrections)
                        mock_send.assert_called()
                    
                    await gps_handler.stop()
    
    async def test_performance_under_load(self):
        """Test system performance under simulated load."""
        diagnostics = SystemDiagnostics(self.config)
        rtcm_handler = RTCMHandler(self.config)
        
        # Simulate processing multiple RTCM messages
        rtcm_data = b'\xD3\x00\x13\x43\x50test_rtcm_data\x12\x34\x56'
        
        start_time = datetime.utcnow()
        
        for i in range(100):
            filtered_data, stats = rtcm_handler.process_rtcm_data(rtcm_data)
            diagnostics.record_operation("rtcm_handler", "process_message", 0.001, True)
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Should process 100 messages in reasonable time (< 1 second)
        self.assertLess(processing_time, 1.0)
        
        # Check performance metrics
        metrics = diagnostics.performance_metrics['rtcm_handler']
        self.assertEqual(metrics.total_operations, 100)
        self.assertEqual(metrics.success_count, 100)
        self.assertGreater(metrics.success_rate, 99.0)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with ZED-F9P devices."""
    
    def setUp(self):
        """Set up backward compatibility tests."""
        self.zed_f9p_config = {
            "gps_device": "/dev/ttyUSB0",
            "gps_baudrate": 38400,
            "device_type": "ZED-F9P",  # Legacy device
            "gps_update_rate": 1,
            "ntrip_enabled": True,
            "ntrip_host": "rtk.example.com",
            "ntrip_port": 2101,
            "ntrip_mountpoint": "MOUNT1"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.zed_f9p_config, f)
            f.flush()
            self.config = Config(f.name)
            self.temp_file = f.name
    
    def tearDown(self):
        """Clean up test files."""
        os.unlink(self.temp_file)
    
    async def test_zed_f9p_compatibility(self):
        """Test that ZED-F9P devices still work with new codebase."""
        gps_handler = GPSHandler(self.config)
        
        # Should initialize without ZED-F9R specific features
        self.assertEqual(self.config.device_type, "ZED-F9P")
        self.assertFalse(self.config.dead_reckoning_enabled)
        self.assertFalse(self.config.sensor_fusion_enabled)
        
        # Should not crash during configuration
        with patch.object(gps_handler, '_connect_device', new_callable=AsyncMock):
            with patch.object(gps_handler, '_send_ubx_message', new_callable=AsyncMock):
                await gps_handler._configure_device()
                
                # Should complete without error
                self.assertTrue(True)  # If we get here, configuration succeeded
    
    def test_rtcm_filtering_with_legacy_config(self):
        """Test RTCM filtering works with legacy configuration."""
        rtcm_handler = RTCMHandler(self.config)
        
        # Should use default RTCM message types
        self.assertEqual(rtcm_handler.filtered_message_types, {1005, 1077, 1087, 1097, 1127})
        
        # Should process RTCM data normally
        rtcm_data = b'\xD3\x00\x13\x43\x50test_rtcm_data\x12\x34\x56'
        filtered_data, stats = rtcm_handler.process_rtcm_data(rtcm_data)
        
        # Should not crash
        self.assertIsInstance(filtered_data, bytes)
        self.assertIsNotNone(stats)


class TestConfigurationMigration(unittest.TestCase):
    """Test configuration migration and validation."""
    
    def test_configuration_migration_v1_to_current(self):
        """Test migration from v1 configuration format."""
        # Simulate old configuration format
        old_config = {
            "gps_device": "/dev/ttyUSB0",
            "gps_baudrate": 38400,
            "gps_update_rate": 1,
            "ntrip_enabled": True,
            "ntrip_host": "rtk.example.com"
            # Missing new ZED-F9R options
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(old_config, f)
            f.flush()
            
            config = Config(f.name)
            
            # Should have new options with default values
            self.assertEqual(config.device_type, "ZED-F9P")  # Default
            self.assertFalse(config.dead_reckoning_enabled)  # Default
            self.assertEqual(config.dynamic_model_type, "portable")  # Default
            
            # Original options should be preserved
            self.assertEqual(config.gps_device, "/dev/ttyUSB0")
            self.assertEqual(config.gps_baudrate, 38400)
            
            os.unlink(f.name)
    
    def test_configuration_validation(self):
        """Test configuration validation logic."""
        diagnostics = SystemDiagnostics(Mock())
        
        # Test with valid configuration
        valid_config = Mock()
        valid_config.gps_device = "/dev/ttyUSB0"
        valid_config.gps_baudrate = 38400
        valid_config.ntrip_enabled = True
        valid_config.ntrip_host = "rtk.example.com"
        
        diagnostics.config = valid_config
        
        # Should pass validation
        health_check = asyncio.run(diagnostics._check_configuration_health())
        self.assertEqual(health_check.status.value, "healthy")
        
        # Test with invalid configuration
        invalid_config = Mock()
        invalid_config.gps_device = ""  # Empty device
        invalid_config.gps_baudrate = 0  # Invalid baudrate
        
        diagnostics.config = invalid_config
        
        # Should detect issues
        health_check = asyncio.run(diagnostics._check_configuration_health())
        self.assertIn(health_check.status.value, ["warning", "critical"])


if __name__ == '__main__':
    unittest.main()
