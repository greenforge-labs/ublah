"""
RTCM Handler for message filtering, validation, and statistics.
Supports RTCM 3.x message parsing and filtering for ZED-F9P/ZED-F9R devices.
"""

import logging
import struct
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RTCMMessage:
    """RTCM message data structure."""
    message_type: int
    message_length: int
    payload: bytes
    crc: int
    timestamp: datetime
    station_id: Optional[int] = None


@dataclass
class RTCMStatistics:
    """RTCM message statistics."""
    total_messages: int = 0
    valid_messages: int = 0
    invalid_messages: int = 0
    filtered_messages: int = 0
    message_counts: Dict[int, int] = None
    last_message_time: Optional[datetime] = None
    data_rate_bps: float = 0.0
    
    def __post_init__(self):
        if self.message_counts is None:
            self.message_counts = defaultdict(int)


class RTCMHandler:
    """Handle RTCM message filtering, validation, and statistics."""
    
    # Supported RTCM message types for ZED-F9P/ZED-F9R
    SUPPORTED_MESSAGES = [1005, 1077, 1087, 1097, 1127]
    
    # RTCM message type descriptions
    MESSAGE_DESCRIPTIONS = {
        1005: "Stationary RTK Reference Station ARP",
        1077: "GPS MSM7 - Full Pseudoranges and PhaseRanges plus CNR",
        1087: "GLONASS MSM7 - Full Pseudoranges and PhaseRanges plus CNR", 
        1097: "Galileo MSM7 - Full Pseudoranges and PhaseRanges plus CNR",
        1127: "BeiDou MSM7 - Full Pseudoranges and PhaseRanges plus CNR",
        1230: "GLONASS L1 and L2 Code-Phase Biases",
    }
    
    def __init__(self, config):
        self.config = config
        self.statistics = RTCMStatistics()
        self.message_buffer = bytearray()
        self.filtered_message_types = set(self.SUPPORTED_MESSAGES)
        self.enable_validation = True
        self.max_message_age = timedelta(seconds=30)  # Max age for RTCM messages
        self.data_rate_window = []
        self.data_rate_window_size = 10  # Track last 10 seconds
        
        # Configure filtering based on config
        if hasattr(config, 'rtcm_message_filter') and config.rtcm_message_filter:
            self.filtered_message_types = set(config.rtcm_message_filter)
            logger.info(f"RTCM filtering enabled for message types: {sorted(self.filtered_message_types)}")
    
    def process_rtcm_data(self, data: bytes) -> Tuple[bytes, RTCMStatistics]:
        """Process RTCM data, filter messages, and return filtered data with statistics."""
        if not data:
            return b'', self.statistics
        
        # Add new data to buffer
        self.message_buffer.extend(data)
        
        # Parse and filter messages
        filtered_data = bytearray()
        messages_processed = 0
        
        while len(self.message_buffer) >= 6:  # Minimum RTCM message size
            message = self._parse_next_message()
            if message is None:
                break
            
            messages_processed += 1
            self.statistics.total_messages += 1
            
            # Validate message if enabled
            if self.enable_validation:
                if self._validate_message(message):
                    self.statistics.valid_messages += 1
                else:
                    self.statistics.invalid_messages += 1
                    logger.debug(f"Invalid RTCM message type {message.message_type}")
                    continue
            
            # Filter message by type
            if self._should_filter_message(message):
                # Add to filtered output
                filtered_data.extend(self._serialize_message(message))
                self.statistics.message_counts[message.message_type] += 1
                logger.debug(f"Passed RTCM-{message.message_type} ({len(message.payload)} bytes)")
            else:
                self.statistics.filtered_messages += 1
                logger.debug(f"Filtered RTCM-{message.message_type}")
        
        # Update statistics
        if messages_processed > 0:
            self.statistics.last_message_time = datetime.utcnow()
            self._update_data_rate(len(data))
        
        return bytes(filtered_data), self.statistics
    
    def _parse_next_message(self) -> Optional[RTCMMessage]:
        """Parse the next RTCM message from the buffer."""
        # Find RTCM sync pattern (0xD3)
        sync_index = -1
        for i in range(len(self.message_buffer)):
            if self.message_buffer[i] == 0xD3:
                sync_index = i
                break
        
        if sync_index == -1:
            # No sync found, clear buffer
            self.message_buffer.clear()
            return None
        
        # Remove data before sync
        if sync_index > 0:
            self.message_buffer = self.message_buffer[sync_index:]
        
        # Check if we have enough data for header
        if len(self.message_buffer) < 6:
            return None
        
        try:
            # Parse RTCM header
            header = struct.unpack('>BHH', self.message_buffer[0:5])
            sync_byte = header[0]  # Should be 0xD3
            length_and_msg = header[1]  # Length (10 bits) + reserved (6 bits)
            message_type = header[2] >> 4  # Message type (12 bits)
            
            # Extract length (first 10 bits)
            message_length = length_and_msg & 0x3FF
            
            # Check if we have complete message
            total_length = 6 + message_length  # Header + payload + CRC
            if len(self.message_buffer) < total_length:
                return None
            
            # Extract payload and CRC
            payload = bytes(self.message_buffer[3:3+message_length])
            crc_bytes = self.message_buffer[3+message_length:3+message_length+3]
            crc = struct.unpack('>I', b'\x00' + crc_bytes)[0]  # 24-bit CRC
            
            # Remove processed message from buffer
            self.message_buffer = self.message_buffer[total_length:]
            
            # Extract station ID if available (first 12 bits of payload)
            station_id = None
            if len(payload) >= 2:
                station_id = struct.unpack('>H', payload[0:2])[0] >> 4
            
            return RTCMMessage(
                message_type=message_type,
                message_length=message_length,
                payload=payload,
                crc=crc,
                timestamp=datetime.utcnow(),
                station_id=station_id
            )
            
        except (struct.error, IndexError) as e:
            logger.debug(f"Error parsing RTCM message: {e}")
            # Remove first byte and try again
            self.message_buffer = self.message_buffer[1:]
            return None
    
    def _validate_message(self, message: RTCMMessage) -> bool:
        """Validate RTCM message integrity."""
        try:
            # Basic validation checks
            if message.message_type < 1000 or message.message_type > 4095:
                return False
            
            if message.message_length < 0 or message.message_length > 1023:
                return False
            
            # Check message age
            if datetime.utcnow() - message.timestamp > self.max_message_age:
                logger.debug(f"RTCM message too old: {message.message_type}")
                return False
            
            # TODO: Add CRC validation if needed
            # For now, assume messages from NTRIP caster are CRC-valid
            
            return True
            
        except Exception as e:
            logger.debug(f"RTCM validation error: {e}")
            return False
    
    def _should_filter_message(self, message: RTCMMessage) -> bool:
        """Determine if message should be passed through the filter."""
        return message.message_type in self.filtered_message_types
    
    def _serialize_message(self, message: RTCMMessage) -> bytes:
        """Serialize RTCM message back to bytes."""
        try:
            # Reconstruct RTCM message
            sync_byte = 0xD3
            length_and_reserved = message.message_length & 0x3FF
            msg_type_and_data = (message.message_type << 4) | (message.payload[0] >> 4 if message.payload else 0)
            
            # Pack header
            header = struct.pack('>BHH', sync_byte, length_and_reserved, msg_type_and_data)
            
            # Add payload (skip first partial byte that's in header)
            if len(message.payload) > 0:
                payload_data = message.payload
            else:
                payload_data = b''
            
            # Add CRC (3 bytes)
            crc_bytes = struct.pack('>I', message.crc)[1:]  # Take last 3 bytes
            
            return header[:3] + payload_data + crc_bytes
            
        except Exception as e:
            logger.error(f"Error serializing RTCM message: {e}")
            return b''
    
    def _update_data_rate(self, bytes_count: int) -> None:
        """Update data rate statistics."""
        now = datetime.utcnow()
        self.data_rate_window.append((now, bytes_count))
        
        # Remove old entries (older than window size)
        cutoff = now - timedelta(seconds=self.data_rate_window_size)
        self.data_rate_window = [(t, b) for t, b in self.data_rate_window if t > cutoff]
        
        # Calculate data rate
        if len(self.data_rate_window) > 1:
            total_bytes = sum(b for _, b in self.data_rate_window)
            time_span = (self.data_rate_window[-1][0] - self.data_rate_window[0][0]).total_seconds()
            if time_span > 0:
                self.statistics.data_rate_bps = (total_bytes * 8) / time_span
    
    def get_message_description(self, message_type: int) -> str:
        """Get human-readable description of RTCM message type."""
        return self.MESSAGE_DESCRIPTIONS.get(message_type, f"Unknown RTCM-{message_type}")
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary."""
        return {
            'total_messages': self.statistics.total_messages,
            'valid_messages': self.statistics.valid_messages,
            'invalid_messages': self.statistics.invalid_messages,
            'filtered_messages': self.statistics.filtered_messages,
            'message_types': dict(self.statistics.message_counts),
            'last_message_time': self.statistics.last_message_time.isoformat() if self.statistics.last_message_time else None,
            'data_rate_bps': round(self.statistics.data_rate_bps, 2),
            'data_rate_kbps': round(self.statistics.data_rate_bps / 1000, 2),
            'supported_messages': list(self.SUPPORTED_MESSAGES),
            'filtered_message_types': list(self.filtered_message_types),
        }
    
    def reset_statistics(self) -> None:
        """Reset all statistics counters."""
        self.statistics = RTCMStatistics()
        self.data_rate_window.clear()
        logger.info("RTCM statistics reset")
