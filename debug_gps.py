#!/usr/bin/env python3
"""
GPS Debug Tool for UBlox GPS Add-on
Helps diagnose connection and data flow issues
"""

import asyncio
import logging
import sys
import serial_asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import time

# Configure logging for debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class GPSDebugger:
    """Debug tool for GPS connection and data flow issues."""
    
    def __init__(self, device_path: str = "/dev/ttyUSB0", baudrate: int = 38400):
        self.device_path = device_path
        self.baudrate = baudrate
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.bytes_received = 0
        self.messages_received = 0
        self.last_data_time = None
        
    async def test_connection(self) -> bool:
        """Test basic serial connection to GPS device."""
        logger.info(f"Testing connection to {self.device_path} @ {self.baudrate} baud...")
        
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.device_path, 
                baudrate=self.baudrate,
                timeout=5
            )
            self.connected = True
            logger.info("✅ Serial connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False
    
    async def test_data_flow(self, duration: int = 30) -> Dict[str, Any]:
        """Test if data is flowing from GPS device."""
        if not self.connected:
            logger.error("❌ Not connected to GPS device")
            return {}
        
        logger.info(f"Testing data flow for {duration} seconds...")
        start_time = time.time()
        raw_messages = []
        ubx_messages = []
        nmea_messages = []
        
        try:
            while time.time() - start_time < duration:
                # Read data with timeout
                try:
                    data = await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
                    if data:
                        self.bytes_received += len(data)
                        self.last_data_time = datetime.now()
                        
                        # Log raw data (first few bytes)
                        logger.debug(f"📡 Received {len(data)} bytes: {data[:20].hex()}...")
                        
                        # Try to identify message types
                        for i, byte in enumerate(data):
                            # Look for UBX sync bytes (0xB5, 0x62)
                            if i < len(data) - 1 and byte == 0xB5 and data[i+1] == 0x62:
                                ubx_messages.append(f"UBX at offset {i}")
                                logger.debug(f"🛰️ UBX message detected at offset {i}")
                            
                            # Look for NMEA messages (start with $)
                            if byte == ord('$'):
                                try:
                                    # Find end of NMEA sentence
                                    end_idx = data.find(b'\r\n', i)
                                    if end_idx > 0:
                                        nmea_msg = data[i:end_idx].decode('ascii', errors='ignore')
                                        nmea_messages.append(nmea_msg)
                                        logger.debug(f"📟 NMEA message: {nmea_msg}")
                                except:
                                    pass
                        
                        raw_messages.append({
                            'timestamp': self.last_data_time.isoformat(),
                            'length': len(data),
                            'data_hex': data.hex()
                        })
                        
                except asyncio.TimeoutError:
                    logger.debug("⏱️ No data received in last second")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Error during data flow test: {e}")
        
        # Summary
        results = {
            'duration': duration,
            'bytes_received': self.bytes_received,
            'raw_messages_count': len(raw_messages),
            'ubx_messages_count': len(ubx_messages),
            'nmea_messages_count': len(nmea_messages),
            'last_data_time': self.last_data_time.isoformat() if self.last_data_time else None,
            'data_rate_bps': self.bytes_received / duration if duration > 0 else 0,
            'sample_nmea_messages': nmea_messages[:5],  # First 5 NMEA messages
            'sample_ubx_detections': ubx_messages[:5],   # First 5 UBX detections
        }
        
        logger.info(f"📊 Data Flow Test Results:")
        logger.info(f"   • Total bytes received: {results['bytes_received']}")
        logger.info(f"   • Data rate: {results['data_rate_bps']:.1f} bytes/sec")
        logger.info(f"   • UBX messages detected: {results['ubx_messages_count']}")
        logger.info(f"   • NMEA messages detected: {results['nmea_messages_count']}")
        logger.info(f"   • Last data received: {results['last_data_time']}")
        
        return results
    
    async def test_device_response(self) -> bool:
        """Test if device responds to commands."""
        if not self.connected:
            logger.error("❌ Not connected to GPS device")
            return False
        
        logger.info("Testing device responsiveness...")
        
        try:
            # Send UBX-MON-VER command to get version info
            # UBX sync (0xB5 0x62) + Class (0x0A) + ID (0x04) + Length (0x00 0x00) + Checksum
            ver_cmd = bytes([0xB5, 0x62, 0x0A, 0x04, 0x00, 0x00, 0x0E, 0x34])
            
            logger.info("📤 Sending UBX-MON-VER command...")
            self.writer.write(ver_cmd)
            await self.writer.drain()
            
            # Wait for response
            response_received = False
            for _ in range(10):  # Wait up to 10 seconds
                try:
                    data = await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
                    if data:
                        logger.debug(f"📥 Response: {data.hex()}")
                        # Look for UBX-MON-VER response (0xB5 0x62 0x0A 0x04)
                        if b'\xB5\x62\x0A\x04' in data:
                            logger.info("✅ Device responded to UBX-MON-VER command")
                            response_received = True
                            break
                except asyncio.TimeoutError:
                    continue
            
            if not response_received:
                logger.warning("⚠️ No response to UBX-MON-VER command")
            
            return response_received
            
        except Exception as e:
            logger.error(f"❌ Error testing device response: {e}")
            return False
    
    async def close(self):
        """Close connection."""
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("Connection closed")

async def main():
    """Main debug function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug UBlox GPS connection')
    parser.add_argument('--device', default='/dev/ttyUSB0', help='GPS device path')
    parser.add_argument('--baudrate', type=int, default=38400, help='Baud rate')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    
    args = parser.parse_args()
    
    debugger = GPSDebugger(args.device, args.baudrate)
    
    try:
        # Test 1: Connection
        if not await debugger.test_connection():
            logger.error("❌ Cannot proceed - connection failed")
            return
        
        # Test 2: Device response
        await debugger.test_device_response()
        
        # Test 3: Data flow
        results = await debugger.test_data_flow(args.duration)
        
        # Final diagnosis
        logger.info("\n🔍 DIAGNOSIS:")
        if results['bytes_received'] == 0:
            logger.error("❌ NO DATA RECEIVED - Check device power, connections, and configuration")
        elif results['ubx_messages_count'] == 0 and results['nmea_messages_count'] == 0:
            logger.warning("⚠️ RAW DATA RECEIVED BUT NO VALID MESSAGES - Check baud rate and message configuration")
        elif results['ubx_messages_count'] > 0 or results['nmea_messages_count'] > 0:
            logger.info("✅ GPS MESSAGES DETECTED - Data flow appears normal")
        
        logger.info(f"\n📋 NEXT STEPS:")
        if results['bytes_received'] == 0:
            logger.info("   1. Check GPS device power and LED status")
            logger.info("   2. Verify USB/serial cable connection")
            logger.info("   3. Check device path and permissions")
            logger.info("   4. Try different baud rates (9600, 38400, 115200)")
        else:
            logger.info("   1. Check GPS antenna connection")
            logger.info("   2. Move to location with clear sky view")
            logger.info("   3. Wait for GPS fix (may take several minutes)")
            logger.info("   4. Check UBlox configuration and message output settings")
    
    finally:
        await debugger.close()

if __name__ == "__main__":
    asyncio.run(main())
