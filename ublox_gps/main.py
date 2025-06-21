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
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Initializing GPS service components...")
            logger.info("🔍 DEBUG: Step 1/5: Loading configuration...")
            logger.info(f"🔍 DEBUG: GPS Device: {self.config.gps_device}")
            logger.info(f"🔍 DEBUG: GPS Baudrate: {self.config.gps_baudrate}")
            logger.info(f"🔍 DEBUG: Device Type: {self.config.device_type}")
            logger.info(f"🔍 DEBUG: NTRIP Enabled: {self.config.ntrip_enabled}")
            logger.info(f"🔍 DEBUG: HomeAssistant URL: {self.config.homeassistant_url}")
            # =========================== DEBUG LOGGING END =============================
            
            # Initialize components
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Step 2/5: Creating GPSHandler instance...")
            # =========================== DEBUG LOGGING END =============================
            self.gps_handler = GPSHandler(self.config)
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Step 3/5: Creating HomeAssistantInterface instance...")
            # =========================== DEBUG LOGGING END =============================
            self.ha_interface = HomeAssistantInterface(self.config)
            
            # Initialize NTRIP client if enabled
            if self.config.ntrip_enabled and self.config.ntrip_host:
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Step 4a/5: Creating NTRIPClient instance (NTRIP enabled)...")
                # =========================== DEBUG LOGGING END =============================
                self.ntrip_client = NTRIPClient(self.config)
            else:
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Step 4b/5: Skipping NTRIP client (disabled or no host)...")
                # =========================== DEBUG LOGGING END =============================
            
            # Start GPS handler
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Step 5a/5: Starting GPS handler (CRITICAL STEP)...")
            # =========================== DEBUG LOGGING END =============================
            await self.gps_handler.start()
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: ✅ GPS handler started successfully!")
            logger.info(f"🔍 DEBUG: GPS handler connected status: {self.gps_handler.connected}")
            # =========================== DEBUG LOGGING END =============================
            
            # Start NTRIP client if configured
            if self.ntrip_client:
                # =========================== DEBUG LOGGING START ===========================
                logger.info("🔍 DEBUG: Step 5b/5: Starting NTRIP client...")
                # =========================== DEBUG LOGGING END =============================
                await self.ntrip_client.start()
            
            # Initialize HomeAssistant entities
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: Step 5c/5: Initializing HomeAssistant entities...")
            # =========================== DEBUG LOGGING END =============================
            await self.ha_interface.initialize_entities()
            
            # =========================== DEBUG LOGGING START ===========================
            logger.info("🔍 DEBUG: ✅ HomeAssistant entities initialized!")
            # =========================== DEBUG LOGGING END =============================
            
            self.running = True
            logger.info("u-blox GPS RTK service started successfully")
            
            # Main service loop
            await self._run_service_loop()
            
        except Exception as e:
            # =========================== DEBUG LOGGING START ===========================
            logger.error(f"🔍 DEBUG: ❌ CRITICAL ERROR in service startup: {e}")
            logger.error(f"🔍 DEBUG: Exception type: {type(e)}")
            import traceback
            logger.error(f"🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            # =========================== DEBUG LOGGING END =============================
            logger.error(f"Error starting GPS service: {e}")
            raise
    
    async def _run_service_loop(self) -> None:
        """Main service loop."""
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                if loop_count % 10 == 0:  # Log every 10 loops
                    logger.info(f"🔍 DEBUG: Service loop iteration #{loop_count}")
                
                # =========================== DEBUG LOGGING START ===========================
                logger.info(f"🔍 DEBUG: Calling gps_handler.get_latest_data() (sync method)")
                # =========================== DEBUG LOGGING END =============================
                
                # Get GPS data (now sync method, no await needed)
                gps_data = self.gps_handler.get_latest_data()
                
                if gps_data:
                    logger.info(f"🔍 DEBUG: Service loop got GPS data with keys: {list(gps_data.keys())}")
                    logger.info(f"🔍 DEBUG: GPS data timestamp: {gps_data.get('timestamp', 'No timestamp')}")
                else:
                    if loop_count % 20 == 0:  # Log every 20 loops when no data
                        logger.warning(f"🔍 DEBUG: Service loop got no GPS data (iteration #{loop_count})")
                
                if gps_data:
                    logger.info(f"🔍 DEBUG: Calling ha_interface.update_entities() with GPS data")
                    
                    # Update HomeAssistant entities
                    await self.ha_interface.update_entities(gps_data)
                
                # Send RTCM corrections if available
                if self.ntrip_client:
                    corrections = await self.ntrip_client.get_corrections()
                    if corrections:
                        await self.gps_handler.send_corrections(corrections)
                
                # Sleep to prevent excessive polling
                await asyncio.sleep(1)
                
            except Exception as e:
                loop_count += 1
                logger.error(f"🔍 DEBUG: Error in service loop iteration #{loop_count}: {e}")
                logger.error(f"Error in service loop: {e}")
                await asyncio.sleep(1)
    
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
