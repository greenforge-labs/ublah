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
            
            # Start reading data in background (only if not already started)
            if not self.reader_task or self.reader_task.done():
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Creating reader task in start() method")
                # =========================== DEBUG LOGGING END =============================
                self.reader_task = asyncio.create_task(self._read_data_loop())
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.warning("🔍 DEBUG: Reader task already exists, skipping creation")
                # =========================== DEBUG LOGGING END =============================
                
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
        
        logger.info(f"🔌 Connecting to {device_path} @ {baudrate} baud...")
        
        try:
            # Open serial connection
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=device_path,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=2
            )
            
            logger.info(f"✅ Serial port opened at {baudrate} baud")
            
            # Mark as connected BEFORE attempting configuration
            self.connected = True
            
            # Continue with device configuration...
            try:
                # Record successful connection
                self.diagnostics.record_operation("gps_handler", "connect", 1.0, True)
                
                # Configure device (only if we have a connection)
                await self._configure_device()
                
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Device configuration completed, reader task will be created in start() method")
                # =========================== DEBUG LOGGING END =============================
                
                logger.info("GPS handler started successfully")
                
            except Exception as e:
                logger.error(f"Error during GPS configuration: {e}")
                self.diagnostics.record_operation("gps_handler", "connect", 0.0, False, str(e))
                await self.stop()
                raise
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to GPS device: {e}")
            logger.error("❌ Check:")
            logger.error("   - Device path: " + device_path)
            logger.error("   - Hardware connections")
            logger.error("   - Device permissions")
            logger.error("   - GPS device power")
            raise GPSConnectionError("Failed to connect to GPS device")
        
        logger.info(f"🎉 Connected to GPS device at {device_path} @ {baudrate} baud")
        
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
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: Starting to enable UBX messages...")
        # =========================== DEBUG LOGGING END =============================
        
        # Base messages for all devices
        messages_to_enable = [
            ('NAV', 'NAV-PVT', 1),     # Position, velocity, time
            ('NAV', 'NAV-HPPOSLLH', 1), # High precision position
            ('NAV', 'NAV-STATUS', 1),   # Navigation status
            ('NAV', 'NAV-SAT', 1),     # Satellite information
        ]
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info(f"🔍 DEBUG: Will enable {len(messages_to_enable)} base messages")
        # =========================== DEBUG LOGGING END =============================
        
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
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: Enabling {msg_type} at rate {rate}Hz...")
                # =========================== DEBUG LOGGING END =============================
                
                # Get message class and ID
                msg_class_code = self._get_ubx_class_code(msg_class)
                msg_id_code = self._get_ubx_msg_id(msg_type)
                
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: {msg_type} -> Class: 0x{msg_class_code:02X}, ID: 0x{msg_id_code:02X}")
                # =========================== DEBUG LOGGING END =============================
                
                cfg_msg = UBXMessage('CFG', 'CFG-MSG', SET,
                                   msgClass=msg_class_code,
                                   msgID=msg_id_code,
                                   rateUART1=rate)
                await self._send_ubx_message(cfg_msg)
                logger.debug(f"Enabled {msg_type} at rate {rate}Hz")
                
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: Successfully sent enable command for {msg_type}")
                # =========================== DEBUG LOGGING END =============================
                
            except GPSConfigurationError as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                # =========================== DEBUG LOGGING START ===========================
                logger.error(f"🔍 DEBUG: GPSConfigurationError enabling {msg_type}: {e}")
                # =========================== DEBUG LOGGING END =============================
                self.diagnostics.log_error(f"Failed to enable {msg_type}")
            
            except Exception as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                # =========================== DEBUG LOGGING START ===========================
                logger.error(f"🔍 DEBUG: Exception enabling {msg_type}: {e}")
                # =========================== DEBUG LOGGING END =============================
                self.diagnostics.log_error(f"Failed to enable {msg_type}")
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info(f"🔍 DEBUG: UBX message enabling completed. Total sent: {len(messages_to_enable)}")
        logger.info(f"🔍 DEBUG: Waiting 2 seconds for device to start outputting messages...")
        # =========================== DEBUG LOGGING END =============================
        
        # Give device time to start outputting enabled messages
        await asyncio.sleep(2.0)
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info(f"🔍 DEBUG: Device should now be outputting NAV messages at 1Hz")
        logger.info(f"🔍 DEBUG: If no NAV messages appear in logs, check:")
        logger.info(f"🔍 DEBUG:   1. Device may need clear sky view for satellite acquisition")
        logger.info(f"🔍 DEBUG:   2. Indoor reception may be too weak for navigation solution")
        logger.info(f"🔍 DEBUG:   3. Device may need CFG-CFG save command (not implemented)")
        logger.info(f"🔍 DEBUG: Will poll device status if no NAV messages after 10 seconds...")
        # =========================== DEBUG LOGGING END =============================

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
            'NAV-COV': 0x36, 'HNR-PVT': 0x00, 'ESF-INS': 0x15,
            'NAV-SAT': 0x35
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
        """Read and process GPS data continuously with enhanced debugging."""
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: GPS data reading loop started")
        # =========================== DEBUG LOGGING END =============================
        data_received_count = 0
        ubx_message_count = 0
        nav_message_count = 0
        ack_message_count = 0
        
        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout=0.1)
                
                if data:
                    data_received_count += 1
                    
                    # =========================== DEBUG LOGGING START ===========================
                    if data_received_count <= 10 or data_received_count % 100 == 0:
                        logger.info(f"🔍 DEBUG: Raw data chunk #{data_received_count}: {data[:50]}...")
                    # =========================== DEBUG LOGGING END =============================
                    
                    # Process UBX messages if UBX sync bytes found
                    if b'\xb5\x62' in data:
                        # =========================== DEBUG LOGGING START ===========================
                        logger.info(f"🔍 DEBUG: UBX sync detected in chunk #{data_received_count}")
                        # =========================== DEBUG LOGGING END =============================
                        
                        try:
                            from pyubx2 import UBXReader
                            from io import BytesIO
                            
                            reader = UBXReader(BytesIO(data))
                            
                            while True:
                                try:
                                    raw_data, message = reader.read()
                                    if message:
                                        ubx_message_count += 1
                                        
                                        # =========================== DEBUG LOGGING START ===========================
                                        logger.info(f"🔍 DEBUG: Parsed UBX message #{ubx_message_count}: {message.identity}")
                                        
                                        # Track message types for debugging
                                        if message.identity.startswith('NAV-'):
                                            nav_message_count += 1
                                            logger.info(f"🔍 DEBUG: 📡 NAV message #{nav_message_count}: {message.identity}")
                                        elif message.identity.startswith('ACK-'):
                                            ack_message_count += 1
                                            logger.info(f"🔍 DEBUG: ✅ ACK message #{ack_message_count}: {message.identity}")
                                        
                                        # Debug latest_data before and after processing
                                        data_keys_before = list(self.latest_data.keys()) if hasattr(self, 'latest_data') else []
                                        # =========================== DEBUG LOGGING END =============================
                                        
                                        await self._process_ubx_message(message)
                                        
                                        # =========================== DEBUG LOGGING START ===========================
                                        data_keys_after = list(self.latest_data.keys()) if hasattr(self, 'latest_data') else []
                                        if data_keys_before != data_keys_after:
                                            logger.info(f"🔍 DEBUG: latest_data updated! New keys: {set(data_keys_after) - set(data_keys_before)}")
                                        # =========================== DEBUG LOGGING END =============================
                                        
                                    else:
                                        break
                                        
                                except Exception as parse_error:
                                    # =========================== DEBUG LOGGING START ===========================
                                    logger.warning(f"🔍 DEBUG: UBX parse error: {parse_error}")
                                    # =========================== DEBUG LOGGING END =============================
                                    break
                                    
                        except Exception as ubx_error:
                            # =========================== DEBUG LOGGING START ===========================
                            logger.error(f"🔍 DEBUG: UBX processing error: {ubx_error}")
                            # =========================== DEBUG LOGGING END =============================
                    
                    # Process NMEA if found
                    if b'$' in data:
                        await self._process_nmea_data(data)
                
            except asyncio.TimeoutError:
                # No data received, continue
                continue
                
            except Exception as e:
                logger.error(f"Error reading GPS data: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info(f"🔍 DEBUG: GPS data loop ending. Stats:")
        logger.info(f"🔍 DEBUG:   Total data chunks: {data_received_count}")
        logger.info(f"🔍 DEBUG:   Total UBX messages: {ubx_message_count}")
        logger.info(f"🔍 DEBUG:   NAV messages: {nav_message_count}")
        logger.info(f"🔍 DEBUG:   ACK messages: {ack_message_count}")
        # =========================== DEBUG LOGGING END =============================

    async def _process_ubx_message(self, message) -> None:
        """Process incoming UBX message with enhanced ZED-F9R support and error handling."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.info(f"🔍 DEBUG: Processing UBX message: {message.identity}")
            # =========================== DEBUG LOGGING END =============================
            
            if message.identity == 'NAV-PVT':
                await self._process_nav_pvt(message)
                
            elif message.identity == 'NAV-HPPOSLLH':
                await self._process_nav_hpposllh(message)
                
            elif message.identity == 'NAV-STATUS':
                await self._process_nav_status(message)
                
            elif message.identity == 'HNR-PVT':
                await self._process_hnr_pvt(message)
                
            elif message.identity == 'ESF-INS':
                await self._process_esf_ins(message)
                
            elif message.identity == 'NAV-SAT':
                await self._process_nav_sat(message)
                
            elif message.identity == 'ACK-ACK':
                await self._process_ack_ack(message)
                
            elif message.identity == 'ACK-NACK':
                await self._process_ack_nack(message)
                
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: Unhandled UBX message type: {message.identity}")
                # =========================== DEBUG LOGGING END =============================
                logger.debug(f"❓ Unhandled UBX message type: {message.identity}")
            
            # Record successful processing
            self.diagnostics.record_operation("gps_handler", "process_ubx", 1.0, True)
            
        except Exception as e:
            logger.error(f"Error processing UBX message {message.identity}: {e}")
            self.diagnostics.record_operation("gps_handler", "process_ubx", 0.0, False, str(e))

    async def _process_nav_pvt(self, message) -> None:
        """Process NAV-PVT message for standard position data with error handling."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.info(f"🔍 DEBUG: Processing NAV-PVT message")
            # =========================== DEBUG LOGGING END =============================
            
            required_fields = ['iTOW', 'year', 'month', 'day', 'hour', 'min', 'sec', 'valid',
                              'nano', 'fixType', 'flags', 'flags2', 'numSV', 'lon', 'lat', 'height',
                              'hMSL', 'hAcc', 'vAcc', 'velN', 'velE', 'velD', 'gSpeed', 'headMot',
                              'sAcc', 'headAcc', 'pDOP', 'flags3', 'headVeh']
            
            missing_fields = [field for field in required_fields if not hasattr(message, field)]
            if missing_fields:
                # =========================== DEBUG LOGGING START ===========================
                logger.warning(f"🔍 DEBUG: NAV-PVT missing fields: {missing_fields}")
                # =========================== DEBUG LOGGING END =============================
                logger.warning(f"📍 NAV-PVT missing fields: {missing_fields}")
                return
            
            latitude = message.lat / 1e7
            longitude = message.lon / 1e7
            altitude = message.height / 1000.0  # Convert from mm to meters
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info(f"🔍 DEBUG: NAV-PVT extracted data:")
            logger.info(f"🔍 DEBUG:   Latitude: {latitude}")
            logger.info(f"🔍 DEBUG:   Longitude: {longitude}")
            logger.info(f"🔍 DEBUG:   Altitude: {altitude}")
            logger.info(f"🔍 DEBUG:   Fix Type: {message.fixType}")
            logger.info(f"🔍 DEBUG:   Satellites: {message.numSV}")
            logger.info(f"🔍 DEBUG:   H Accuracy: {message.hAcc / 1000.0}")
            # =========================== DEBUG LOGGING END =============================
            
            self.latest_data.update({
                'timestamp': datetime.utcnow(),
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'fix_type': message.fixType,
                'satellites': message.numSV,  # Total satellites (backwards compatibility)
                'satellites_used': message.numSV,  # Satellites used in nav solution
                'horizontal_accuracy': message.hAcc / 1000.0,  # Convert from mm to meters
                'vertical_accuracy': message.vAcc / 1000.0,
                'speed': message.gSpeed / 1000.0,  # Convert from mm/s to m/s
                'heading': message.headMot / 1e5,  # Convert from 1e-5 degrees to degrees
                'pdop': message.pDOP / 100.0,  # Convert from 0.01 to actual value
            })
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info(f"🔍 DEBUG: Updated latest_data with NAV-PVT. Keys: {list(self.latest_data.keys())}")
            # =========================== DEBUG LOGGING END =============================
            
            self.diagnostics.record_operation("gps_handler", "nav_pvt", 1.0, True)
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"🔍 DEBUG: Error processing NAV-PVT: {e}")
            # =========================== DEBUG LOGGING END =============================
            logger.error(f"❌ Error processing NAV-PVT: {e}")
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
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing ESF-INS message: {e}")
            self.diagnostics.log_error("GPS ESF-INS data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing ESF-INS message: {e}")
            self.diagnostics.log_error("GPS ESF-INS data processing error")

    async def _process_nav_hpposllh(self, message) -> None:
        """Process NAV-HPPOSLLH message for high precision position data with error handling."""
        try:
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

    async def _process_nav_sat(self, message) -> None:
        """Process NAV-SAT message for satellite information with error handling."""
        try:
            self.latest_data.update({
                'sat_timestamp': datetime.utcnow(),
                'sat_num_svs': message.numSvs,
                'sat_global_svid': message.globalSvid,
                'sat_reserved1': message.reserved1,
                'sat_reserved2': message.reserved2,
                'sat_svid': message.svid,
                'sat_flags': message.flags,
                'sat_quality': message.quality,
                'sat_cno': message.cno,
                'sat_elev': message.elev,
                'sat_azim': message.azim,
                'sat_prn': message.prn,
            })
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-SAT message: {e}")
            self.diagnostics.log_error("GPS NAV-SAT data validation error")
        
        except Exception as e:
            logger.debug(f"Error processing NAV-SAT message: {e}")
            self.diagnostics.log_error("GPS NAV-SAT data processing error")

    async def _process_ack_ack(self, message) -> None:
        """Process ACK-ACK message for configuration success with error handling."""
        try:
            # Map message class/ID to readable names for better logging
            msg_map = {
                (0x01, 0x07): "NAV-PVT",
                (0x01, 0x14): "NAV-HPPOSLLH", 
                (0x01, 0x03): "NAV-STATUS",
                (0x01, 0x35): "NAV-SAT",
                (0x06, 0x01): "CFG-MSG",
                (0x06, 0x00): "CFG-PRT",
            }
            
            msg_name = msg_map.get((message.clsID, message.msgID), f"0x{message.clsID:02X}-0x{message.msgID:02X}")
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info(f"🔍 DEBUG: ✅ Configuration ACK for {msg_name}")
            # =========================== DEBUG LOGGING END =============================
            
            # Count successful configuration acknowledgments
            if not hasattr(self, 'ack_count'):
                self.ack_count = 0
            self.ack_count += 1
            
            self.diagnostics.record_operation("gps_handler", "config_ack", 1.0, True)
            
        except Exception as e:
            logger.error(f"Error processing ACK-ACK message: {e}")
            self.diagnostics.log_error("GPS ACK-ACK data processing error")

    async def _process_ack_nack(self, message) -> None:
        """Process ACK-NACK message for configuration failure with error handling."""
        try:
            # Map message class/ID to readable names for better logging
            msg_map = {
                (0x01, 0x07): "NAV-PVT",
                (0x01, 0x14): "NAV-HPPOSLLH", 
                (0x01, 0x03): "NAV-STATUS",
                (0x01, 0x35): "NAV-SAT",
                (0x06, 0x01): "CFG-MSG",
                (0x06, 0x00): "CFG-PRT",
            }
            
            msg_name = msg_map.get((message.clsID, message.msgID), f"0x{message.clsID:02X}-0x{message.msgID:02X}")
            
            logger.warning(f"❌ Configuration NACK for {msg_name} - command rejected!")
            self.diagnostics.log_warning(f"ACK-NACK received for {msg_name}")
            
        except Exception as e:
            logger.error(f"Error processing ACK-NACK message: {e}")
            self.diagnostics.log_error("GPS ACK-NACK data processing error")

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
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """Return the latest GPS data with comprehensive debugging."""
        # =========================== DEBUG LOGGING START ===========================
        if hasattr(self, 'latest_data'):
            data_keys = list(self.latest_data.keys())
            logger.info(f"🔍 DEBUG: get_latest_data() called - available keys: {data_keys}")
            
            if data_keys:
                # Show sample of data for key fields
                sample_data = {}
                for key in ['timestamp', 'latitude', 'longitude', 'fix_type', 'satellites', 'satellites_used']:
                    if key in self.latest_data:
                        sample_data[key] = self.latest_data[key]
                logger.info(f"🔍 DEBUG: Sample GPS data: {sample_data}")
            else:
                logger.warning(f"🔍 DEBUG: latest_data exists but is EMPTY!")
                
            return self.latest_data.copy() if self.latest_data else None
        else:
            logger.warning(f"🔍 DEBUG: latest_data attribute DOES NOT EXIST!")
            return None
        # =========================== DEBUG LOGGING END =============================
    
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
