"""
NTRIP Client for receiving RTK correction data.
Supports standard NTRIP protocol with authentication and RTCM message filtering.
"""

import asyncio
import logging
import base64
import socket
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime, timedelta
from rtcm_handler import RTCMHandler, RTCMStatistics

logger = logging.getLogger(__name__)

class NTRIPClient:
    """NTRIP client for receiving RTK correction data with RTCM filtering."""
    
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.reader_task: Optional[asyncio.Task] = None
        self.corrections_buffer = bytearray()
        self.last_data_time = None
        self._stop_event = asyncio.Event()
        self.connection_retries = 0
        self.max_retries = 5
        self.retry_delay = 5  # seconds
        
        # RTCM processing
        self.rtcm_handler = RTCMHandler(config)
        self.rtcm_enabled = getattr(config, 'rtcm_filtering_enabled', True)
        self.raw_data_received = 0
        self.filtered_data_sent = 0
        
        logger.info(f"NTRIP client initialized with RTCM filtering: {'enabled' if self.rtcm_enabled else 'disabled'}")
    
    async def start(self) -> None:
        """Start NTRIP client."""
        if not self.config.ntrip_enabled:
            logger.info("NTRIP client disabled in configuration")
            return
        
        if not self.config.ntrip_host or not self.config.ntrip_mountpoint:
            logger.warning("NTRIP configuration incomplete - host or mountpoint missing")
            return
        
        logger.info(f"Starting NTRIP client for {self.config.ntrip_host}:{self.config.ntrip_port}")
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30, connect=10)
        )
        
        # Start connection task
        self.reader_task = asyncio.create_task(self._connection_loop())
    
    async def stop(self) -> None:
        """Stop NTRIP client."""
        logger.info("Stopping NTRIP client...")
        
        self._stop_event.set()
        
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        if self.session:
            await self.session.close()
        
        self.connected = False
        logger.info("NTRIP client stopped")
    
    async def _connection_loop(self) -> None:
        """Main connection loop with retry logic."""
        while not self._stop_event.is_set():
            try:
                await self._connect_and_stream()
                self.connection_retries = 0  # Reset retry counter on successful connection
                
            except Exception as e:
                self.connected = False
                self.connection_retries += 1
                
                if self.connection_retries <= self.max_retries:
                    retry_delay = min(self.retry_delay * self.connection_retries, 60)
                    logger.warning(f"NTRIP connection failed (attempt {self.connection_retries}/{self.max_retries}): {e}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=retry_delay)
                        break  # Stop event was set during wait
                    except asyncio.TimeoutError:
                        continue  # Retry connection
                else:
                    logger.error(f"NTRIP connection failed after {self.max_retries} attempts: {e}")
                    await asyncio.sleep(60)  # Wait longer before trying again
                    self.connection_retries = 0  # Reset counter for next cycle
    
    async def _connect_and_stream(self) -> None:
        """Connect to NTRIP caster and stream corrections."""
        url = f"http://{self.config.ntrip_host}:{self.config.ntrip_port}/{self.config.ntrip_mountpoint}"
        
        headers = {
            'User-Agent': 'NTRIP Client/1.0',
            'Accept': '*/*',
            'Connection': 'close',
        }
        
        # Add authentication if credentials provided
        if self.config.ntrip_username and self.config.ntrip_password:
            credentials = f"{self.config.ntrip_username}:{self.config.ntrip_password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f'Basic {encoded_credentials}'
        
        logger.info(f"Connecting to NTRIP caster: {url}")
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                self.connected = True
                self.last_data_time = datetime.utcnow()
                logger.info(f"Connected to NTRIP caster: {self.config.ntrip_host}")
                
                # Read correction data stream
                async for chunk in response.content.iter_chunked(1024):
                    if self._stop_event.is_set():
                        break
                    
                    if chunk:
                        self.raw_data_received += len(chunk)
                        self.corrections_buffer.extend(chunk)
                        self.last_data_time = datetime.utcnow()
                        logger.debug(f"Received {len(chunk)} bytes of RTCM data")
                        
                        # Limit buffer size to prevent memory issues
                        if len(self.corrections_buffer) > 10240:  # 10KB max buffer
                            self.corrections_buffer = self.corrections_buffer[-5120:]  # Keep last 5KB
            
            elif response.status == 401:
                raise Exception("NTRIP authentication failed - check username/password")
            elif response.status == 404:
                raise Exception(f"NTRIP mountpoint not found: {self.config.ntrip_mountpoint}")
            else:
                raise Exception(f"NTRIP connection failed with status {response.status}: {response.reason}")
    
    async def get_corrections(self) -> Optional[bytes]:
        """Get available RTCM correction data with filtering applied."""
        if not self.corrections_buffer:
            return None
        
        # Get all buffered corrections
        raw_corrections = bytes(self.corrections_buffer)
        self.corrections_buffer.clear()
        
        if self.rtcm_enabled and raw_corrections:
            # Process through RTCM handler for filtering and validation
            filtered_corrections, rtcm_stats = self.rtcm_handler.process_rtcm_data(raw_corrections)
            self.filtered_data_sent += len(filtered_corrections)
            
            if filtered_corrections:
                logger.debug(f"RTCM filtering: {len(raw_corrections)} → {len(filtered_corrections)} bytes "
                           f"({rtcm_stats.valid_messages} valid msgs, {rtcm_stats.filtered_messages} filtered)")
            
            return filtered_corrections if filtered_corrections else None
        else:
            self.filtered_data_sent += len(raw_corrections)
            return raw_corrections
    
    def is_connected(self) -> bool:
        """Check if NTRIP client is connected."""
        if not self.connected:
            return False
        
        # Check if we've received data recently (within last 30 seconds)
        if self.last_data_time:
            time_since_data = datetime.utcnow() - self.last_data_time
            return time_since_data < timedelta(seconds=30)
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get NTRIP client status information with RTCM statistics."""
        status = {
            'connected': self.connected,
            'host': self.config.ntrip_host,
            'port': self.config.ntrip_port,
            'mountpoint': self.config.ntrip_mountpoint,
            'last_data_time': self.last_data_time.isoformat() if self.last_data_time else None,
            'connection_retries': self.connection_retries,
            'buffer_size': len(self.corrections_buffer),
            'raw_data_received': self.raw_data_received,
            'filtered_data_sent': self.filtered_data_sent,
            'rtcm_enabled': self.rtcm_enabled,
        }
        
        # Add RTCM statistics if enabled
        if self.rtcm_enabled:
            status['rtcm_statistics'] = self.rtcm_handler.get_statistics_summary()
            
        return status
    
    async def get_source_table(self) -> Optional[str]:
        """Get NTRIP source table from caster."""
        if not self.session:
            return None
        
        try:
            url = f"http://{self.config.ntrip_host}:{self.config.ntrip_port}"
            headers = {'User-Agent': 'NTRIP Client/1.0'}
            
            # Add authentication if credentials provided
            if self.config.ntrip_username and self.config.ntrip_password:
                credentials = f"{self.config.ntrip_username}:{self.config.ntrip_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers['Authorization'] = f'Basic {encoded_credentials}'
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to get NTRIP source table: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting NTRIP source table: {e}")
            return None
