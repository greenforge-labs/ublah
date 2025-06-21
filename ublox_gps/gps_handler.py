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
            
            # Configure device-specific settings
            await self._configure_gnss_systems()
            await self._configure_dynamic_model()
            
            # Disable NMEA and/or RTCM3 output if requested
            await self._disable_protocol_outputs()
            
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

    async def _disable_protocol_outputs(self) -> None:
        """Disable NMEA and/or RTCM3 outputs on USB interface based on configuration."""
        try:
            # Modern method: Use CFG-USBOUTPROT to disable protocol outputs on USB
            layers = SET_LAYER_RAM | SET_LAYER_BBR | SET_LAYER_FLASH
            transaction = TXN_NONE
            
            # Disable NMEA if configured
            if self.config.disable_nmea_output:
                logger.info("Disabling NMEA output on USB interface...")
                
                # CFG-USBOUTPROT-NMEA (0x10780002) = 0 (disable)
                cfgData = [(b"\x10\x78\x00\x02", b"\x00")]  # CFG-USBOUTPROT-NMEA = 0
                
                msg = UBXMessage.config_set(layers, transaction, cfgData)
                await self._send_ubx_message(msg)
                logger.info("NMEA output disabled on USB interface via CFG-USBOUTPROT")
            
            # Disable RTCM3 if configured
            if self.config.disable_rtcm3_output:
                logger.info("Disabling RTCM3 output on USB interface...")
                
                # CFG-USBOUTPROT-RTCM3X (0x10780014) = 0 (disable)
                cfgData = [(b"\x10\x78\x00\x14", b"\x00")]  # CFG-USBOUTPROT-RTCM3X = 0
                
                msg = UBXMessage.config_set(layers, transaction, cfgData)
                await self._send_ubx_message(msg)
                logger.info("RTCM3 output disabled on USB interface via CFG-USBOUTPROT")
            
        except Exception as e:
            logger.warning(f"Failed to disable protocol outputs via CFG-USBOUTPROT: {e}")
            
            # Fallback for NMEA only (legacy method)
            if self.config.disable_nmea_output:
                logger.info("Falling back to legacy method of disabling individual NMEA messages...")
                
                # Legacy method - disable individual NMEA messages
                nmea_messages = [
                    (b"\xf0\x00"),  # GGA
                    (b"\xf0\x01"),  # GLL
                    (b"\xf0\x02"),  # GSA
                    (b"\xf0\x03"),  # GSV
                    (b"\xf0\x04"),  # RMC
                    (b"\xf0\x05"),  # VTG
                    (b"\xf0\x06"),  # GRS
                    (b"\xf0\x07"),  # GST
                    (b"\xf0\x08"),  # ZDA
                    (b"\xf0\x09"),  # GBS
                    (b"\xf0\x0a"),  # DTM
                    (b"\xf0\x0d"),  # GNS
                    (b"\xf0\x0e"),  # THS
                    (b"\xf0\x0f"),  # VLW
                ]
                
                for msg_class_id in nmea_messages:
                    try:
                        # Disable on all ports (I2C, UART1, UART2, USB, SPI)
                        rates = b"\x00\x00\x00\x00\x00\x00"  # All zeros = disabled
                        msg = UBXMessage(
                            ubxClass=b"\x06",  # CFG
                            ubxID=b"\x01",     # MSG
                            payload=msg_class_id + rates
                        )
                        await self._send_ubx_message(msg)
                    except Exception as e:
                        logger.debug(f"Failed to disable NMEA message {msg_class_id.hex()}: {e}")
                
                logger.info("Disabled individual NMEA messages via legacy CFG-MSG")
{{ ... }}
