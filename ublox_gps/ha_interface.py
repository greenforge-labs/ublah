"""
HomeAssistant Interface for u-blox GPS RTK add-in.
Manages entity creation and updates via HomeAssistant API.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class HomeAssistantInterface:
    """Interface for communicating with HomeAssistant API."""
    
    def __init__(self, config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.entities_initialized = False
        self.last_update_time = None
        
        # Entity definitions
        self.entities = {
            'device_tracker.ublox_gps': {
                'name': 'u-blox GPS Location',
                'icon': 'mdi:crosshairs-gps',
                'device_class': None,
            },
            'sensor.ublox_gps_fix_type': {
                'name': 'GPS Fix Type',
                'icon': 'mdi:satellite-variant',
                'device_class': None,
            },
            'sensor.ublox_gps_satellites': {
                'name': 'GPS Satellites',
                'icon': 'mdi:satellite',
                'device_class': None,
                'unit_of_measurement': 'satellites',
            },
            'sensor.ublox_gps_satellites_used': {
                'name': 'GPS Satellites Used',
                'icon': 'mdi:satellite-uplink',
                'device_class': None,
                'unit_of_measurement': 'satellites',
            },
            'sensor.ublox_gps_satellites_in_view': {
                'name': 'GPS Satellites in View',
                'icon': 'mdi:satellite-variant',
                'device_class': None,
                'unit_of_measurement': 'satellites',
            },
            'sensor.ublox_gps_signal_strength': {
                'name': 'GPS Signal Strength',
                'icon': 'mdi:signal',
                'device_class': 'signal_strength',
                'unit_of_measurement': 'dBHz',
            },
            'sensor.ublox_gps_pdop': {
                'name': 'GPS Position DOP',
                'icon': 'mdi:target-variant',
                'device_class': None,
                'unit_of_measurement': None,
            },
            'binary_sensor.ublox_gps_signal_acquired': {
                'name': 'GPS Signal Acquired',
                'icon': 'mdi:satellite-uplink',
                'device_class': 'connectivity',
            },
            'sensor.ublox_gps_accuracy': {
                'name': 'GPS Horizontal Accuracy',
                'icon': 'mdi:target',
                'device_class': 'distance',
                'unit_of_measurement': 'cm',
            },
            'sensor.ublox_gps_altitude': {
                'name': 'GPS Altitude',
                'icon': 'mdi:altimeter',
                'device_class': 'distance',
                'unit_of_measurement': 'm',
            },
            'binary_sensor.ublox_gps_connected': {
                'name': 'GPS Device Connected',
                'icon': 'mdi:connection',
                'device_class': 'connectivity',
            },
            'binary_sensor.ublox_ntrip_connected': {
                'name': 'NTRIP Connected',
                'icon': 'mdi:wifi',
                'device_class': 'connectivity',
            },
            'sensor.ublox_gps_speed': {
                'name': 'GPS Speed',
                'icon': 'mdi:speedometer',
                'device_class': 'speed',
                'unit_of_measurement': 'm/s',
            },
            'sensor.ublox_gps_heading': {
                'name': 'GPS Heading',
                'icon': 'mdi:compass',
                'unit_of_measurement': '°',
            },
        }
    
    async def initialize_entities(self) -> None:
        """Initialize HomeAssistant entities."""
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: Starting HomeAssistant entity initialization...")
        logger.info(f"🔍 DEBUG: HomeAssistant URL: {self.config.homeassistant_url}")
        logger.info(f"🔍 DEBUG: SUPERVISOR_TOKEN available: {bool(self.config.homeassistant_token)}")
        if self.config.homeassistant_token:
            logger.info(f"🔍 DEBUG: SUPERVISOR_TOKEN length: {len(self.config.homeassistant_token)} chars")
        # =========================== DEBUG LOGGING END =============================
        
        if not self.config.homeassistant_token:
            logger.error("SUPERVISOR_TOKEN environment variable not found - this indicates a HomeAssistant configuration issue")
            logger.error("Make sure 'homeassistant_api: true' is set in config.yaml")
            return
        
        logger.info("Initializing HomeAssistant entities...")
        logger.info(f"Using SUPERVISOR_TOKEN for authentication")
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: Creating aiohttp ClientSession...")
        # =========================== DEBUG LOGGING END =============================
        
        self.session = aiohttp.ClientSession(
            headers={
                'Authorization': f'Bearer {self.config.homeassistant_token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=10)
        )
        
        # =========================== DEBUG LOGGING START ===========================
        logger.info("🔍 DEBUG: ✅ aiohttp ClientSession created successfully")
        # =========================== DEBUG LOGGING END =============================
        
        try:
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Registering device with HomeAssistant...")
            # =========================== DEBUG LOGGING END =============================
            
            # Register device
            await self._register_device()
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: ✅ Device registration completed")
            logger.info(f"🔍 DEBUG: Number of entities to initialize: {len(self.entities)}")
            # =========================== DEBUG LOGGING END =============================
            
            # Initialize all entities
            for entity_id, entity_config in self.entities.items():
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: Initializing entity: {entity_id}")
                # =========================== DEBUG LOGGING END =============================
                await self._initialize_entity(entity_id, entity_config)
            
            self.entities_initialized = True
            logger.info("HomeAssistant entities initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize HomeAssistant entities: {e}")
            if self.session:
                await self.session.close()
                self.session = None
    
    async def _register_device(self) -> None:
        """Register the GPS device with HomeAssistant."""
        device_info = {
            'identifiers': ['ublox_gps_rtk'],
            'name': 'u-blox GPS RTK',
            'manufacturer': 'u-blox',
            'model': 'ZED-F9P',
            'sw_version': '0.1.0',
        }
        
        # This would typically be done through the device registry API
        # For now, we'll include device info in entity attributes
        logger.debug(f"Device info prepared: {device_info}")
    
    async def _initialize_entity(self, entity_id: str, entity_config: Dict[str, Any]) -> None:
        """Initialize a single entity in HomeAssistant."""
        try:
            # Set initial state
            await self._update_entity_state(entity_id, 'unknown', entity_config)
            logger.debug(f"Initialized entity: {entity_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize entity {entity_id}: {e}")
    
    async def update_gps_data(self, gps_data: Dict[str, Any]) -> None:
        """Update GPS data entities in HomeAssistant."""
        if not self.entities_initialized or not self.session:
            logger.warning(f"🔍 DEBUG: Cannot update GPS data - entities_initialized: {self.entities_initialized}, session: {self.session is not None}")
            return
        
        logger.info(f"🔍 DEBUG: update_gps_data called with data keys: {list(gps_data.keys())}")
        logger.info(f"🔍 DEBUG: GPS data values: {gps_data}")
        
        try:
            # Update device tracker with location
            if 'latitude' in gps_data and 'longitude' in gps_data:
                logger.info(f"🔍 DEBUG: Updating device tracker with lat: {gps_data['latitude']}, lon: {gps_data['longitude']}")
                
                await self._update_entity_state(
                    'device_tracker.ublox_gps',
                    'home',  # or 'not_home' based on your logic
                    self.entities['device_tracker.ublox_gps'],
                    {
                        'latitude': gps_data['latitude'],
                        'longitude': gps_data['longitude'],
                        'gps_accuracy': gps_data.get('horizontal_accuracy', 0),
                        'battery': 100,  # GPS devices typically don't report battery
                        'source_type': 'gps'
                    }
                )
            
            # Update fix type
            if 'fix_type' in gps_data:
                fix_type_names = {
                    0: 'No Fix',
                    1: '2D Fix', 
                    2: '3D Fix',
                    3: 'GNSS + DR',
                    4: 'Time Only',
                    5: 'Survey-in'
                }
                fix_type_str = fix_type_names.get(gps_data['fix_type'], f"Unknown ({gps_data['fix_type']})")
                
                logger.info(f"🔍 DEBUG: Updating fix type: {fix_type_str}")
                
                await self._update_entity_state(
                    'sensor.ublox_gps_fix_type',
                    fix_type_str,
                    self.entities['sensor.ublox_gps_fix_type']
                )
            
            # Update satellite count
            if 'satellites' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites',
                    gps_data['satellites'],
                    self.entities['sensor.ublox_gps_satellites']
                )
            
            # Update satellites used (from NAV-PVT)
            if 'satellites_used' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites_used',
                    gps_data['satellites_used'],
                    self.entities['sensor.ublox_gps_satellites_used']
                )
            
            # Update satellites in view (from NAV-SAT)
            if 'sat_num_svs' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites_in_view',
                    gps_data['sat_num_svs'],
                    self.entities['sensor.ublox_gps_satellites_in_view']
                )
            
            # Update signal strength (average C/N0 from NAV-SAT)
            if 'sat_cno' in gps_data and gps_data['sat_cno']:
                try:
                    # Calculate average signal strength if multiple satellites
                    if isinstance(gps_data['sat_cno'], list):
                        avg_signal = sum(gps_data['sat_cno']) / len(gps_data['sat_cno'])
                    else:
                        avg_signal = gps_data['sat_cno']
                    
                    await self._update_entity_state(
                        'sensor.ublox_gps_signal_strength',
                        round(avg_signal, 1),
                        self.entities['sensor.ublox_gps_signal_strength']
                    )
                except (TypeError, ZeroDivisionError):
                    pass
            
            # Update PDOP (position dilution of precision)
            if 'pdop' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_pdop',
                    round(gps_data['pdop'], 2),
                    self.entities['sensor.ublox_gps_pdop']
                )
            
            # Update signal acquired status
            signal_acquired = (
                gps_data.get('fix_type', 'No Fix') != 'No Fix' or
                gps_data.get('satellites_used', 0) > 0 or
                gps_data.get('sat_num_svs', 0) > 4
            )
            await self._update_entity_state(
                'binary_sensor.ublox_gps_signal_acquired',
                'on' if signal_acquired else 'off',
                self.entities['binary_sensor.ublox_gps_signal_acquired']
            )
            
            # Update accuracy (convert from meters to centimeters)
            if 'horizontal_accuracy' in gps_data:
                accuracy_cm = round(gps_data['horizontal_accuracy'] * 100, 1)
                
                logger.info(f"🔍 DEBUG: Updating accuracy: {accuracy_cm} cm")
                
                await self._update_entity_state(
                    'sensor.ublox_gps_accuracy',
                    accuracy_cm,
                    self.entities['sensor.ublox_gps_accuracy']
                )
            
            # Update altitude
            if 'altitude' in gps_data:
                logger.info(f"🔍 DEBUG: Updating altitude: {gps_data['altitude']} m")
                
                await self._update_entity_state(
                    'sensor.ublox_gps_altitude',
                    round(gps_data['altitude'], 1),
                    self.entities['sensor.ublox_gps_altitude']
                )
            
            # Update speed
            if 'speed' in gps_data:
                logger.info(f"🔍 DEBUG: Updating speed: {gps_data['speed']} m/s")
                
                await self._update_entity_state(
                    'sensor.ublox_gps_speed',
                    round(gps_data['speed'], 2),
                    self.entities['sensor.ublox_gps_speed']
                )
            
            # Update heading
            if 'heading' in gps_data:
                logger.info(f"🔍 DEBUG: Updating heading: {gps_data['heading']}°")
                
                await self._update_entity_state(
                    'sensor.ublox_gps_heading',
                    round(gps_data['heading'], 1),
                    self.entities['sensor.ublox_gps_heading']
                )
            
            self.last_update_time = datetime.utcnow()
            
            logger.info(f"🔍 DEBUG: GPS data update completed successfully")
            
        except Exception as e:
            logger.error(f"🔍 DEBUG: Failed to update GPS entities: {e}")
            logger.error(f"Failed to update GPS entities: {e}")
    
    async def update_entities(self, gps_data: Dict[str, Any]) -> None:
        """Update HomeAssistant entities with GPS data."""
        if not self.entities_initialized or not self.session:
            return
        
        try:
            # Update device tracker (location)
            if 'latitude' in gps_data and 'longitude' in gps_data:
                location_data = {
                    'latitude': gps_data['latitude'],
                    'longitude': gps_data['longitude'],
                    'gps_accuracy': int(gps_data.get('horizontal_accuracy', 0) * 100),  # Convert to cm
                    'source_type': 'gps',
                }
                await self._update_entity_state(
                    'device_tracker.ublox_gps', 
                    'home',  # or calculate zone based on coordinates
                    self.entities['device_tracker.ublox_gps'],
                    location_data
                )
            
            # Update fix type
            if 'fix_type' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_fix_type',
                    gps_data['fix_type'],
                    self.entities['sensor.ublox_gps_fix_type']
                )
            
            # Update satellite count
            if 'satellites' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites',
                    gps_data['satellites'],
                    self.entities['sensor.ublox_gps_satellites']
                )
            
            # Update satellites used (from NAV-PVT)
            if 'satellites_used' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites_used',
                    gps_data['satellites_used'],
                    self.entities['sensor.ublox_gps_satellites_used']
                )
            
            # Update satellites in view (from NAV-SAT)
            if 'sat_num_svs' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_satellites_in_view',
                    gps_data['sat_num_svs'],
                    self.entities['sensor.ublox_gps_satellites_in_view']
                )
            
            # Update signal strength (average C/N0 from NAV-SAT)
            if 'sat_cno' in gps_data and gps_data['sat_cno']:
                try:
                    # Calculate average signal strength if multiple satellites
                    if isinstance(gps_data['sat_cno'], list):
                        avg_signal = sum(gps_data['sat_cno']) / len(gps_data['sat_cno'])
                    else:
                        avg_signal = gps_data['sat_cno']
                    
                    await self._update_entity_state(
                        'sensor.ublox_gps_signal_strength',
                        round(avg_signal, 1),
                        self.entities['sensor.ublox_gps_signal_strength']
                    )
                except (TypeError, ZeroDivisionError):
                    pass
            
            # Update PDOP (position dilution of precision)
            if 'pdop' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_pdop',
                    round(gps_data['pdop'], 2),
                    self.entities['sensor.ublox_gps_pdop']
                )
            
            # Update signal acquired status
            signal_acquired = (
                gps_data.get('fix_type', 'No Fix') != 'No Fix' or
                gps_data.get('satellites_used', 0) > 0 or
                gps_data.get('sat_num_svs', 0) > 4
            )
            await self._update_entity_state(
                'binary_sensor.ublox_gps_signal_acquired',
                'on' if signal_acquired else 'off',
                self.entities['binary_sensor.ublox_gps_signal_acquired']
            )
            
            # Update accuracy (convert to cm)
            if 'horizontal_accuracy' in gps_data:
                accuracy_cm = int(gps_data['horizontal_accuracy'] * 100)
                await self._update_entity_state(
                    'sensor.ublox_gps_accuracy',
                    accuracy_cm,
                    self.entities['sensor.ublox_gps_accuracy']
                )
            
            # Update altitude
            if 'altitude' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_altitude',
                    round(gps_data['altitude'], 2),
                    self.entities['sensor.ublox_gps_altitude']
                )
            
            # Update speed
            if 'speed' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_speed',
                    round(gps_data['speed'], 2),
                    self.entities['sensor.ublox_gps_speed']
                )
            
            # Update heading
            if 'heading' in gps_data:
                await self._update_entity_state(
                    'sensor.ublox_gps_heading',
                    round(gps_data['heading'], 1),
                    self.entities['sensor.ublox_gps_heading']
                )
            
            self.last_update_time = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to update GPS entities: {e}")
    
    async def update_status(self, status_data: Dict[str, Any]) -> None:
        """Update status entities."""
        if not self.entities_initialized or not self.session:
            return
        
        try:
            # Update GPS connection status
            if 'gps_connected' in status_data:
                await self._update_entity_state(
                    'binary_sensor.ublox_gps_connected',
                    'on' if status_data['gps_connected'] else 'off',
                    self.entities['binary_sensor.ublox_gps_connected']
                )
            
            # Update NTRIP connection status
            if 'ntrip_connected' in status_data:
                await self._update_entity_state(
                    'binary_sensor.ublox_ntrip_connected',
                    'on' if status_data['ntrip_connected'] else 'off',
                    self.entities['binary_sensor.ublox_ntrip_connected']
                )
            
        except Exception as e:
            logger.error(f"Failed to update status entities: {e}")
    
    async def _update_entity_state(
        self, 
        entity_id: str, 
        state: Any, 
        entity_config: Dict[str, Any],
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update entity state in HomeAssistant."""
        if not self.session:
            return
        
        url = f"{self.config.homeassistant_url}/api/states/{entity_id}"
        
        # Prepare entity data
        entity_data = {
            'state': state,
            'attributes': {
                'friendly_name': entity_config['name'],
                'icon': entity_config['icon'],
                'last_updated': datetime.utcnow().isoformat(),
            }
        }
        
        # Add device class if specified
        if entity_config.get('device_class'):
            entity_data['attributes']['device_class'] = entity_config['device_class']
        
        # Add unit of measurement if specified
        if entity_config.get('unit_of_measurement'):
            entity_data['attributes']['unit_of_measurement'] = entity_config['unit_of_measurement']
        
        # Add additional attributes
        if attributes:
            entity_data['attributes'].update(attributes)
        
        try:
            async with self.session.post(url, json=entity_data) as response:
                if response.status not in [200, 201]:
                    # Get response text for better error details
                    response_text = await response.text()
                    logger.warning(f"Failed to update entity {entity_id}: {response.status} - {response_text}")
                    
                else:
                    logger.debug(f"Updated entity {entity_id} with state: {state}")
                    
        except Exception as e:
            logger.error(f"Error updating entity {entity_id}: {e}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.entities_initialized = False
        logger.info("HomeAssistant interface cleaned up")
