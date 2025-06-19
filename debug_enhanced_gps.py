#!/usr/bin/env python3
"""
Enhanced GPS Debug Tool with detailed logging and diagnostics
Helps identify specific issues in the UBlox GPS data pipeline
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add the ublox_gps module to the path
sys.path.insert(0, str(Path(__file__).parent / 'ublox_gps'))

from config import Config
from gps_handler import GPSHandler
from ha_interface import HomeAssistantInterface

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('gps_debug.log')
    ]
)

logger = logging.getLogger(__name__)

class EnhancedGPSDebugger:
    """Enhanced GPS debugger that uses the actual GPS handler with detailed logging."""
    
    def __init__(self):
        self.config = Config()
        self.gps_handler = None
        self.debug_stats = {
            'connection_attempts': 0,
            'bytes_received': 0,
            'messages_parsed': 0,
            'latest_data_updates': 0,
            'errors': [],
            'start_time': datetime.now()
        }
        
    async def run_comprehensive_debug(self, duration: int = 60) -> dict:
        """Run comprehensive debugging for specified duration."""
        logger.info(f"🔍 Starting comprehensive GPS debug session for {duration} seconds...")
        
        try:
            # Step 1: Test configuration
            await self._debug_configuration()
            
            # Step 2: Test GPS handler initialization
            await self._debug_gps_handler_init()
            
            # Step 3: Monitor data flow
            await self._monitor_data_flow(duration)
            
            # Step 4: Test Home Assistant interface
            await self._debug_ha_interface()
            
        except Exception as e:
            logger.error(f"❌ Debug session failed: {e}")
            self.debug_stats['errors'].append(f"Debug session error: {e}")
        
        finally:
            if self.gps_handler:
                await self.gps_handler.stop()
        
        return self._generate_report()
    
    async def _debug_configuration(self):
        """Debug configuration settings."""
        logger.info("📋 Debugging configuration...")
        
        try:
            config_data = {
                'gps_device': self.config.gps_device,
                'gps_baudrate': self.config.gps_baudrate,
                'device_type': self.config.device_type,
                'update_rate_hz': self.config.update_rate_hz,
                'ntrip_enabled': self.config.ntrip_enabled,
            }
            
            logger.info(f"📋 Configuration: {json.dumps(config_data, indent=2)}")
            
            # Check if device file exists
            if os.path.exists(self.config.gps_device):
                logger.info(f"✅ GPS device file exists: {self.config.gps_device}")
            else:
                logger.error(f"❌ GPS device file not found: {self.config.gps_device}")
                self.debug_stats['errors'].append(f"Device file not found: {self.config.gps_device}")
                
        except Exception as e:
            logger.error(f"❌ Configuration debug failed: {e}")
            self.debug_stats['errors'].append(f"Configuration error: {e}")
    
    async def _debug_gps_handler_init(self):
        """Debug GPS handler initialization."""
        logger.info("🛰️ Debugging GPS handler initialization...")
        
        try:
            self.debug_stats['connection_attempts'] += 1
            self.gps_handler = GPSHandler(self.config)
            
            # Monkey patch the GPS handler to add debug logging
            original_read_loop = self.gps_handler._read_data_loop
            original_parse_ubx = getattr(self.gps_handler, '_parse_ubx_message', None)
            original_parse_nmea = getattr(self.gps_handler, '_parse_nmea_message', None)
            
            async def debug_read_loop():
                logger.debug("🔄 Starting debug read loop...")
                bytes_count = 0
                message_count = 0
                
                while not self.gps_handler._stop_event.is_set() and self.gps_handler.connected:
                    try:
                        if self.gps_handler.reader.at_eof():
                            logger.warning("📡 Reader reached EOF")
                            break
                        
                        # Read data with detailed logging
                        data = await self.gps_handler.reader.read(1024)
                        if data:
                            bytes_count += len(data)
                            self.debug_stats['bytes_received'] += len(data)
                            logger.debug(f"📥 Received {len(data)} bytes (total: {bytes_count})")
                            logger.debug(f"📥 Data sample: {data[:50].hex()}...")
                            
                            # Check for UBX and NMEA patterns
                            ubx_count = data.count(b'\xb5\x62')
                            nmea_count = data.count(b'$')
                            
                            if ubx_count > 0:
                                logger.debug(f"🛰️ Found {ubx_count} potential UBX messages")
                            if nmea_count > 0:
                                logger.debug(f"📟 Found {nmea_count} potential NMEA messages")
                            
                            # Try to call original parsing if it exists
                            # This is just for monitoring - we'll let the original handle the actual parsing
                            
                        else:
                            logger.debug("📡 No data received this cycle")
                        
                        await asyncio.sleep(0.01)
                        
                    except Exception as e:
                        logger.error(f"❌ Error in debug read loop: {e}")
                        self.debug_stats['errors'].append(f"Read loop error: {e}")
                        await asyncio.sleep(1)
            
            # Replace the read loop with our debug version
            self.gps_handler._read_data_loop = debug_read_loop
            
            # Start the GPS handler
            await self.gps_handler.start()
            logger.info("✅ GPS handler started successfully")
            
        except Exception as e:
            logger.error(f"❌ GPS handler initialization failed: {e}")
            self.debug_stats['errors'].append(f"GPS handler init error: {e}")
            raise
    
    async def _monitor_data_flow(self, duration: int):
        """Monitor data flow and latest_data updates."""
        logger.info(f"📊 Monitoring data flow for {duration} seconds...")
        
        start_time = datetime.now()
        last_data_check = {}
        data_update_count = 0
        
        while (datetime.now() - start_time).total_seconds() < duration:
            try:
                # Check latest_data
                current_data = await self.gps_handler.get_latest_data()
                
                if current_data != last_data_check:
                    data_update_count += 1
                    self.debug_stats['latest_data_updates'] += 1
                    logger.info(f"📈 latest_data updated ({data_update_count}): {json.dumps(current_data, indent=2, default=str)}")
                    last_data_check = current_data.copy()
                
                # Check connection status
                if self.gps_handler.is_connected():
                    logger.debug("✅ GPS handler reports connected")
                else:
                    logger.warning("❌ GPS handler reports disconnected")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error monitoring data flow: {e}")
                self.debug_stats['errors'].append(f"Data flow monitor error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"📊 Data flow monitoring complete. Updates detected: {data_update_count}")
    
    async def _debug_ha_interface(self):
        """Debug Home Assistant interface."""
        logger.info("🏠 Debugging Home Assistant interface...")
        
        try:
            ha_interface = HomeAssistantInterface(self.config)
            await ha_interface.initialize_entities()
            logger.info("✅ Home Assistant interface initialized successfully")
            
            # Test with sample data
            sample_data = {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 100.0,
                'fix_type': 3,
                'satellites': 12,
                'timestamp': datetime.now()
            }
            
            await ha_interface.update_entities(sample_data)
            logger.info("✅ Home Assistant entity update test successful")
            
        except Exception as e:
            logger.error(f"❌ Home Assistant interface debug failed: {e}")
            self.debug_stats['errors'].append(f"HA interface error: {e}")
    
    def _generate_report(self) -> dict:
        """Generate comprehensive debug report."""
        duration = (datetime.now() - self.debug_stats['start_time']).total_seconds()
        
        report = {
            'debug_session': {
                'duration_seconds': duration,
                'timestamp': datetime.now().isoformat(),
                'configuration': {
                    'device': self.config.gps_device,
                    'baudrate': self.config.gps_baudrate,
                    'device_type': self.config.device_type,
                }
            },
            'statistics': self.debug_stats,
            'diagnosis': [],
            'recommendations': []
        }
        
        # Generate diagnosis
        if self.debug_stats['connection_attempts'] == 0:
            report['diagnosis'].append("❌ GPS handler initialization never attempted")
        elif len([e for e in self.debug_stats['errors'] if 'connection' in e.lower()]) > 0:
            report['diagnosis'].append("❌ Connection errors detected")
        elif self.debug_stats['bytes_received'] == 0:
            report['diagnosis'].append("❌ No data received from GPS device")
        elif self.debug_stats['latest_data_updates'] == 0:
            report['diagnosis'].append("⚠️ Data received but latest_data never updated")
        else:
            report['diagnosis'].append("✅ Data flow appears normal")
        
        # Generate recommendations
        if self.debug_stats['bytes_received'] == 0:
            report['recommendations'].extend([
                "Check GPS device power and LED indicators",
                "Verify USB cable and connection",
                "Try different baud rates (9600, 38400, 115200)",
                "Check device permissions and path"
            ])
        elif self.debug_stats['latest_data_updates'] == 0:
            report['recommendations'].extend([
                "Check GPS antenna connection",
                "Move to location with clear sky view",
                "Wait longer for GPS fix (cold start can take 5+ minutes)",
                "Check UBX message configuration",
                "Review GPS device firmware version"
            ])
        
        logger.info(f"\n📋 DEBUG REPORT:")
        logger.info(f"   Duration: {duration:.1f} seconds")
        logger.info(f"   Bytes received: {self.debug_stats['bytes_received']}")
        logger.info(f"   Data updates: {self.debug_stats['latest_data_updates']}")
        logger.info(f"   Errors: {len(self.debug_stats['errors'])}")
        
        for diagnosis in report['diagnosis']:
            logger.info(f"   {diagnosis}")
        
        if report['recommendations']:
            logger.info(f"\n💡 RECOMMENDATIONS:")
            for rec in report['recommendations']:
                logger.info(f"   • {rec}")
        
        return report

async def main():
    """Main debug function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced UBlox GPS debugging')
    parser.add_argument('--duration', type=int, default=60, help='Debug duration in seconds')
    parser.add_argument('--output', help='Output report to JSON file')
    
    args = parser.parse_args()
    
    debugger = EnhancedGPSDebugger()
    report = await debugger.run_comprehensive_debug(args.duration)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"📄 Debug report saved to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
