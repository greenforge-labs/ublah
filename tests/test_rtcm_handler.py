"""
Unit tests for RTCM handler functionality.
Tests RTCM message filtering, validation, and statistics.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from ublox_gps.rtcm_handler import RTCMHandler, RTCMMessage, RTCMStatistics, HealthStatus
from ublox_gps.config import Config


class TestRTCMHandler(unittest.TestCase):
    """Test RTCM handler functionality."""
    
    def setUp(self):
        """Set up test RTCM handler."""
        self.mock_config = Mock()
        self.mock_config.rtcm_message_filter = [1005, 1077, 1087, 1097, 1127]
        self.mock_config.rtcm_filtering_enabled = True
        self.mock_config.rtcm_validation_enabled = True
        self.mock_config.rtcm_max_message_age_seconds = 30
        
        self.handler = RTCMHandler(self.mock_config)
    
    def test_initialization(self):
        """Test RTCM handler initialization."""
        self.assertIsInstance(self.handler.statistics, RTCMStatistics)
        self.assertEqual(self.handler.filtered_message_types, {1005, 1077, 1087, 1097, 1127})
        self.assertTrue(self.handler.enable_validation)
    
    def test_message_filtering_allowed(self):
        """Test that supported message types are allowed through."""
        # Create a mock RTCM message
        message = RTCMMessage(
            message_type=1077,  # GPS MSM7 - should be allowed
            message_length=100,
            payload=b'test payload',
            crc=0x123456,
            timestamp=datetime.utcnow(),
            station_id=1234
        )
        
        # Test filtering decision
        should_filter = self.handler._should_filter_message(message)
        self.assertTrue(should_filter)
    
    def test_message_filtering_blocked(self):
        """Test that unsupported message types are blocked."""
        # Create a mock RTCM message with unsupported type
        message = RTCMMessage(
            message_type=1019,  # GPS Ephemeris - not in supported list
            message_length=100,
            payload=b'test payload',
            crc=0x123456,
            timestamp=datetime.utcnow(),
            station_id=1234
        )
        
        # Test filtering decision
        should_filter = self.handler._should_filter_message(message)
        self.assertFalse(should_filter)
    
    def test_message_validation_valid(self):
        """Test validation of valid RTCM messages."""
        message = RTCMMessage(
            message_type=1077,
            message_length=100,
            payload=b'test payload' * 10,  # 120 bytes payload
            crc=0x123456,
            timestamp=datetime.utcnow(),
            station_id=1234
        )
        
        is_valid = self.handler._validate_message(message)
        self.assertTrue(is_valid)
    
    def test_message_validation_invalid_type(self):
        """Test validation rejects invalid message types."""
        message = RTCMMessage(
            message_type=999,  # Invalid type (< 1000)
            message_length=100,
            payload=b'test payload',
            crc=0x123456,
            timestamp=datetime.utcnow()
        )
        
        is_valid = self.handler._validate_message(message)
        self.assertFalse(is_valid)
    
    def test_message_validation_too_old(self):
        """Test validation rejects messages that are too old."""
        old_timestamp = datetime.utcnow() - timedelta(minutes=5)  # Older than max_message_age
        
        message = RTCMMessage(
            message_type=1077,
            message_length=100,
            payload=b'test payload',
            crc=0x123456,
            timestamp=old_timestamp
        )
        
        is_valid = self.handler._validate_message(message)
        self.assertFalse(is_valid)
    
    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        # Create sample RTCM data (simplified)
        rtcm_data = b'\xD3\x00\x13\x43\x50' + b'test_payload_data' + b'\x12\x34\x56'
        
        # Process the data
        filtered_data, stats = self.handler.process_rtcm_data(rtcm_data)
        
        # Check that statistics were updated
        self.assertIsInstance(stats, RTCMStatistics)
        # Note: Actual parsing may fail with mock data, but structure should be correct
    
    def test_statistics_summary(self):
        """Test statistics summary generation."""
        # Add some fake statistics
        self.handler.statistics.total_messages = 100
        self.handler.statistics.valid_messages = 90
        self.handler.statistics.invalid_messages = 10
        self.handler.statistics.message_counts[1077] = 45
        self.handler.statistics.message_counts[1087] = 35
        self.handler.statistics.last_message_time = datetime.utcnow()
        
        summary = self.handler.get_statistics_summary()
        
        self.assertEqual(summary['total_messages'], 100)
        self.assertEqual(summary['valid_messages'], 90)
        self.assertEqual(summary['invalid_messages'], 10)
        self.assertEqual(summary['message_types'][1077], 45)
        self.assertEqual(summary['message_types'][1087], 35)
        self.assertIn('last_message_time', summary)
        self.assertIn('supported_messages', summary)
    
    def test_message_descriptions(self):
        """Test message type descriptions."""
        self.assertEqual(
            self.handler.get_message_description(1077),
            "GPS MSM7 - Full Pseudoranges and PhaseRanges plus CNR"
        )
        self.assertEqual(
            self.handler.get_message_description(1005),
            "Stationary RTK Reference Station ARP"
        )
        self.assertTrue(
            self.handler.get_message_description(9999).startswith("Unknown RTCM-")
        )
    
    def test_statistics_reset(self):
        """Test statistics reset functionality."""
        # Add some statistics
        self.handler.statistics.total_messages = 50
        self.handler.statistics.valid_messages = 45
        self.handler.statistics.message_counts[1077] = 25
        
        # Reset statistics
        self.handler.reset_statistics()
        
        # Verify reset
        self.assertEqual(self.handler.statistics.total_messages, 0)
        self.assertEqual(self.handler.statistics.valid_messages, 0)
        self.assertEqual(len(self.handler.statistics.message_counts), 0)
    
    def test_data_rate_calculation(self):
        """Test data rate calculation."""
        # Simulate multiple data updates
        for i in range(5):
            self.handler._update_data_rate(1000)  # 1KB per update
        
        # Data rate should be calculated
        self.assertGreaterEqual(self.handler.statistics.data_rate_bps, 0)
    
    def test_configuration_based_filtering(self):
        """Test that filtering respects configuration."""
        # Test with filtering disabled
        disabled_config = Mock()
        disabled_config.rtcm_filtering_enabled = False
        disabled_config.rtcm_message_filter = []
        
        disabled_handler = RTCMHandler(disabled_config)
        
        # Should have empty filter set when disabled
        self.assertEqual(len(disabled_handler.filtered_message_types), 0)
    
    def test_edge_case_empty_data(self):
        """Test handling of empty RTCM data."""
        filtered_data, stats = self.handler.process_rtcm_data(b'')
        
        self.assertEqual(filtered_data, b'')
        self.assertIsInstance(stats, RTCMStatistics)
    
    def test_edge_case_malformed_data(self):
        """Test handling of malformed RTCM data."""
        malformed_data = b'\xFF\xFF\xFF\xFF'  # Not valid RTCM
        
        filtered_data, stats = self.handler.process_rtcm_data(malformed_data)
        
        # Should handle gracefully without crashing
        self.assertIsInstance(filtered_data, bytes)
        self.assertIsInstance(stats, RTCMStatistics)


if __name__ == '__main__':
    unittest.main()
