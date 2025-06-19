"""
GPS Handler for ublox GPS devices with enhanced error handling and diagnostics.
Supports ZED-F9P and ZED-F9R devices with comprehensive validation and monitoring.
"""

import asyncio
import logging
import serial_asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pyubx2 import UBXMessage, UBX_MSGIDS, SET
from pynmea2 import parse as nmea_parse
from serial.tools import list_ports
from diagnostics import SystemDiagnostics

logger = logging.getLogger(__name__)

class GPSConnectionError(Exception):
    """GPS connection related errors."""
    pass

class GPSConfigurationError(Exception):
    """GPS configuration related errors."""
    pass

class GPSDataValidationError(Exception):
    """GPS data validation errors."""
    pass

class GPSHandler:
    """Handle GPS communication with enhanced error handling and diagnostics."""
    
    def __init__(self, config):
        self.config = config
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.serial_port: Optional[serial_asyncio.SerialTransport] = None
        self.connected = False
        self.latest_data = {}
        self.reader_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.diagnostics = SystemDiagnostics(self.config)
    
    async def start(self) -> None:
        """Start GPS communication with error handling."""
        logger.info("Starting GPS handler...")
        
        try:
            await self._connect_device()
            await self._configure_device()
            
            # Start reading data in background
            self.reader_task = asyncio.create_task(self._read_data_loop())
            logger.info("GPS handler started successfully")
            
        except GPSConnectionError as e:
            logger.error(f"Failed to connect to GPS device: {e}")
            self.diagnostics.log_error("GPS connection error")
            raise
        
        except GPSConfigurationError as e:
            logger.error(f"Failed to configure GPS device: {e}")
            self.diagnostics.log_error("GPS configuration error")
            raise
        
        except Exception as e:
            logger.error(f"Failed to start GPS handler: {e}")
            self.diagnostics.log_error("GPS handler error")
            raise
    
    async def stop(self) -> None:
        """Stop GPS communication with error handling."""
        logger.info("Stopping GPS handler...")
        
        self._stop_event.set()
        
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("GPS serial port closed")
        
        self.connected = False
        logger.info("GPS handler stopped")
    
    async def _connect_device(self) -> None:
        """Connect to GPS device via serial port with error handling."""
        device_path = self.config.gps_device
        baudrate = self.config.gps_baudrate
        
        try:
            # Check if device exists
            if not self._device_exists(device_path):
                available_ports = self._list_available_ports()
                raise GPSConnectionError(f"GPS device not found at {device_path}. Available ports: {available_ports}")
            
            # Open serial connection
            self.reader, self.writer = await serial_asyncio.open_serial_connection(url=device_path, baudrate=baudrate)
            self.serial_port = self.writer.transport.serial  # Access underlying serial port
            
            self.connected = True
            logger.info(f"Connected to GPS device at {device_path} @ {baudrate} baud")
            
        except GPSConnectionError as e:
            logger.error(f"Failed to connect to GPS device: {e}")
            self.diagnostics.log_error("GPS connection error")
            raise
        
        except Exception as e:
            logger.error(f"Failed to connect to GPS device: {e}")
            self.diagnostics.log_error("GPS connection error")
            raise
    
    def _device_exists(self, device_path: str) -> bool:
        """Check if the specified device path exists."""
        import os
        return os.path.exists(device_path)
    
    def _list_available_ports(self) -> List[str]:
        """List available serial ports."""
        ports = list_ports.comports()
        return [port.device for port in ports]
    
    async def _configure_device(self) -> None:
        """Configure GPS device with enhanced ZED-F9R support and error handling."""
        logger.info(f"Configuring {self.config.device_type} device...")
        
        try:
            # Configure navigation engine for dead reckoning if ZED-F9R
            if self.config.device_type == "ZED-F9R" and self.config.dead_reckoning_enabled:
                await self._configure_navigation_engine()
                await self._configure_dynamic_model()
            
            # Configure message rates and types
            await self._enable_messages()
            
            # Disable NMEA output if requested
            if self.config.disable_nmea_output:
                await self._disable_nmea_output()
            
            logger.info("Device configuration completed")
            
        except GPSConfigurationError as e:
            logger.error(f"Device configuration failed: {e}")
            self.diagnostics.log_error("GPS configuration error")
            raise
        
        except Exception as e:
            logger.error(f"Device configuration failed: {e}")
            self.diagnostics.log_error("GPS configuration error")
            raise

    async def _configure_navigation_engine(self) -> None:
        """Configure UBX-CFG-NAVSPG for dead reckoning support with error handling."""
        logger.info("Configuring navigation engine for dead reckoning...")
        
        try:
            # Configure navigation engine settings
            navspg_msg = UBXMessage('CFG', 'CFG-NAVSPG', SET,
                                   dynModel=self._get_dynamic_model_code(),
                                   fixMode=3,  # Auto 2D/3D
                                   utcStandard=0,  # Automatic
                                   useAdr=1 if self.config.dead_reckoning_enabled else 0)
            await self._send_ubx_message(navspg_msg)
            
        except GPSConfigurationError as e:
            logger.error(f"Failed to configure navigation engine: {e}")
            self.diagnostics.log_error("GPS navigation engine configuration error")
            raise
        
        except Exception as e:
            logger.error(f"Failed to configure navigation engine: {e}")
            self.diagnostics.log_error("GPS navigation engine configuration error")
            raise

    async def _configure_dynamic_model(self) -> None:
        """Configure UBX-CFG-DYNMODEL for application-specific settings with error handling."""
        logger.info(f"Configuring dynamic model: {self.config.dynamic_model_type}")
        
        try:
            model_code = self._get_dynamic_model_code()
            dynmodel_msg = UBXMessage('CFG', 'CFG-DYNMODEL', SET, dynModel=model_code)
            await self._send_ubx_message(dynmodel_msg)
            
        except GPSConfigurationError as e:
            logger.error(f"Failed to configure dynamic model: {e}")
            self.diagnostics.log_error("GPS dynamic model configuration error")
            raise
        
        except Exception as e:
            logger.error(f"Failed to configure dynamic model: {e}")
            self.diagnostics.log_error("GPS dynamic model configuration error")
            raise

    def _get_dynamic_model_code(self) -> int:
        """Get dynamic model code for UBX configuration."""
        dyn_models = {
            'portable': 0, 'stationary': 2, 'pedestrian': 3,
            'automotive': 4, 'sea': 5, 'airborne_1g': 6,
            'airborne_2g': 7, 'airborne_4g': 8, 'wrist': 9
        }
        return dyn_models.get(self.config.dynamic_model_type, 4)  # Default: automotive

    async def _disable_nmea_output(self) -> None:
        """Disable default NMEA message output to reduce data overhead with error handling."""
        logger.info("Disabling NMEA output messages...")
        
        nmea_messages = [
            ('NMEA', 'GGA'), ('NMEA', 'GLL'), ('NMEA', 'GSA'), 
            ('NMEA', 'GSV'), ('NMEA', 'RMC'), ('NMEA', 'VTG')
        ]
        
        for msg_class, msg_type in nmea_messages:
            try:
                cfg_msg = UBXMessage('CFG', 'CFG-MSG', SET,
                                   msgClass=0xF0,  # NMEA class
                                   msgID=self._get_nmea_msg_id(msg_type),
                                   rateUART1=0)  # Disable on UART1
                await self._send_ubx_message(cfg_msg)
            except GPSConfigurationError as e:
                logger.debug(f"Failed to disable {msg_type}: {e}")
                self.diagnostics.log_error(f"Failed to disable {msg_type}")
            
            except Exception as e:
                logger.debug(f"Failed to disable {msg_type}: {e}")
                self.diagnostics.log_error(f"Failed to disable {msg_type}")

    def _get_nmea_msg_id(self, msg_type: str) -> int:
        """Get NMEA message ID for configuration."""
        nmea_ids = {
            'GGA': 0x00, 'GLL': 0x01, 'GSA': 0x02,
            'GSV': 0x03, 'RMC': 0x04, 'VTG': 0x05
        }
        return nmea_ids.get(msg_type, 0x00)

    async def _enable_messages(self) -> None:
        """Enable required UBX messages based on device capabilities with error handling."""
        # Base messages for all devices
        messages_to_enable = [
            ('NAV', 'NAV-PVT', 1),     # Position, velocity, time
            ('NAV', 'NAV-HPPOSLLH', 1), # High precision position
            ('NAV', 'NAV-STATUS', 1),   # Navigation status
        ]
        
        # ZED-F9R specific messages
        if self.config.device_type == "ZED-F9R":
            if self.config.high_rate_positioning:
                # High rate navigation data
                hnr_rate = max(1, min(self.config.hnr_rate_hz, 30))  # Limit to 30Hz
                messages_to_enable.append(('HNR', 'HNR-PVT', hnr_rate))
            
            if self.config.enable_esf_ins:
                messages_to_enable.append(('ESF', 'ESF-INS', 1))
                
            if self.config.enable_nav_cov:
                messages_to_enable.append(('NAV', 'NAV-COV', 1))
        
        for msg_class, msg_type, rate in messages_to_enable:
            try:
                # Get message class and ID
                msg_class_code = self._get_ubx_class_code(msg_class)
                msg_id_code = self._get_ubx_msg_id(msg_type)
                
                cfg_msg = UBXMessage('CFG', 'CFG-MSG', SET,
                                   msgClass=msg_class_code,
                                   msgID=msg_id_code,
                                   rateUART1=rate)
                await self._send_ubx_message(cfg_msg)
                logger.debug(f"Enabled {msg_type} at rate {rate}Hz")
                
            except GPSConfigurationError as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                self.diagnostics.log_error(f"Failed to enable {msg_type}")
            
            except Exception as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                self.diagnostics.log_error(f"Failed to enable {msg_type}")

    def _get_ubx_class_code(self, msg_class: str) -> int:
        """Get UBX message class code."""
        class_codes = {
            'NAV': 0x01, 'RXM': 0x02, 'INF': 0x04, 'ACK': 0x05,
            'CFG': 0x06, 'UPD': 0x09, 'MON': 0x0A, 'AID': 0x0B,
            'TIM': 0x0D, 'ESF': 0x10, 'MGA': 0x13, 'LOG': 0x21,
            'SEC': 0x27, 'HNR': 0x28
        }
        return class_codes.get(msg_class, 0x01)

    def _get_ubx_msg_id(self, msg_type: str) -> int:
        """Get UBX message ID code."""
        msg_ids = {
            'NAV-PVT': 0x07, 'NAV-HPPOSLLH': 0x14, 'NAV-STATUS': 0x03,
            'NAV-COV': 0x36, 'HNR-PVT': 0x00, 'ESF-INS': 0x15
        }
        return msg_ids.get(msg_type, 0x00)
    
    async def _send_ubx_message(self, message: UBXMessage) -> None:
        """Send UBX message to device with error handling."""
        if not self.writer or not self.connected:
            raise GPSConnectionError("GPS device not connected")
        
        try:
            self.writer.write(message.serialize())
            await asyncio.sleep(0.1)  # Small delay for device processing
        except GPSConnectionError as e:
            logger.error(f"Failed to send UBX message: {e}")
            self.diagnostics.log_error("Failed to send UBX message")
            raise
        
        except Exception as e:
            logger.error(f"Failed to send UBX message: {e}")
            self.diagnostics.log_error("Failed to send UBX message")
            raise
    
    async def _read_data_loop(self) -> None:
        """Background task to read GPS data continuously with error handling."""
        
        # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
        logger.info("🔄 Starting GPS data read loop...")
        bytes_received_total = 0
        cycles_with_data = 0
        cycles_without_data = 0
        message_parse_attempts = 0
        successful_updates = 0
        # DEBUG: END - GPS Data Flow Debugging
        
        while not self._stop_event.is_set() and self.connected:
            try:
                if self.reader.at_eof():
                    # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
                    logger.warning("📡 Reader reached EOF - connection may be lost")
                    # DEBUG: END - GPS Data Flow Debugging
                    break
                
                # Read data from stream
                try:
                    # Try to read a chunk of data
                    data = await self.reader.read(1024)
                    if not data:
                        # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
                        cycles_without_data += 1
                        if cycles_without_data % 100 == 0:  # Log every 100 empty cycles
                            logger.debug(f"📡 No data received for {cycles_without_data} cycles")
                        # DEBUG: END - GPS Data Flow Debugging
                        await asyncio.sleep(0.01)
                        continue
                    
                    # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
                    # We got data!
                    cycles_with_data += 1
                    bytes_received_total += len(data)
                    cycles_without_data = 0  # Reset counter
                    
                    # Log data reception every 50 cycles or first few cycles
                    if cycles_with_data <= 5 or cycles_with_data % 50 == 0:
                        logger.info(f"📥 Cycle {cycles_with_data}: Received {len(data)} bytes (total: {bytes_received_total})")
                        logger.debug(f"📥 Data sample: {data[:50].hex()}...")
                    # DEBUG: END - GPS Data Flow Debugging
                    
                    # Process data byte by byte to find UBX messages
                    for byte in data:
                        try:
                            # Look for UBX message start (0xB5, 0x62)
                            if byte == 0xB5:
                                # Potential UBX message start
                                next_byte = await self.reader.read(1)
                                if next_byte and next_byte[0] == 0x62:
                                    # Read message class and ID
                                    header = await self.reader.read(4)
                                    if len(header) == 4:
                                        msg_class, msg_id, length_low, length_high = header
                                        length = length_low + (length_high << 8)
                                        
                                        # Read payload and checksum
                                        payload_and_checksum = await self.reader.read(length + 2)
                                        if len(payload_and_checksum) == length + 2:
                                            # Reconstruct complete UBX message
                                            complete_msg = bytes([0xB5, 0x62]) + header + payload_and_checksum
                                            
                                            # Parse UBX message
                                            try:
                                                from pyubx2 import UBXReader
                                                from io import BytesIO
                                                ubx_reader = UBXReader(BytesIO(complete_msg))
                                                raw_data, parsed_data = ubx_reader.read()
                                                if parsed_data:
                                                    await self._process_ubx_message(parsed_data)
                                                    # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
                                                    successful_updates += 1
                                                    # DEBUG: END - GPS Data Flow Debugging
                                            except Exception as parse_error:
                                                # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
                                                message_parse_attempts += 1
                                                # DEBUG: END - GPS Data Flow Debugging
                                                logger.debug(f"Failed to parse UBX message: {parse_error}")
                            
                            # Check for NMEA message start
                            elif byte == ord('$'):
                                # Read until newline for NMEA message
                                line = b'$'
                                while True:
                                    char_data = await self.reader.read(1)
                                    if not char_data:
                                        break
                                    char = char_data[0]
                                    line += char_data
                                    if char in (ord('\n'), ord('\r')):
                                        break
                                
                                # Process NMEA message
                                try:
                                    line_str = line.decode('ascii', errors='ignore').strip()
                                    if line_str.startswith('$'):
                                        nmea_msg = nmea_parse(line_str)
                                        await self._process_nmea_message(nmea_msg)
                                except Exception as nmea_error:
                                    logger.debug(f"Failed to parse NMEA message: {nmea_error}")
                                    
                        except Exception as byte_error:
                            logger.debug(f"Error processing byte: {byte_error}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Failed to parse message: {e}")
                
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                logger.error(f"Error reading GPS data: {e}")
                self.diagnostics.record_operation("gps_handler", "read_data", 0.0, False, str(e))
                await asyncio.sleep(1)  # Wait before retrying
        
        # DEBUG: START - GPS Data Flow Debugging (Remove after bug is resolved)
        # Log final statistics when loop exits
        logger.info(f"📊 GPS read loop ended - Stats:")
        logger.info(f"   • Cycles with data: {cycles_with_data}")
        logger.info(f"   • Total bytes received: {bytes_received_total}")
        logger.info(f"   • Message parse attempts: {message_parse_attempts}")
        logger.info(f"   • Successful data updates: {successful_updates}")
        logger.info(f"   • Current latest_data keys: {list(self.latest_data.keys())}")
        # DEBUG: END - GPS Data Flow Debugging
    
    async def _process_ubx_message(self, message) -> None:
        """Process incoming UBX message with enhanced ZED-F9R support and error handling."""
        try:
            # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
            logger.debug(f"🛰️ Processing UBX message: {message.identity}")
            # DEBUG: END - Message Processing Debugging
            
            if message.identity == 'NAV-PVT':
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug("📍 Processing NAV-PVT message")
                # DEBUG: END - Message Processing Debugging
                await self._process_nav_pvt(message)
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"📍 NAV-PVT processed, latest_data keys: {list(self.latest_data.keys())}")
                # DEBUG: END - Message Processing Debugging
                
            elif message.identity == 'NAV-HPPOSLLH':
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug("📍 Processing NAV-HPPOSLLH message")
                # DEBUG: END - Message Processing Debugging
                await self._process_nav_hpposllh(message)
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"📍 NAV-HPPOSLLH processed, latest_data keys: {list(self.latest_data.keys())}")
                # DEBUG: END - Message Processing Debugging
                
            elif message.identity == 'NAV-STATUS':
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug("📊 Processing NAV-STATUS message")
                # DEBUG: END - Message Processing Debugging
                await self._process_nav_status(message)
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"📊 NAV-STATUS processed, latest_data keys: {list(self.latest_data.keys())}")
                # DEBUG: END - Message Processing Debugging
                
            elif message.identity == 'HNR-PVT':
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug("🔄 Processing HNR-PVT message")
                # DEBUG: END - Message Processing Debugging
                await self._process_hnr_pvt(message)
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"🔄 HNR-PVT processed, latest_data keys: {list(self.latest_data.keys())}")
                # DEBUG: END - Message Processing Debugging
                
            elif message.identity == 'ESF-INS':
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug("📡 Processing ESF-INS message")
                # DEBUG: END - Message Processing Debugging
                await self._process_esf_ins(message)
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"📡 ESF-INS processed, latest_data keys: {list(self.latest_data.keys())}")
                # DEBUG: END - Message Processing Debugging
                
            else:
                # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
                logger.debug(f"❓ Unhandled UBX message type: {message.identity}")
                # DEBUG: END - Message Processing Debugging
            
            # Record successful processing
            self.diagnostics.record_operation("gps_handler", "process_ubx", 1.0, True)
            
            # DEBUG: START - Message Processing Debugging (Remove after bug is resolved)
            # Log current latest_data summary every 10 messages
            if hasattr(self, '_message_count'):
                self._message_count += 1
            else:
                self._message_count = 1
                
            if self._message_count % 10 == 0:
                logger.info(f"📊 Message #{self._message_count} processed. Current data: {list(self.latest_data.keys())}")
                if self.latest_data:
                    logger.info(f"📊 Sample data: {dict(list(self.latest_data.items())[:3])}")
            # DEBUG: END - Message Processing Debugging
            
        except Exception as e:
            logger.error(f"Error processing UBX message {message.identity}: {e}")
            self.diagnostics.record_operation("gps_handler", "process_ubx", 0.0, False, str(e))

    async def _process_nav_pvt(self, message) -> None:
        """Process NAV-PVT message for standard position data with error handling."""
        try:
            # DEBUG: START - NAV-PVT Processing Debugging (Remove after bug is resolved)
            logger.debug(f"📍 NAV-PVT: fixType={getattr(message, 'fixType', 'unknown')}, numSV={getattr(message, 'numSV', 'unknown')}")
            # DEBUG: END - NAV-PVT Processing Debugging
            
            # Validate message has required fields
            required_fields = ['iTOW', 'year', 'month', 'day', 'hour', 'min', 'sec', 'valid',
                              'nano', 'fixType', 'flags', 'flags2', 'numSV', 'lon', 'lat', 'height',
                              'hMSL', 'hAcc', 'vAcc', 'velN', 'velE', 'velD', 'gSpeed', 'headMot',
                              'sAcc', 'headAcc', 'pDOP', 'flags3', 'headVeh']
            
            missing_fields = [field for field in required_fields if not hasattr(message, field)]
            if missing_fields:
                # DEBUG: START - NAV-PVT Processing Debugging (Remove after bug is resolved)
                logger.warning(f"📍 NAV-PVT missing fields: {missing_fields}")
                # DEBUG: END - NAV-PVT Processing Debugging
                return
            
            # Convert coordinates from 1e-7 degrees to decimal degrees
            latitude = message.lat / 1e7
            longitude = message.lon / 1e7
            altitude = message.height / 1000.0  # Convert from mm to meters
            
            # DEBUG: START - NAV-PVT Processing Debugging (Remove after bug is resolved)
            logger.debug(f"📍 NAV-PVT coordinates: lat={latitude:.7f}, lon={longitude:.7f}, alt={altitude:.3f}m")
            # DEBUG: END - NAV-PVT Processing Debugging
            
            # Update latest_data
            self.latest_data.update({
                'timestamp': datetime.utcnow(),
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'fix_type': message.fixType,
                'satellites': message.numSV,
                'horizontal_accuracy': message.hAcc / 1000.0,  # Convert from mm to meters
                'vertical_accuracy': message.vAcc / 1000.0,
                'speed': message.gSpeed / 1000.0,  # Convert from mm/s to m/s
                'heading': message.headMot / 1e5,  # Convert from 1e-5 degrees to degrees
                'pdop': message.pDOP / 100.0,  # Convert from 0.01 to actual value
            })
            
            # DEBUG: START - NAV-PVT Processing Debugging (Remove after bug is resolved)
            logger.debug(f"📍 NAV-PVT: Updated latest_data with {len(self.latest_data)} fields")
            logger.debug(f"📍 NAV-PVT: Fix type={message.fixType}, Satellites={message.numSV}")
            # DEBUG: END - NAV-PVT Processing Debugging
            
            # Record successful operation
            self.diagnostics.record_operation("gps_handler", "nav_pvt", 1.0, True)
            
        except Exception as e:
            # DEBUG: START - NAV-PVT Processing Debugging (Remove after bug is resolved)
            logger.error(f"❌ Error processing NAV-PVT: {e}")
            # DEBUG: END - NAV-PVT Processing Debugging
            self.diagnostics.record_operation("gps_handler", "nav_pvt", 0.0, False, str(e))

    async def _process_hnr_pvt(self, message) -> None:
        """Process HNR-PVT message for high-rate navigation data with error handling."""
        try:
            self.latest_data.update({
                'hnr_timestamp': datetime.utcnow(),
                'hnr_latitude': message.lat / 1e7,
                'hnr_longitude': message.lon / 1e7,
                'hnr_altitude': message.hMSL / 1000.0,
                'hnr_speed': message.gSpeed / 1000.0,
                'hnr_heading': message.headMot / 1e5,
                'hnr_valid': bool(message.flags & 0x01),  # Valid flag
                'hnr_gps_fix_ok': bool(message.flags & 0x02),  # GPS fix OK
                'hnr_diff_soln': bool(message.flags & 0x04),  # Differential solution
                'hnr_wkn_set': bool(message.flags & 0x08),  # Week number set
                'hnr_tow_set': bool(message.flags & 0x10),  # Time of week set
            })
            
            logger.debug(f"HNR-PVT: lat={message.lat/1e7:.8f}, lon={message.lon/1e7:.8f}, spd={message.gSpeed/1000.0:.2f}m/s")
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing HNR-PVT message: {e}")
            self.diagnostics.log_error("GPS HNR-PVT data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing HNR-PVT message: {e}")
            self.diagnostics.log_error("GPS HNR-PVT data processing error")

    async def _process_esf_ins(self, message) -> None:
        """Process ESF-INS message for inertial sensor fusion data with error handling."""
        try:
            self.latest_data.update({
                'fusion_timestamp': datetime.utcnow(),
                'fusion_version': getattr(message, 'version', 0),
                'fusion_x_ang_rate': getattr(message, 'xAngRate', 0),  # deg/s
                'fusion_y_ang_rate': getattr(message, 'yAngRate', 0),
                'fusion_z_ang_rate': getattr(message, 'zAngRate', 0),
                'fusion_x_accel': getattr(message, 'xAccel', 0),      # m/s²
                'fusion_y_accel': getattr(message, 'yAccel', 0),
                'fusion_z_accel': getattr(message, 'zAccel', 0),
                'fusion_comp_age': getattr(message, 'compAge', 255),   # Compensation age
                'fusion_ins_fix_type': getattr(message, 'insFixType', 0),
            })
            
            logger.debug(f"ESF-INS: ax={getattr(message, 'xAccel', 0):.3f}, ay={getattr(message, 'yAccel', 0):.3f}, az={getattr(message, 'zAccel', 0):.3f}")
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing ESF-INS message: {e}")
            self.diagnostics.log_error("GPS ESF-INS data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing ESF-INS message: {e}")
            self.diagnostics.log_error("GPS ESF-INS data processing error")

    async def _process_nav_hpposllh(self, message) -> None:
        """Process NAV-HPPOSLLH message for high precision position data with error handling."""
        try:
            # Combine standard and high precision parts
            hp_lat = (message.lat + message.latHp * 1e-2) / 1e7
            hp_lon = (message.lon + message.lonHp * 1e-2) / 1e7
            hp_height = (message.height + message.heightHp * 1e-1) / 1000.0
            hp_hmsl = (message.hMSL + message.hMSLHp * 1e-1) / 1000.0
            
            self.latest_data.update({
                'hp_timestamp': datetime.utcnow(),
                'hp_latitude': hp_lat,
                'hp_longitude': hp_lon,
                'hp_height': hp_height,
                'hp_hmsl': hp_hmsl,
                'hp_horizontal_accuracy': message.hAcc / 10000.0,  # Convert 0.1mm to m
                'hp_vertical_accuracy': message.vAcc / 10000.0,
                'hp_flags': message.flags,
                'hp_invalid_llh': bool(message.flags & 0x01),
            })
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-HPPOSLLH message: {e}")
            self.diagnostics.log_error("GPS NAV-HPPOSLLH data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing NAV-HPPOSLLH message: {e}")
            self.diagnostics.log_error("GPS NAV-HPPOSLLH data processing error")

    async def _process_nav_status(self, message) -> None:
        """Process NAV-STATUS message for navigation status information with error handling."""
        try:
            self.latest_data.update({
                'nav_status_timestamp': datetime.utcnow(),
                'gps_fix': message.gpsFix,
                'fix_stat_flags': message.flags,
                'fix_stat': message.fixStat,
                'flags2': message.flags2,
                'ttff': message.ttff,  # Time to first fix (ms)
                'msss': message.msss,  # Time since startup (ms)
                'map_matching': bool(message.flags2 & 0x40),  # Map matching status
                'differential_corrections': bool(message.flags & 0x02),
                'week_number_valid': bool(message.flags & 0x04),
                'time_of_week_valid': bool(message.flags & 0x08),
            })
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-STATUS message: {e}")
            self.diagnostics.log_error("GPS NAV-STATUS data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing NAV-STATUS message: {e}")
            self.diagnostics.log_error("GPS NAV-STATUS data processing error")

    async def _process_nav_cov(self, message) -> None:
        """Process NAV-COV message for covariance matrix data with error handling."""
        try:
            self.latest_data.update({
                'cov_timestamp': datetime.utcnow(),
                'cov_pos_xx': getattr(message, 'posCovNN', 0),
                'cov_pos_yy': getattr(message, 'posCovEE', 0),
                'cov_pos_zz': getattr(message, 'posCovDD', 0),
                'cov_pos_xy': getattr(message, 'posCovNE', 0),
                'cov_pos_xz': getattr(message, 'posCovND', 0),
                'cov_pos_yz': getattr(message, 'posCovED', 0),
            })
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-COV message: {e}")
            self.diagnostics.log_error("GPS NAV-COV data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing NAV-COV message: {e}")
            self.diagnostics.log_error("GPS NAV-COV data processing error")

    def _get_fix_type_name(self, fix_type: int, carr_soln: int = 0) -> str:
        """Convert numeric fix type to readable name with RTK status."""
        base_fix_types = {
            0: "No Fix",
            1: "Dead Reckoning",
            2: "2D Fix",
            3: "3D Fix",
            4: "GNSS + Dead Reckoning",
            5: "Time Only Fix"
        }
        
        base_name = base_fix_types.get(fix_type, f"Unknown ({fix_type})")
        
        # Enhanced RTK detection for high-precision applications
        if fix_type == 3:  # 3D Fix
            if carr_soln == 1:
                return "RTK Float"
            elif carr_soln == 2:
                return "RTK Fixed"
        elif fix_type == 4:  # GNSS + Dead Reckoning
            if carr_soln == 1:
                return "RTK Float + DR"
            elif carr_soln == 2:
                return "RTK Fixed + DR"
        
        return base_name

    async def _process_nmea_message(self, message) -> None:
        """Process incoming NMEA message with error handling."""
        try:
            if hasattr(message, 'sentence_type'):
                if message.sentence_type == 'GGA':
                    # Global Positioning System Fix Data
                    self.latest_data.update({
                        'timestamp': datetime.utcnow(),
                        'latitude': message.latitude,
                        'longitude': message.longitude,
                        'altitude': message.altitude,
                        'satellites': message.num_sats,
                        'hdop': message.horizontal_dil,
                        'fix_quality': message.gps_qual,
                    })
                    
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NMEA message: {e}")
            self.diagnostics.log_error("GPS NMEA data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing NMEA message: {e}")
            self.diagnostics.log_error("GPS NMEA data processing error")
    
    async def get_latest_data(self) -> Dict[str, Any]:
        """Get the latest GPS data."""
        return self.latest_data.copy()
    
    def is_connected(self) -> bool:
        """Check if GPS device is connected."""
        return self.connected and self.writer and not self.writer.is_closing()
    
    async def send_corrections(self, rtcm_data: bytes) -> None:
        """Send RTCM correction data to GPS device with error handling."""
        if not self.writer or not self.connected:
            logger.warning("Cannot send corrections: GPS device not connected")
            return
        
        try:
            self.writer.write(rtcm_data)
            logger.debug(f"Sent {len(rtcm_data)} bytes of RTCM corrections")
        except GPSConnectionError as e:
            logger.error(f"Failed to send RTCM corrections: {e}")
            self.diagnostics.log_error("Failed to send RTCM corrections")
        
        except Exception as e:
            logger.error(f"Failed to send RTCM corrections: {e}")
            self.diagnostics.log_error("Failed to send RTCM corrections")
