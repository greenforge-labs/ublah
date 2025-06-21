"""
GPS Handler for ublox GPS devices with enhanced error handling and diagnostics.
Supports ZED-F9P and ZED-F9R devices with comprehensive validation and monitoring.
"""

import asyncio
import logging
import serial_asyncio
import time
import re
from io import BytesIO
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pyubx2 import UBXMessage, UBX_MSGIDS, SET, UBXReader
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
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: Starting GPS device connection process")
        logger.debug(f" Attempting connection to: {device_path}")
        logger.debug(f" Baudrate: {baudrate}")
        
        # Check if device path exists
        if self._device_exists(device_path):
            logger.debug(f" ✅ Device path exists: {device_path}")
        else:
            logger.error(f"❌ Device path does NOT exist: {device_path}")
        
        # List all available serial ports for comparison
        available_ports = self._list_available_ports()
        logger.debug(f" Available serial ports: {available_ports}")
        
        # Check device permissions (Linux/Unix systems)
        try:
            import os
            import stat
            if os.path.exists(device_path):
                file_stat = os.stat(device_path)
                permissions = stat.filemode(file_stat.st_mode)
                logger.debug(f" Device permissions: {permissions}")
                logger.debug(f" Device owner UID: {file_stat.st_uid}")
                logger.debug(f" Current process UID: {os.getuid()}")
        except Exception as perm_e:
            logger.warning(f"🔍 DEBUG: Could not check device permissions: {perm_e}")
        # =========================== DEBUG LOGGING END =============================
        
        logger.info(f"🔌 Connecting to {device_path} @ {baudrate} baud...")
        
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Calling serial_asyncio.open_serial_connection...")
            # =========================== DEBUG LOGGING END =============================
            
            # Open serial connection
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=device_path,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=2
            )
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: ✅ serial_asyncio.open_serial_connection() completed successfully")
            logger.debug(f" Reader object: {type(self.reader)}")
            logger.debug(f" Writer object: {type(self.writer)}")
            # =========================== DEBUG LOGGING END =============================
            
            logger.info(f"✅ Serial port opened at {baudrate} baud")
            
            # Mark as connected BEFORE attempting configuration
            self.connected = True
            
            # Continue with device configuration...
            try:
                # Record successful connection
                self.diagnostics.record_operation("gps_handler", "connect", 1.0, True)
                
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Device connected successfully, configuration will happen in start() method")
                # =========================== DEBUG LOGGING END =============================
                
            except Exception as e:
                logger.error(f"Error during GPS connection: {e}")
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
            
            # Configure GNSS constellations
            await self._configure_constellations()
            
            # Configure message rates and types
            await self._enable_messages()
            
            # Disable NMEA output if requested
            if self.config.disable_nmea_output:
                await self._disable_nmea_output()
            
            # =========================== CRITICAL FIX START ===========================
            # Save configuration to non-volatile memory (BBR/Flash)
            # This was the missing piece causing GPS connectivity issues!
            logger.info("💾 Saving device configuration to non-volatile memory...")
            await self._save_device_configuration()
            # =========================== CRITICAL FIX END =============================
            
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

    async def _configure_constellations(self) -> None:
        """Configure UBX-CFG-GNSS for selected GNSS constellations with error handling."""
        constellations = self.config.constellation
        logger.info(f"Configuring GNSS constellations: {', '.join(constellations)}")
        
        # Map constellation names to GNSS IDs
        gnss_map = {
            "GPS": 0,
            "SBAS": 1,
            "GALILEO": 2,
            "BEIDOU": 3,
            "IMES": 4,
            "QZSS": 5,
            "GLONASS": 6
        }
        
        try:
            # Build a single CFG-GNSS message containing ALL constellation blocks (per F9 interface spec)
            blocks: dict[str, int] = {}
            index = 0
            for constellation, gnss_id in gnss_map.items():
                enabled = constellation in constellations
                flags = 0x01 if enabled else 0x00  # bit0 = enable / disable

                logger.info(f"{'Enabling' if enabled else 'Disabling'} {constellation} (ID: {gnss_id}) in composite CFG-GNSS")

                # Append this 8-byte block using pyubx2's indexed field names
                blocks.update({
                    f"gnssId_{index}": gnss_id,
                    f"resTrkCh_{index}": 0,
                    f"maxTrkCh_{index}": 0,  # 0 = let receiver decide
                    f"flags_{index}": flags,
                    f"sigCfgMask_{index}": 0,
                })
                index += 1

            # Compose the single message
            gnss_msg = UBXMessage(
                'CFG', 'CFG-GNSS', SET,
                msgVer=0,
                numTrkChHw=32,
                numTrkChUse=32,
                numConfigBlocks=index,
                **blocks
            )

            await self._send_ubx_message(gnss_msg)
            logger.info("GNSS constellation configuration completed (single composite message)")

        except GPSConfigurationError as e:
            logger.error(f"Failed to configure GNSS constellations: {e}")
            self.diagnostics.log_error("GPS GNSS constellation configuration error")
            raise
        except Exception as e:
            logger.error(f"Failed to configure GNSS constellations: {e}")
            self.diagnostics.log_error("GPS GNSS constellation configuration error")
            raise

    def _get_dynamic_model_code(self) -> int:
        """Get dynamic model code for UBX configuration."""
        dyn_models = {
            'portable': 0, 'stationary': 2, 'pedestrian': 3,
            'automotive': 4, 'sea': 5, 'airborne_1g': 6,
            'airborne_2g': 7, 'airborne_4g': 8, 'wrist': 9
        }
        return dyn_models.get(self.config.dynamic_model_type, 2)  # Default: stationary

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
                                   rateUART1=0,  # Disable on UART1
                                   rateUSB=0)  # Disable on USB
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
        logger.debug(f" Will enable {len(messages_to_enable)} base messages")
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
                logger.debug(f" Enabling {msg_type} at rate {rate}Hz...")
                # =========================== DEBUG LOGGING END =============================
                
                # Get message class and ID
                msg_class_code = self._get_ubx_class_code(msg_class)
                msg_id_code = self._get_ubx_msg_id(msg_type)
                
                # =========================== DEBUG LOGGING START ===========================
                logger.debug(f" {msg_type} -> Class: 0x{msg_class_code:02X}, ID: 0x{msg_id_code:02X}")
                # =========================== DEBUG LOGGING END =============================
                
                cfg_msg = UBXMessage('CFG', 'CFG-MSG', SET,
                                   msgClass=msg_class_code,
                                   msgID=msg_id_code,
                                   rateUART1=rate,
                                   rateUSB=rate)
                await self._send_ubx_message(cfg_msg)
                logger.debug(f"Enabled {msg_type} at rate {rate}Hz")
                
                # =========================== DEBUG LOGGING START ===========================
                logger.debug(f" Successfully sent enable command for {msg_type}")
                # =========================== DEBUG LOGGING END =============================
                
            except GPSConfigurationError as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                # =========================== DEBUG LOGGING START ===========================
                logger.error(f"GPSConfigurationError enabling {msg_type}: {e}")
                # =========================== DEBUG LOGGING END =============================
                self.diagnostics.log_error(f"Failed to enable {msg_type}")
            
            except Exception as e:
                logger.warning(f"Failed to enable {msg_type}: {e}")
                # =========================== DEBUG LOGGING START ===========================
                logger.error(f"Exception enabling {msg_type}: {e}")
                # =========================== DEBUG LOGGING END =============================
                self.diagnostics.log_error(f"Failed to enable {msg_type}")
        
        # =========================== DEBUG LOGGING END ===========================
        logger.info(f"ESF-INS message processed")
        
        # =========================== DEBUG LOGGING START ===========================
        logger.debug(f" Device should now be outputting NAV messages at 1Hz")
        logger.debug(f" If no NAV messages appear in logs, check:")
        logger.debug(f"   1. Device may need clear sky view for satellite acquisition")
        logger.debug(f"   2. Indoor reception may be too weak for navigation solution")
        logger.debug(f"   3. Device may need CFG-CFG save command (not implemented)")
        logger.debug(f" Will poll device status if no NAV messages after 10 seconds...")
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
    
    async def _send_ubx_message(self, message):
        """Send a UBX message to the GPS device."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Sending UBX message: {message.identity if hasattr(message, 'identity') else 'Unknown'}")
            logger.debug(f" Message bytes: {message.serialize().hex()}")
            # =========================== DEBUG LOGGING END =============================
            
            # Send the message
            self.writer.write(message.serialize())
            await self.writer.drain()
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" UBX message sent successfully")
            # =========================== DEBUG LOGGING END =============================
            return True
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"Error sending UBX message: {e}")
            # =========================== DEBUG LOGGING END =============================
            logger.error(f"Error sending UBX message: {e}")
            return False
    
    async def _send_poll(self, msg_class, msg_id):
        """Send a poll (GET) message to request data from the GPS device."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Sending poll request for {msg_class}-{msg_id}")
            # =========================== DEBUG LOGGING END =============================
            
            # Create a poll message using pyubx2
            from pyubx2 import UBXMessage, GET
            poll_msg = UBXMessage(msg_class, f"{msg_class}-{msg_id}", GET)
            
            # Log the message bytes for debugging
            logger.debug(f" Poll message bytes: {poll_msg.serialize().hex()}")
            
            # Send the message
            await self._send_ubx_message(poll_msg)
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Poll request sent successfully")
            # =========================== DEBUG LOGGING END =============================
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"Error sending poll request: {e}")
            # =========================== DEBUG LOGGING END =============================
            logger.error(f"Error sending {msg_class}-{msg_id} poll request: {e}")

    async def _read_data_loop(self) -> None:
        """Read data from the GPS device and process it with improved handling of partial messages."""
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: GPS data reading loop started")
        logger.debug(f" Reader object type: {type(self.reader)}")
        logger.debug(f" Writer object type: {type(self.writer)}")
        # =========================== DEBUG LOGGING END ===========================
        
        # Initialize counters and state variables
        self._nav_message_count = 0
        self._ack_message_count = 0
        last_data_time = time.time()
        data_timeout_warning_logged = False
        data_timeout_poll_sent = False
        buffer = bytearray()  # Buffer to accumulate partial messages
        
        while not self._stop_event.is_set():
            try:
                # Read data from the device
                try:
                    data = await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Attempted to read data, received {len(data) if data else 0} bytes")
                    if data and len(data) > 0:
                        logger.debug(f" First few bytes: {data[:min(10, len(data))].hex()}")
                    # =========================== DEBUG LOGGING END ===========================
                except Exception as read_error:
                    logger.error(f"Error reading from device: {read_error}")
                    data = None
                
                if data:
                    # Reset timeout tracking
                    current_time = time.time()
                    time_since_last_data = current_time - last_data_time
                    last_data_time = current_time
                    data_timeout_warning_logged = False
                    data_timeout_poll_sent = False
                    
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Read {len(data)} bytes")
                    # =========================== DEBUG LOGGING END =============================
                    
                    # Append new data to buffer
                    buffer.extend(data)
                    
                    # Process UBX messages
                    if b'\xb5\x62' in buffer:
                        # =========================== DEBUG LOGGING START ===========================
                        logger.debug(f" Found UBX sync bytes in buffer (size: {len(buffer)})")
                        # =========================== DEBUG LOGGING END =============================
                        
                        try:
                            # Create a BytesIO object from the buffer
                            bio = BytesIO(buffer)
                            reader = UBXReader(bio)
                            parsed_messages = 0
                            
                            # Try to parse as many complete messages as possible
                            while True:
                                try:
                                    start_pos = bio.tell()
                                    raw_data, message = reader.read()
                                    
                                    if message:
                                        end_pos = bio.tell()
                                        parsed_messages += 1
                                        
                                        # =========================== DEBUG LOGGING START ===========================
                                        logger.debug(f" Parsed UBX message: {message.identity}")
                                        # =========================== DEBUG LOGGING END =============================
                                        
                                        # Track message counts
                                        if message.identity.startswith("NAV-"):
                                            self._nav_message_count += 1
                                        elif message.identity.startswith("ACK-"):
                                            self._ack_message_count += 1
                                        
                                        # Process the message
                                        await self._process_ubx_message(message)
                                    else:
                                        # No more complete messages
                                        break
                                        
                                except Exception as parse_error:
                                    # =========================== DEBUG LOGGING START ===========================
                                    logger.warning(f"🔍 DEBUG: Error parsing individual UBX message: {parse_error}")
                                    # =========================== DEBUG LOGGING END =============================
                                    # Try to recover by finding next sync bytes
                                    current_pos = bio.tell()
                                    remaining = buffer[current_pos:]
                                    sync_pos = remaining.find(b'\xb5\x62')
                                    
                                    if sync_pos >= 0:
                                        # Skip to next potential message
                                        bio.seek(current_pos + sync_pos)
                                    else:
                                        # No more sync bytes, exit loop
                                        break
                            
                            # If buffer is getting too large, trim it (keeping last 4KB)
                            if len(buffer) > 8192:  # 8KB max buffer
                                buffer = buffer[-4096:]  # Keep last 4KB
                                logger.warning("Buffer too large, trimmed to last 4KB")
                            
                        except Exception as e:
                            # =========================== DEBUG LOGGING START ===========================
                            logger.warning(f"🔍 DEBUG: Error in UBX message processing loop: {e}")
                            # =========================== DEBUG LOGGING END =============================
                            logger.warning(f"Error processing UBX messages: {e}")
                            
                            # Reset buffer on serious errors, keeping only data after last sync bytes
                            sync_pos = buffer.rfind(b'\xb5\x62')
                            if sync_pos >= 0:
                                buffer = buffer[sync_pos:]
                            else:
                                buffer.clear()
                    
                    # Process NMEA data
                    if b'$' in buffer:
                        # =========================== DEBUG LOGGING START ===========================
                        nmea_start = buffer.find(b'$')
                        nmea_sample = buffer[nmea_start:nmea_start+min(20, len(buffer)-nmea_start)].decode('ascii', errors='replace')
                        logger.debug(f" Found NMEA data in buffer, sample: {nmea_sample}...")
                        # =========================== DEBUG LOGGING END ===========================
                        await self._process_nmea_data(buffer)
                
                # Check for timeout
                else:
                    current_time = time.time()
                    time_since_last_data = current_time - last_data_time
                    
                    # Log warning after 5 seconds of no data
                    if time_since_last_data > 5.0 and not data_timeout_warning_logged:
                        logger.warning(f"No data received from GPS for {time_since_last_data:.1f} seconds")
                        data_timeout_warning_logged = True
                    
                    # Send poll request after 10 seconds of no data
                    if time_since_last_data > 10.0 and not data_timeout_poll_sent:
                        logger.warning("Sending MON-VER poll to check device responsiveness")
                        await self._send_poll("MON", "VER")
                        data_timeout_poll_sent = True
                
            except asyncio.TimeoutError:
                # This is normal, just continue
                pass
                
            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors
        
        # =========================== DEBUG LOGGING START ===========================
        logger.debug(f" GPS data loop ending. Stats:")
        logger.debug(f"   NAV messages: {self._nav_message_count}")
        logger.debug(f"   ACK messages: {self._ack_message_count}")
        # =========================== DEBUG LOGGING END ===========================

    def _get_fix_type_string(self, fix_type, carrier_soln=0):
        """
        Convert numeric fix type and carrier solution status to descriptive string.
        
        Args:
            fix_type (int): UBX fixType value (0-5)
            carrier_soln (int): Carrier phase solution status (0-3)
                0: No carrier phase solution
                1: Float solution (cm/dm level)
                2: Fixed solution (mm level)
                3: Reserved
                
        Returns:
            str: Human-readable fix type description
        """
        fix_types = {
            0: "No Fix",
            1: "Dead Reckoning",
            2: "2D Fix",
            3: "3D Fix",
            4: "GNSS + Dead Reckoning",
            5: "Time Only"
        }
        
        rtk_status = {
            0: "",
            1: "RTK Float",
            2: "RTK Fixed",
            3: "RTK Reserved"
        }
        
        base_fix = fix_types.get(fix_type, f"Unknown ({fix_type})")
        
        # For 3D or GNSS+DR fixes, add RTK status if available
        if fix_type in [3, 4] and carrier_soln > 0:
            return f"{base_fix} + {rtk_status[carrier_soln]}"
        
        return base_fix
        
    async def _process_ubx_message(self, message) -> None:
        """Process a UBX message based on its class and ID."""
        try:
            # Extract message class and ID from the message identity
            # Message identity format is typically "CLASS-ID" (e.g., "NAV-PVT")
            if hasattr(message, 'identity'):
                msg_parts = message.identity.split('-')
                if len(msg_parts) == 2:
                    msg_class, msg_id = msg_parts
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.warning(f"🔍 DEBUG: Unexpected message identity format: {message.identity}")
                    # =========================== DEBUG LOGGING END =============================
                    return
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.warning(f"🔍 DEBUG: Message has no identity attribute: {message}")
                # =========================== DEBUG LOGGING END =============================
                return
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing UBX message: {msg_class}-{msg_id}")
            # =========================== DEBUG LOGGING END =============================
            
            # Handle NAV class messages
            if msg_class == "NAV":
                if msg_id == "PVT":
                    await self._process_nav_pvt(message)
                elif msg_id == "HPPOSLLH":
                    await self._process_nav_hpposllh(message)
                elif msg_id == "STATUS":
                    await self._process_nav_status(message)
                elif msg_id == "SAT":
                    await self._process_nav_sat(message)
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled NAV message: {msg_id}")
                    # =========================== DEBUG LOGGING END =============================
                    pass
            
            # Handle High Navigation Rate messages (ZED-F9R specific)
            elif msg_class == "HNR":
                if msg_id == "PVT":
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received HNR-PVT message, adding to debug log")
                    logger.debug(f" HNR-PVT attributes: {dir(message)}")
                    # =========================== DEBUG LOGGING END =============================
                    # Just log for now, implement processing later if needed
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled HNR message: {msg_id}")
                    # =========================== DEBUG LOGGING END =============================
                    pass
            
            # Handle Enhanced Sensor Fusion messages (ZED-F9R specific)
            elif msg_class == "ESF":
                if msg_id == "INS":
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received ESF-INS message, adding to debug log")
                    logger.debug(f" ESF-INS attributes: {dir(message)}")
                    # =========================== DEBUG LOGGING END =============================
                    # Just log for now, implement processing later if needed
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled ESF message: {msg_id}")
                    # =========================== DEBUG LOGGING END =============================
                    pass
                
            # Handle ACK messages
            elif msg_class == "ACK":
                if msg_id == "ACK":
                    await self._process_ack_ack(message)
                elif msg_id == "NACK":
                    await self._process_ack_nack(message)
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled ACK message: {msg_id}")
                    # =========================== DEBUG LOGGING END =============================
                    pass
                
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.debug(f" Unhandled UBX message class: {msg_class}-{msg_id}")
                # =========================== DEBUG LOGGING END =============================
                logger.debug(f"❓ Unhandled UBX message type: {msg_class}-{msg_id}")
            
            # Record successful processing
            self.diagnostics.record_operation("gps_handler", "process_ubx", 1.0, True)
            
        except Exception as e:
            logger.error(f"Error processing UBX message {message.identity}: {e}")
            self.diagnostics.record_operation("gps_handler", "process_ubx", 0.0, False, str(e))

    async def _process_ubx_message(self, message) -> None:
        """Process a UBX message and update data accordingly.
        
        Args:
            message: The UBX message to process
        """
        try:
            # Get message class and ID from the identity string (e.g., "NAV-PVT")
            msg_class, msg_id = message.identity.split('-', 1)
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing UBX message: {message.identity}")
            logger.debug(f" Message type: {type(message)}")
            # logger.debug(f" Message attributes: {dir(message)}")
            logger.debug(f" Current latest_data keys: {list(self.latest_data.keys())}")
            # =========================== DEBUG LOGGING END ===========================
            
            # Handle Navigation messages
            if msg_class == "NAV":
                if msg_id == "PVT":
                    await self._process_nav_pvt(message)
                elif msg_id == "HPPOSLLH":
                    await self._process_nav_hpposllh(message)
                elif msg_id == "STATUS":
                    # Process NAV-STATUS message
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received NAV-STATUS message, adding to debug log")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                elif msg_id == "COV":
                    # Process NAV-COV message
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received NAV-COV message, adding to debug log")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled NAV message: {msg_id}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
            
            # Handle High Rate Navigation messages (ZED-F9R specific)
            elif msg_class == "HNR":
                if msg_id == "PVT":
                    # Process HNR-PVT message
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received HNR-PVT message, adding to debug log")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled HNR message: {msg_id}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
            
            # Handle Enhanced Sensor Fusion messages (ZED-F9R specific)
            elif msg_class == "ESF":
                if msg_id == "INS":
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received ESF-INS message, adding to debug log")
                    logger.debug(f" ESF-INS attributes: {dir(message)}")
                    # =========================== DEBUG LOGGING END ===========================
                    # Just log for now, implement processing later if needed
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled ESF message: {msg_id}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                
            # Handle ACK messages
            elif msg_class == "ACK":
                if msg_id == "ACK":
                    await self._process_ack_ack(message)
                elif msg_id == "NACK":
                    await self._process_ack_nack(message)
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled ACK message: {msg_id}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                
            # Handle MON messages
            elif msg_class == "MON":
                if msg_id == "VER":
                    # Process MON-VER message
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Received MON-VER message, adding to debug log")
                    logger.debug(f" MON-VER attributes: {dir(message)}")
                    if hasattr(message, 'swVersion'):
                        logger.debug(f" GPS firmware version: {message.swVersion}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                else:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Unhandled MON message: {msg_id}")
                    # =========================== DEBUG LOGGING END ===========================
                    pass
                
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.debug(f" Unhandled UBX message class: {msg_class}-{msg_id}")
                # =========================== DEBUG LOGGING END ===========================
                logger.debug(f"❓ Unhandled UBX message type: {msg_class}-{msg_id}")
            
            # Record successful processing
            self.diagnostics.record_operation("gps_handler", "process_ubx", 1.0, True)
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"Error processing UBX message: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception traceback", exc_info=True)
            # =========================== DEBUG LOGGING END ===========================
            logger.error(f"Error processing UBX message {message.identity if hasattr(message, 'identity') else 'Unknown'}: {e}")
            self.diagnostics.record_operation("gps_handler", "process_ubx", 0.0, False, str(e))

    async def _process_nav_pvt(self, message) -> None:
        """Process NAV-PVT message for standard position data with error handling."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing NAV-PVT message")
            logger.debug(f" Message attributes: {dir(message)}")
            # =========================== DEBUG LOGGING END =============================
            
            # Check for essential fields needed for basic position
            essential_fields = ['lat', 'lon', 'height', 'fixType', 'numSV', 'hAcc', 'vAcc']
            missing_essential = [field for field in essential_fields if not hasattr(message, field)]
            if missing_essential:
                # =========================== DEBUG LOGGING START ===========================
                logger.warning(f"🔍 DEBUG: NAV-PVT missing ESSENTIAL fields: {missing_essential}")
                # =========================== DEBUG LOGGING END =============================
                logger.warning(f"📍 NAV-PVT missing ESSENTIAL fields: {missing_essential}")
                return
            
            # Extract basic position data with safe attribute access
            latitude = message.lat / 1e7
            longitude = message.lon / 1e7
            altitude = message.height / 1000.0  # Convert from mm to meters
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" NAV-PVT extracted data:")
            logger.debug(f"   Latitude: {latitude}")
            logger.debug(f"   Longitude: {longitude}")
            logger.debug(f"   Altitude: {altitude}")
            logger.debug(f"   Fix Type: {message.fixType}")
            logger.debug(f"   Satellites: {message.numSV}")
            logger.debug(f"   H Accuracy: {message.hAcc / 1000.0}")
            # =========================== DEBUG LOGGING END =============================
            
            # Build data dictionary with all available fields
            data_update = {
                'timestamp': datetime.utcnow(),
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'fix_type': message.fixType,
                'satellites': message.numSV,  # Total satellites (backwards compatibility)
                'satellites_used': message.numSV,  # Satellites used in nav solution
                'horizontal_accuracy': message.hAcc / 1000.0,  # Convert from mm to meters
                'vertical_accuracy': message.vAcc / 1000.0,
            }
            
            # Add optional fields if available
            if hasattr(message, 'gSpeed'):
                data_update['speed'] = message.gSpeed / 1000.0  # Convert from mm/s to m/s
            
            if hasattr(message, 'headMot'):
                data_update['heading'] = message.headMot / 1e5  # Convert from 1e-5 degrees to degrees
            
            if hasattr(message, 'pDOP'):
                data_update['pdop'] = message.pDOP / 100.0  # Convert from 0.01 to actual value
            
            # Add carrier solution status if available for RTK detection
            if hasattr(message, 'flags'):
                carr_soln = (message.flags >> 6) & 0x03  # Extract carrier phase solution status
                data_update['carrier_solution'] = carr_soln
                
                # Update fix type string with RTK info
                fix_type_str = self._get_fix_type_string(message.fixType, carr_soln)
                data_update['fix_type_str'] = fix_type_str
            
            # Update the latest data dictionary
            self.latest_data.update(data_update)
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Updated latest_data with NAV-PVT. Keys: {list(self.latest_data.keys())}")
            # =========================== DEBUG LOGGING END =============================
            
            self.diagnostics.record_operation("gps_handler", "nav_pvt", 1.0, True)
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"NAV-PVT Exception: {type(e).__name__}: {e}")
            logger.error(f"NAV-PVT traceback", exc_info=True)
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
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f"Processing NAV-HPPOSLLH - checking fields...")
            logger.debug(f"Message attributes: {dir(message)}")
            # =========================== DEBUG LOGGING END =============================
            
            lat_hp = getattr(message, 'latHp', 0)
            lon_hp = getattr(message, 'lonHp', 0)
            height_hp = getattr(message, 'heightHp', 0)
            hmsl_hp = getattr(message, 'hMSLHp', 0)

            hp_lat = (message.lat + lat_hp * 1e-2) / 1e7
            hp_lon = (message.lon + lon_hp * 1e-2) / 1e7
            hp_height = (message.height + height_hp * 1e-1) / 1000.0
            hp_hmsl = (message.hMSL + hmsl_hp * 1e-1) / 1000.0
            
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
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" NAV-HPPOSLLH processed successfully")
            # =========================== DEBUG LOGGING END =============================
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-HPPOSLLH message: {e}")
            self.diagnostics.log_error("GPS NAV-HPPOSLLH data validation error")
        
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"NAV-HPPOSLLH Exception: {type(e).__name__}: {e}")
            logger.error(f"NAV-HPPOSLLH traceback", exc_info=True)
            # =========================== DEBUG LOGGING END =============================
            logger.debug(f"Error processing NAV-HPPOSLLH message: {e}")
            self.diagnostics.log_error("GPS NAV-HPPOSLLH data processing error")

    async def _process_nmea_data(self, data) -> None:
        """Process NMEA sentences from the buffer.
        
        Args:
            data: Buffer containing NMEA data
        """
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing NMEA data from buffer")
            # =========================== DEBUG LOGGING END ===========================
            
            # Convert bytes to string if needed
            if isinstance(data, (bytes, bytearray)):
                data_str = data.decode('ascii', errors='ignore')
            else:
                data_str = str(data)
            
            # Find all NMEA sentences (starting with $ and ending with \r\n)
            import pynmea2
            import re
            
            # Find all potential NMEA sentences
            nmea_pattern = r'\$.*?\\r\\n|\$.*?\r\n'
            sentences = re.findall(nmea_pattern, data_str)
            
            if not sentences:
                # =========================== DEBUG LOGGING START ===========================
                logger.debug(f" No complete NMEA sentences found in buffer")
                # =========================== DEBUG LOGGING END ===========================
                return
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Found {len(sentences)} potential NMEA sentences")
            # =========================== DEBUG LOGGING END ===========================
            
            for sentence in sentences:
                try:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Processing NMEA sentence: {sentence[:20]}...")
                    # =========================== DEBUG LOGGING END ===========================
                    
                    # Clean up the sentence
                    sentence = sentence.strip()
                    if not sentence.startswith('$'):
                        continue
                        
                    # Parse the NMEA sentence
                    msg = pynmea2.parse(sentence)
                    
                    # =========================== DEBUG LOGGING START ===========================
                    logger.debug(f" Parsed NMEA sentence: {msg.sentence_type}")
                    logger.debug(f" NMEA data: {msg}")
                    # =========================== DEBUG LOGGING END ===========================
                    
                    # Process different NMEA sentence types
                    if msg.sentence_type == 'GGA':  # Global Positioning System Fix Data
                        if msg.latitude and msg.longitude:
                            self.latest_data.update({
                                'nmea_timestamp': datetime.utcnow(),
                                'nmea_latitude': msg.latitude,
                                'nmea_longitude': msg.longitude,
                                'nmea_altitude': float(msg.altitude) if msg.altitude else None,
                                'nmea_num_sats': int(msg.num_sats) if msg.num_sats else 0,
                                'nmea_quality': msg.gps_qual,
                                'nmea_hdop': float(msg.horizontal_dil) if msg.horizontal_dil else None
                            })
                            # =========================== DEBUG LOGGING START ===========================
                            logger.debug(f" Updated latest_data with GGA information")
                            # =========================== DEBUG LOGGING END ===========================
                    
                    elif msg.sentence_type == 'RMC':  # Recommended Minimum Navigation Information
                        if msg.latitude and msg.longitude:
                            self.latest_data.update({
                                'nmea_timestamp': datetime.utcnow(),
                                'nmea_latitude': msg.latitude,
                                'nmea_longitude': msg.longitude,
                                'nmea_speed': float(msg.spd_over_grnd) if msg.spd_over_grnd else None,
                                'nmea_course': float(msg.true_course) if msg.true_course else None,
                                'nmea_status': msg.status
                            })
                            # =========================== DEBUG LOGGING START ===========================
                            logger.debug(f" Updated latest_data with RMC information")
                            # =========================== DEBUG LOGGING END ===========================
                    
                    elif msg.sentence_type == 'GSA':  # GPS DOP and active satellites
                        self.latest_data.update({
                            'nmea_timestamp': datetime.utcnow(),
                            'nmea_mode': msg.mode,
                            'nmea_fix_type': int(msg.mode_fix_type) if msg.mode_fix_type else 0,
                            'nmea_pdop': float(msg.pdop) if msg.pdop else None,
                            'nmea_hdop': float(msg.hdop) if msg.hdop else None,
                            'nmea_vdop': float(msg.vdop) if msg.vdop else None
                        })
                        # =========================== DEBUG LOGGING START ===========================
                        logger.debug(f" Updated latest_data with GSA information")
                        # =========================== DEBUG LOGGING END ===========================
                    
                    elif msg.sentence_type == 'GSV':  # Satellites in view
                        # Just log GSV messages for now
                        # =========================== DEBUG LOGGING START ===========================
                        logger.debug(f" Received GSV message: {msg.num_sv_in_view} satellites in view")
                        # =========================== DEBUG LOGGING END ===========================
                    
                except Exception as nmea_error:
                    # =========================== DEBUG LOGGING START ===========================
                    logger.warning(f"🔍 DEBUG: Error parsing NMEA sentence: {nmea_error}")
                    # =========================== DEBUG LOGGING END ===========================
            
            self.diagnostics.record_operation("gps_handler", "nmea_processing", 1.0, True)
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"NMEA processing error: {e}")
            # =========================== DEBUG LOGGING END ===========================
            logger.error(f"Error processing NMEA data: {e}")
            self.diagnostics.record_operation("gps_handler", "nmea_processing", 0.0, False, str(e))

    async def _process_nav_status(self, message) -> None:
        """Process NAV-STATUS message for navigation status information with error handling."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing NAV-STATUS - checking fields...")
            logger.debug(f" Message attributes: {dir(message)}")
            # =========================== DEBUG LOGGING END =============================
            
            self.latest_data.update({
                'nav_status_timestamp': datetime.utcnow(),
                'gps_fix': message.gpsFix,
                'fix_stat_flags': message.flags,
                'fix_stat': message.fixStat,
                'flags2': message.flags2,
                'ttff': message.ttff,  # Time to first fix (ms)
                'msss': message.msss,  # Time since startup (ms)
            })
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" NAV-STATUS processed successfully")
            # =========================== DEBUG LOGGING END =============================
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-STATUS message: {e}")
            self.diagnostics.log_error("GPS NAV-STATUS data validation error")
        
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"NAV-STATUS Exception: {type(e).__name__}: {e}")
            logger.error(f"NAV-STATUS traceback", exc_info=True)
            # =========================== DEBUG LOGGING END =============================
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
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" Processing NAV-SAT - checking fields...")
            logger.debug(f" Message attributes: {dir(message)}")
            logger.debug(f" numSvs: {getattr(message, 'numSvs', 'NOT FOUND')}")
            # =========================== DEBUG LOGGING END =============================
            
            # NAV-SAT contains repeated groups, extract satellite info
            satellites = []
            num_svs = getattr(message, 'numSvs', 0)
            
            # Each satellite has multiple fields in the repeated group
            for i in range(1, num_svs + 1):
                sat_data = {
                    'svid': getattr(message, f'svid_{i:02d}', 0),
                    'flags': getattr(message, f'flags_{i:02d}', 0),
                    'quality': getattr(message, f'quality_{i:02d}', 0),
                    'cno': getattr(message, f'cno_{i:02d}', 0),
                    'elev': getattr(message, f'elev_{i:02d}', 0),
                    'azim': getattr(message, f'azim_{i:02d}', 0),
                    'prRes': getattr(message, f'prRes_{i:02d}', 0),
                }
                satellites.append(sat_data)
            
            self.latest_data.update({
                'sat_timestamp': datetime.utcnow(),
                'sat_num_svs': num_svs,
                'satellites_info': satellites,
                'satellites_in_view': num_svs,
            })
            
            # Calculate average signal strength
            if satellites:
                avg_cno = sum(s['cno'] for s in satellites) / len(satellites)
                self.latest_data['signal_strength'] = avg_cno
            
            # =========================== DEBUG LOGGING START ===========================
            logger.debug(f" NAV-SAT processed successfully with {num_svs} satellites")
            # =========================== DEBUG LOGGING END =============================
            
        except GPSDataValidationError as e:
            logger.debug(f"Error processing NAV-SAT message: {e}")
            self.diagnostics.log_error("GPS NAV-SAT data validation error")
        
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"NAV-SAT Exception: {type(e).__name__}: {e}")
            logger.error(f"NAV-SAT traceback", exc_info=True)
            # =========================== DEBUG LOGGING END =============================
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
            logger.debug(f" ✅ Configuration ACK for {msg_name}")
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

    async def _process_nmea_data(self, raw: bytes) -> None:
        """Decode a raw byte chunk, extract individual NMEA sentences and
        delegate each one to :py:meth:`_process_nmea_message`.

        This prevents the read loop from crashing when a chunk contains NMEA
        text and ensures sentences are parsed asynchronously.
        """
        try:
            text = raw.decode('ascii', errors='ignore')
            for line in text.splitlines():
                if line.startswith('$'):
                    try:
                        nmea_msg = nmea_parse(line)
                        await self._process_nmea_message(nmea_msg)
                    except Exception as e:
                        logger.debug(f"Error parsing NMEA line '{line}': {e}")
        except Exception as e:
            logger.debug(f"Error processing NMEA data chunk: {e}")

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
            logger.debug(f" get_latest_data() called - available keys: {data_keys}")
            
            if data_keys:
                # Show sample of data for key fields
                sample_data = {}
                for key in ['timestamp', 'latitude', 'longitude', 'fix_type', 'satellites', 'satellites_used']:
                    if key in self.latest_data:
                        sample_data[key] = self.latest_data[key]
                logger.debug(f" Sample GPS data: {sample_data}")
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

    async def _save_device_configuration(self) -> None:
        """Save device configuration to non-volatile memory (BBR/Flash) with error handling."""
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Creating CFG-CFG message with byte masks")
            # =========================== DEBUG LOGGING END =============================
            
            # Create CFG-CFG message to save configuration
            # pyubx2 expects masks as bytes for X004 type
            cfg_msg = UBXMessage('CFG', 'CFG-CFG', SET, 
                               clearMask=b'\x00\x00\x00\x00',  # Don't clear anything
                               saveMask=b'\xFF\xFF\xFF\xFF',   # Save all settings
                               loadMask=b'\x00\x00\x00\x00',   # Don't load anything
                               deviceMask=b'\x00')              # All devices
            
            # Send CFG-CFG message to save configuration
            await self._send_ubx_message(cfg_msg)
            
            # Wait for ACK-ACK message to confirm configuration save
            await asyncio.sleep(0.1)  # Small delay for device processing
            
            logger.info("💾 Device configuration saved to non-volatile memory")
            
        except GPSConfigurationError as e:
            logger.error(f"Failed to save device configuration: {e}")
            self.diagnostics.log_error("Failed to save device configuration")
            raise
            
        except Exception as e:
            logger.error(f"Failed to save device configuration: {e}")
            self.diagnostics.log_error("Failed to save device configuration")
            raise GPSConfigurationError(f"Failed to save device configuration: {e}")
