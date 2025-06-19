#!/usr/bin/env python3
"""
Run GPS Service with Enhanced Debugging
This script runs the GPS service with detailed debugging to identify data flow issues
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Add the ublox_gps module to the path
sys.path.insert(0, str(Path(__file__).parent / 'ublox_gps'))

from main import UbloxGPSService

# Configure enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('gps_debug_detailed.log')
    ]
)

logger = logging.getLogger(__name__)

# Global service instance for signal handling
service = None

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    if service:
        asyncio.create_task(service.stop())

async def run_debug_session(duration_minutes=5):
    """Run a debug session for specified duration."""
    global service
    
    logger.info(f"🔍 Starting {duration_minutes}-minute GPS debug session...")
    logger.info("🔍 This will help identify where GPS data flow is breaking")
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        service = UbloxGPSService()
        
        # Start the service
        logger.info("🚀 Starting GPS service with enhanced debugging...")
        await service.start()
        
        # Run for specified duration
        logger.info(f"⏱️ Running debug session for {duration_minutes} minutes...")
        logger.info("⏱️ Watch the logs below to see data flow...")
        logger.info("⏱️ Press Ctrl+C to stop early")
        
        await asyncio.sleep(duration_minutes * 60)
        
    except KeyboardInterrupt:
        logger.info("🛑 Debug session interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error during debug session: {e}")
    finally:
        if service:
            logger.info("🛑 Stopping GPS service...")
            await service.stop()
            logger.info("✅ GPS service stopped")

async def main():
    """Main debug function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug GPS service with enhanced logging')
    parser.add_argument('--duration', type=int, default=5, help='Debug duration in minutes (default: 5)')
    
    args = parser.parse_args()
    
    print("🔍 GPS Debug Session Starting")
    print("=" * 50)
    print(f"Duration: {args.duration} minutes")
    print(f"Log file: gps_debug_detailed.log")
    print("=" * 50)
    print()
    print("🔍 What to look for in the logs:")
    print("   📡 'Starting GPS data read loop' - GPS reader started")
    print("   📥 'Received X bytes' - Raw data from GPS device")
    print("   🛰️ 'Processing UBX message' - Message parsing")
    print("   📍 'NAV-PVT processed' - Position data updates")
    print("   📊 'GPS data received' - Data flowing to HomeAssistant")
    print("   ❌ Any error messages")
    print()
    print("Press Ctrl+C to stop early...")
    print("=" * 50)
    
    await run_debug_session(args.duration)
    
    print()
    print("🔍 Debug Session Complete")
    print("=" * 50)
    print("📄 Check 'gps_debug_detailed.log' for full details")
    print()
    print("🔍 Quick Diagnosis:")
    print("   • If you see 'Starting GPS data read loop' = GPS handler started OK")
    print("   • If you see 'Received X bytes' = GPS device is sending data")
    print("   • If you see 'Processing UBX message' = Messages are being parsed")
    print("   • If you see 'GPS data received' = Data is flowing to HomeAssistant")
    print("   • If you see lots of ❌ errors = Check those specific error messages")
    print()
    print("💡 Next steps:")
    print("   1. Review the log output above")
    print("   2. Check gps_debug_detailed.log for more details")
    print("   3. Share relevant log excerpts for further diagnosis")

if __name__ == "__main__":
    asyncio.run(main())
