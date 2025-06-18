"""
Main application entry point for u-blox GPS RTK add-in.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from config import Config
from gps_handler import GPSHandler
from ntrip_client import NTRIPClient
from ha_interface import HomeAssistantInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class UbloxGPSService:
    """Main service class for u-blox GPS RTK functionality."""
    
    def __init__(self):
        self.config = Config()
        self.gps_handler: Optional[GPSHandler] = None
        self.ntrip_client: Optional[NTRIPClient] = None
        self.ha_interface: Optional[HomeAssistantInterface] = None
        self.running = False
    
    async def start(self) -> None:
        """Start the GPS service."""
        logger.info("Starting u-blox GPS RTK service...")
        
        try:
            # Initialize components
            self.gps_handler = GPSHandler(self.config)
            self.ha_interface = HomeAssistantInterface(self.config)
            
            # Initialize NTRIP client if enabled
            if self.config.ntrip_enabled and self.config.ntrip_host:
                self.ntrip_client = NTRIPClient(self.config)
            
            # Start GPS handler
            await self.gps_handler.start()
            
            # Start NTRIP client if configured
            if self.ntrip_client:
                await self.ntrip_client.start()
            
            # Initialize HomeAssistant entities
            await self.ha_interface.initialize_entities()
            
            self.running = True
            logger.info("u-blox GPS RTK service started successfully")
            
            # Main service loop
            await self._run_service_loop()
            
        except Exception as e:
            logger.error(f"Error starting GPS service: {e}")
            raise
    
    async def _run_service_loop(self) -> None:
        """Main service loop."""
        while self.running:
            try:
                # Get GPS data
                gps_data = await self.gps_handler.get_latest_data()
                
                if gps_data:
                    # Update HomeAssistant entities
                    await self.ha_interface.update_entities(gps_data)
                
                # Send RTCM corrections if available
                if self.ntrip_client:
                    corrections = await self.ntrip_client.get_corrections()
                    if corrections:
                        await self.gps_handler.send_corrections(corrections)
                
                # Update connection status
                status = {
                    'gps_connected': self.gps_handler.is_connected(),
                    'ntrip_connected': self.ntrip_client.is_connected() if self.ntrip_client else False,
                    'last_fix_time': gps_data.get('timestamp') if gps_data else None
                }
                await self.ha_interface.update_status(status)
                
                # Wait before next iteration
                await asyncio.sleep(1.0 / self.config.update_rate_hz)
                
            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def stop(self) -> None:
        """Stop the GPS service."""
        logger.info("Stopping u-blox GPS RTK service...")
        self.running = False
        
        if self.ntrip_client:
            await self.ntrip_client.stop()
        
        if self.gps_handler:
            await self.gps_handler.stop()
        
        logger.info("u-blox GPS RTK service stopped")

# Global service instance
service: Optional[UbloxGPSService] = None

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    if service and service.running:
        asyncio.create_task(service.stop())

async def main():
    """Main application entry point."""
    global service
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        service = UbloxGPSService()
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if service:
            await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
