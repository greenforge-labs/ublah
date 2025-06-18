"""
GPS Handler for u-blox ZED-F9P communication.
Handles serial communication, configuration, and data parsing.
"""

import asyncio
import logging
import serial
import serial.tools.list_ports
from typing import Dict, Any, Optional, List
from pyubx2 import UBXReader, UBXMessage, POLL, SET, GET
from pyubx2.ubxtypes_core import *
import pynmea2
from datetime import datetime

logger = logging.getLogger(__name__)

class GPSHandler:
    """Handles communication with u-blox ZED-F9P GPS device."""
    
    def __init__(self, config):
        self.config = config
        self.serial_port: Optional[serial.Serial] = None
        self.connected = False
        self.latest_data = {}
        self.reader_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start GPS communication."""
        logger.info("Starting GPS handler...")
        
        try:
            await self._connect_device()
            await self._configure_device()
            
            # Start reading data in background
            self.reader_task = asyncio.create_task(self._read_data_loop())
            logger.info("GPS handler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start GPS handler: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop GPS communication."""
        logger.info("Stopping GPS handler...")
        
        self._stop_event.set()
        
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            logger.info("GPS serial port closed")
        
        self.connected = False
        logger.info("GPS handler stopped")
    
    async def _connect_device(self) -> None:
        """Connect to GPS device via serial port."""
        device_path = self.config.gps_device
        baudrate = self.config.gps_baudrate
        
        try:
            # Check if device exists
            if not self._device_exists(device_path):
                available_ports = self._list_available_ports()
                raise Exception(f"GPS device not found at {device_path}. Available ports: {available_ports}")
            
            # Open serial connection
            self.serial_port = serial.Serial(
                port=device_path,
                baudrate=baudrate,
                timeout=1.0,
                write_timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            self.connected = True
            logger.info(f"Connected to GPS device at {device_path} @ {baudrate} baud")
            
        except Exception as e:
            logger.error(f"Failed to connect to GPS device: {e}")
            raise
    
    def _device_exists(self, device_path: str) -> bool:
        """Check if the specified device path exists."""
        import os
        return os.path.exists(device_path)
    
    def _list_available_ports(self) -> List[str]:
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    async def _configure_device(self) -> None:
        """Configure u-blox device for RTK operation."""
        logger.info("Configuring GPS device...")
        
        try:
            # Configure navigation rate
            rate_ms = int(1000 / self.config.update_rate_hz)
            nav_rate_msg = UBXMessage('CFG', 'CFG-RATE', SET, 
                                    measRate=rate_ms, navRate=1, timeRef=1)
            await self._send_ubx_message(nav_rate_msg)
            
            # Configure constellation
            await self._configure_constellations()
            
            # Enable required message types
            await self._enable_messages()
            
            # Save configuration
            save_msg = UBXMessage('CFG', 'CFG-CFG', SET, 
                                clearMask=0, saveMask=0x1F, loadMask=0)
            await self._send_ubx_message(save_msg)
            
            logger.info("GPS device configuration complete")
            
        except Exception as e:
            logger.error(f"Failed to configure GPS device: {e}")
            raise
    
    async def _configure_constellations(self) -> None:
        """Configure GNSS constellations."""
        constellations = self.config.constellation.upper().split('+')
        logger.info(f"Configuring constellations: {constellations}")
        
        # This is a simplified configuration - full implementation would
        # configure each constellation individually
        # For now, we'll enable all major constellations
        pass
    
    async def _enable_messages(self) -> None:
        """Enable required UBX and NMEA messages."""
        messages_to_enable = [
            ('NAV', 'NAV-PVT'),     # Position, velocity, time
            ('NAV', 'NAV-HPPOSLLH'), # High precision position
            ('NAV', 'NAV-STATUS'),   # Navigation status
        ]
        
        for msg_class, msg_type in messages_to_enable:
            # Enable message on UART1
            cfg_msg = UBXMessage('CFG', 'CFG-MSG', SET,
                               msgClass=getattr(UBX_CLASSES, msg_class),
                               msgID=getattr(UBX_MSGIDS, msg_type.replace('-', '_')),
                               rateUART1=1)
            await self._send_ubx_message(cfg_msg)
    
    async def _send_ubx_message(self, message: UBXMessage) -> None:
        """Send UBX message to device."""
        if not self.serial_port or not self.connected:
            raise Exception("GPS device not connected")
        
        try:
            self.serial_port.write(message.serialize())
            await asyncio.sleep(0.1)  # Small delay for device processing
        except Exception as e:
            logger.error(f"Failed to send UBX message: {e}")
            raise
    
    async def _read_data_loop(self) -> None:
        """Background task to read GPS data continuously."""
        ubx_reader = UBXReader(self.serial_port)
        
        while not self._stop_event.is_set() and self.connected:
            try:
                if self.serial_port.in_waiting > 0:
                    try:
                        # Try to read UBX message
                        raw_data, parsed_data = ubx_reader.read()
                        if parsed_data:
                            await self._process_ubx_message(parsed_data)
                    except Exception as e:
                        # If UBX parsing fails, try NMEA
                        try:
                            line = self.serial_port.readline().decode('ascii', errors='ignore').strip()
                            if line.startswith('$'):
                                nmea_msg = pynmea2.parse(line)
                                await self._process_nmea_message(nmea_msg)
                        except Exception as nmea_e:
                            logger.debug(f"Failed to parse message: UBX={e}, NMEA={nmea_e}")
                
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                logger.error(f"Error in GPS data loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_ubx_message(self, message) -> None:
        """Process incoming UBX message."""
        try:
            if hasattr(message, 'identity') and message.identity == 'NAV-PVT':
                # Position, Velocity, Time message
                self.latest_data.update({
                    'timestamp': datetime.utcnow().isoformat(),
                    'latitude': message.lat / 1e7,
                    'longitude': message.lon / 1e7,
                    'altitude': message.hMSL / 1000.0,  # Convert mm to m
                    'fix_type': self._get_fix_type_name(message.fixType),
                    'satellites': message.numSV,
                    'horizontal_accuracy': message.hAcc / 1000.0,  # Convert mm to m
                    'vertical_accuracy': message.vAcc / 1000.0,
                    'speed': message.gSpeed / 1000.0,  # Convert mm/s to m/s
                    'heading': message.headMot / 1e5,  # Convert to degrees
                })
                
        except Exception as e:
            logger.debug(f"Error processing UBX message: {e}")
    
    async def _process_nmea_message(self, message) -> None:
        """Process incoming NMEA message."""
        try:
            if hasattr(message, 'sentence_type'):
                if message.sentence_type == 'GGA':
                    # Global Positioning System Fix Data
                    self.latest_data.update({
                        'timestamp': datetime.utcnow().isoformat(),
                        'latitude': message.latitude,
                        'longitude': message.longitude,
                        'altitude': message.altitude,
                        'satellites': message.num_sats,
                        'hdop': message.horizontal_dil,
                        'fix_quality': message.gps_qual,
                    })
                    
        except Exception as e:
            logger.debug(f"Error processing NMEA message: {e}")
    
    def _get_fix_type_name(self, fix_type: int) -> str:
        """Convert numeric fix type to readable name."""
        fix_types = {
            0: "No Fix",
            1: "Dead Reckoning",
            2: "2D Fix",
            3: "3D Fix",
            4: "GNSS + Dead Reckoning",
            5: "Time Only Fix"
        }
        return fix_types.get(fix_type, f"Unknown ({fix_type})")
    
    async def get_latest_data(self) -> Dict[str, Any]:
        """Get the latest GPS data."""
        return self.latest_data.copy()
    
    def is_connected(self) -> bool:
        """Check if GPS device is connected."""
        return self.connected and self.serial_port and self.serial_port.is_open
    
    async def send_corrections(self, rtcm_data: bytes) -> None:
        """Send RTCM correction data to GPS device."""
        if not self.serial_port or not self.connected:
            logger.warning("Cannot send corrections: GPS device not connected")
            return
        
        try:
            self.serial_port.write(rtcm_data)
            logger.debug(f"Sent {len(rtcm_data)} bytes of RTCM corrections")
        except Exception as e:
            logger.error(f"Failed to send RTCM corrections: {e}")
