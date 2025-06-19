"""
Unit tests for GPS handler functionality.
Tests ZED-F9R GPS handler with error handling and diagnostics.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from ublox_gps.gps_handler import GPSHandler, GPSConnectionError, GPSConfigurationError, GPSDataValidationError
from pyubx2 import UBXMessage


class TestGPSHandler(unittest.TestCase):
    """Test GPS handler functionality."""
    
    def setUp(self):
        """Set up test GPS handler."""
        self.mock_config = Mock()
        self.mock_config.gps_device = "/dev/ttyUSB0"
        self.mock_config.gps_baudrate = 38400
        self.mock_config.device_type = "ZED-F9R"
        self.mock_config.dead_reckoning_enabled = True
        self.mock_config.dynamic_model_type = "automotive"
        self.mock_config.sensor_fusion_enabled = True
        self.mock_config.high_rate_positioning = True
        self.mock_config.hnr_rate_hz = 10
        self.mock_config.enable_esf_ins = True
        self.mock_config.disable_nmea_output = True
        
        self.handler = GPSHandler(self.mock_config)
    
    def test_initialization(self):
        """Test GPS handler initialization."""
        self.assertEqual(self.handler.config, self.mock_config)
        self.assertFalse(self.handler.connected)
        self.assertEqual(self.handler.latest_data, {})
        self.assertIsNone(self.handler.serial_port)
    
    @patch('ublox_gps.gps_handler.serial_asyncio.open_serial_connection')
    async def test_successful_connection(self, mock_serial):
        """Test successful GPS device connection."""
        # Mock successful serial connection
        mock_transport = Mock()
        mock_protocol = Mock()
        mock_serial.return_value = (mock_protocol, mock_transport)
        
        with patch.object(self.handler, '_device_exists', return_value=True):
            with patch.object(self.handler, '_configure_device', new_callable=AsyncMock):
                await self.handler._connect_device()
                
                self.assertTrue(self.handler.connected)
                mock_serial.assert_called_once()
    
    @patch('ublox_gps.gps_handler.serial_asyncio.list_serial_ports')
    async def test_connection_device_not_found(self, mock_list_ports):
        """Test connection failure when device not found."""
        # Mock device not existing
        mock_list_ports.return_value = [Mock(name="/dev/ttyUSB1")]
        
        with patch.object(self.handler, '_device_exists', return_value=False):
            with self.assertRaises(GPSConnectionError) as context:
                await self.handler._connect_device()
            
            self.assertIn("GPS device not found", str(context.exception))
    
    def test_device_exists_check(self):
        """Test device existence checking."""
        with patch('os.path.exists', return_value=True):
            self.assertTrue(self.handler._device_exists("/dev/ttyUSB0"))
        
        with patch('os.path.exists', return_value=False):
            self.assertFalse(self.handler._device_exists("/dev/ttyUSB0"))
    
    async def test_configure_device_zed_f9r(self):
        """Test ZED-F9R specific device configuration."""
        with patch.object(self.handler, '_configure_navigation_engine', new_callable=AsyncMock) as mock_nav:
            with patch.object(self.handler, '_configure_dynamic_model', new_callable=AsyncMock) as mock_dyn:
                with patch.object(self.handler, '_enable_messages', new_callable=AsyncMock) as mock_enable:
                    with patch.object(self.handler, '_disable_nmea_output', new_callable=AsyncMock) as mock_nmea:
                        await self.handler._configure_device()
                        
                        # Should call ZED-F9R specific configuration
                        mock_nav.assert_called_once()
                        mock_dyn.assert_called_once()
                        mock_enable.assert_called_once()
                        mock_nmea.assert_called_once()
    
    async def test_configure_device_zed_f9p(self):
        """Test ZED-F9P device configuration (backward compatibility)."""
        # Change config to ZED-F9P
        self.mock_config.device_type = "ZED-F9P"
        self.mock_config.dead_reckoning_enabled = False
        
        with patch.object(self.handler, '_configure_navigation_engine', new_callable=AsyncMock) as mock_nav:
            with patch.object(self.handler, '_configure_dynamic_model', new_callable=AsyncMock) as mock_dyn:
                with patch.object(self.handler, '_enable_messages', new_callable=AsyncMock) as mock_enable:
                    await self.handler._configure_device()
                    
                    # Should skip navigation engine config for ZED-F9P
                    mock_nav.assert_not_called()
                    mock_dyn.assert_called_once()  # Dynamic model still configured
                    mock_enable.assert_called_once()
    
    def test_dynamic_model_mapping(self):
        """Test dynamic model code mapping."""
        test_cases = [
            ("portable", 0),
            ("stationary", 2),
            ("pedestrian", 3),
            ("automotive", 4),
            ("sea", 5),
            ("airborne1g", 6),
            ("unknown_model", 4)  # Should default to automotive
        ]
        
        for model_type, expected_code in test_cases:
            self.mock_config.dynamic_model_type = model_type
            actual_code = self.handler._get_dynamic_model_code()
            self.assertEqual(actual_code, expected_code)
    
    def test_fix_type_naming(self):
        """Test fix type name generation with RTK status."""
        test_cases = [
            (0, 0, "No Fix"),
            (1, 0, "Dead Reckoning Only"),
            (2, 0, "2D Fix"),
            (3, 0, "3D Fix"),
            (3, 1, "3D Fix + RTK Float"),
            (3, 2, "3D Fix + RTK Fixed"),
            (4, 0, "GNSS + Dead Reckoning"),
            (4, 1, "GNSS + Dead Reckoning + RTK Float"),
            (4, 2, "GNSS + Dead Reckoning + RTK Fixed"),
            (5, 0, "Time Only Fix")
        ]
        
        for fix_type, carr_soln, expected_name in test_cases:
            actual_name = self.handler._get_fix_type_name(fix_type, carr_soln)
            self.assertEqual(actual_name, expected_name)
    
    async def test_nav_pvt_processing(self):
        """Test NAV-PVT message processing."""
        # Create mock NAV-PVT message
        mock_message = Mock()
        mock_message.identity = 'NAV-PVT'
        mock_message.lat = 400000000  # 40.0 degrees * 1e7
        mock_message.lon = -740000000  # -74.0 degrees * 1e7
        mock_message.height = 100000  # 100m * 1000
        mock_message.hMSL = 50000  # 50m * 1000
        mock_message.hAcc = 2000  # 2m * 1000
        mock_message.vAcc = 3000  # 3m * 1000
        mock_message.fixType = 3
        mock_message.carrSoln = 2  # RTK Fixed
        mock_message.valid = 0x07  # All valid flags
        mock_message.gSpeed = 5000  # 5 m/s * 1000
        mock_message.heading = 45000000  # 45 degrees * 1e5
        mock_message.numSV = 12
        
        await self.handler._process_nav_pvt(mock_message)
        
        # Check that data was properly processed and stored
        self.assertIn('latitude', self.handler.latest_data)
        self.assertIn('longitude', self.handler.latest_data)
        self.assertIn('fix_type', self.handler.latest_data)
        self.assertEqual(self.handler.latest_data['latitude'], 40.0)
        self.assertEqual(self.handler.latest_data['longitude'], -74.0)
        self.assertEqual(self.handler.latest_data['fix_type'], "3D Fix + RTK Fixed")
    
    async def test_hnr_pvt_processing(self):
        """Test HNR-PVT message processing for ZED-F9R."""
        mock_message = Mock()
        mock_message.identity = 'HNR-PVT'
        mock_message.lat = 400000000
        mock_message.lon = -740000000
        mock_message.height = 100000
        mock_message.gSpeed = 10000
        mock_message.heading = 90000000
        
        await self.handler._process_hnr_pvt(mock_message)
        
        # Check HNR-specific data
        self.assertIn('hnr_latitude', self.handler.latest_data)
        self.assertIn('hnr_longitude', self.handler.latest_data)
        self.assertIn('hnr_speed', self.handler.latest_data)
        self.assertIn('hnr_heading', self.handler.latest_data)
    
    async def test_esf_ins_processing(self):
        """Test ESF-INS message processing for sensor fusion."""
        mock_message = Mock()
        mock_message.identity = 'ESF-INS'
        # Mock sensor fusion data
        mock_message.xAccel = 100  # 0.1 m/s^2
        mock_message.yAccel = -50  # -0.05 m/s^2
        mock_message.zAccel = 9800  # ~9.8 m/s^2
        mock_message.xGyro = 10  # 0.01 deg/s
        mock_message.yGyro = -5
        mock_message.zGyro = 0
        
        # Add getattr fallbacks for missing attributes
        def mock_getattr(obj, attr, default=0):
            return getattr(obj, attr, default)
        
        with patch('builtins.getattr', side_effect=mock_getattr):
            await self.handler._process_esf_ins(mock_message)
        
        # Check sensor fusion data
        self.assertIn('fusion_timestamp', self.handler.latest_data)
        self.assertIn('fusion_accel_x', self.handler.latest_data)
        self.assertIn('fusion_gyro_x', self.handler.latest_data)
    
    async def test_error_handling_in_message_processing(self):
        """Test error handling during message processing."""
        # Create a mock message that will cause an error
        mock_message = Mock()
        mock_message.identity = 'NAV-PVT'
        mock_message.lat = None  # This should cause an error
        
        # Should not raise exception, but should log error
        with patch('ublox_gps.gps_handler.logger') as mock_logger:
            await self.handler._process_nav_pvt(mock_message)
            # Should have logged an error
            mock_logger.debug.assert_called()
    
    async def test_send_corrections(self):
        """Test sending RTCM corrections to GPS device."""
        # Mock connected serial port
        mock_port = Mock()
        self.handler.serial_port = mock_port
        self.handler.connected = True
        
        rtcm_data = b'\xD3\x00\x13\x43\x50test_rtcm_data\x12\x34\x56'
        
        await self.handler.send_corrections(rtcm_data)
        
        # Should have written to serial port
        mock_port.write.assert_called_once_with(rtcm_data)
    
    async def test_send_corrections_not_connected(self):
        """Test sending corrections when not connected."""
        self.handler.connected = False
        self.handler.serial_port = None
        
        rtcm_data = b'test_data'
        
        # Should handle gracefully without error
        await self.handler.send_corrections(rtcm_data)
        # Should not crash
    
    def test_get_latest_data(self):
        """Test getting latest GPS data."""
        # Add some test data
        test_data = {
            'latitude': 40.0,
            'longitude': -74.0,
            'fix_type': '3D Fix',
            'timestamp': datetime.utcnow().isoformat()
        }
        self.handler.latest_data = test_data
        
        result = asyncio.run(self.handler.get_latest_data())
        self.assertEqual(result, test_data)
    
    def test_is_connected(self):
        """Test connection status checking."""
        # Test not connected
        self.assertFalse(self.handler.is_connected())
        
        # Test connected
        mock_port = Mock()
        mock_port.is_open = True
        self.handler.serial_port = mock_port
        self.handler.connected = True
        
        self.assertTrue(self.handler.is_connected())
    
    async def test_nmea_message_processing(self):
        """Test NMEA message processing."""
        # Create mock NMEA GGA message
        mock_message = Mock()
        mock_message.sentence_type = 'GGA'
        mock_message.latitude = 40.0
        mock_message.longitude = -74.0
        mock_message.altitude = 100.0
        mock_message.gps_qual = 4  # RTK Fixed
        
        await self.handler._process_nmea_message(mock_message)
        
        # Check NMEA data was processed
        self.assertIn('nmea_timestamp', self.handler.latest_data)
        self.assertIn('nmea_latitude', self.handler.latest_data)
        self.assertIn('fix_quality', self.handler.latest_data)


class TestGPSHandlerIntegration(unittest.TestCase):
    """Integration tests for GPS handler."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.mock_config = Mock()
        self.mock_config.gps_device = "/dev/ttyUSB0"
        self.mock_config.gps_baudrate = 38400
        self.mock_config.device_type = "ZED-F9R"
        self.mock_config.dead_reckoning_enabled = True
        
    @patch('ublox_gps.gps_handler.serial_asyncio.open_serial_connection')
    async def test_full_startup_sequence(self, mock_serial):
        """Test complete GPS handler startup sequence."""
        handler = GPSHandler(self.mock_config)
        
        # Mock successful connection
        mock_transport = Mock()
        mock_protocol = Mock()
        mock_serial.return_value = (mock_protocol, mock_transport)
        
        with patch.object(handler, '_device_exists', return_value=True):
            with patch.object(handler, '_send_ubx_message', new_callable=AsyncMock):
                await handler.start()
                
                self.assertTrue(handler.connected)
                self.assertIsNotNone(handler.reader_task)
    
    async def test_error_recovery(self):
        """Test error recovery during operation."""
        handler = GPSHandler(self.mock_config)
        
        # Test that handler can recover from connection errors
        with patch.object(handler, '_connect_device', side_effect=GPSConnectionError("Test error")):
            with self.assertRaises(GPSConnectionError):
                await handler.start()
            
            # Handler should be in safe state
            self.assertFalse(handler.connected)


if __name__ == '__main__':
    unittest.main()
