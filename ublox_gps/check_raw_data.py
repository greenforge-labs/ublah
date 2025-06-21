#!/usr/bin/env python3
"""
Quick raw data checker for GPS device
Run this directly in the Home Assistant add-on to check if GPS is sending data
"""

import asyncio
import serial_asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_raw_gps_data():
    """Check if GPS device is sending any raw data."""
    device_path = "/dev/ttyACM0"
    baudrate = 38400
    
    logger.info(f"🔍 Checking raw data from {device_path} @ {baudrate} baud...")
    
    try:
        # Open serial connection
        reader, writer = await serial_asyncio.open_serial_connection(
            url=device_path,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        
        logger.info(f"✅ Serial connection opened successfully")
        
        # Read data for 30 seconds
        start_time = asyncio.get_event_loop().time()
        total_bytes = 0
        data_chunks = 0
        
        logger.info("📡 Listening for data (30 seconds)...")
        
        while asyncio.get_event_loop().time() - start_time < 30:
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                if data:
                    total_bytes += len(data)
                    data_chunks += 1
                    logger.info(f"📥 Chunk #{data_chunks}: {len(data)} bytes")
                    logger.info(f"📥 Data sample: {data[:50].hex()}...")
                    
                    # Check for UBX signatures
                    if b'\xb5\x62' in data:
                        logger.info("🛰️ UBX messages detected!")
                    
                    # Check for NMEA signatures  
                    if b'$' in data:
                        logger.info("📍 NMEA messages detected!")
                        
                else:
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                logger.debug("No data received in last second...")
                continue
                
        # Results
        logger.info(f"📊 Results after 30 seconds:")
        logger.info(f"   • Total bytes received: {total_bytes}")
        logger.info(f"   • Data chunks: {data_chunks}")
        
        if total_bytes == 0:
            logger.error("❌ NO DATA RECEIVED - GPS device not transmitting!")
            logger.error("❌ Possible issues:")
            logger.error("   - GPS device not powered")
            logger.error("   - Wrong device path")
            logger.error("   - Wrong baudrate")
            logger.error("   - Hardware connection issue")
            logger.error("   - GPS device in wrong mode")
        else:
            logger.info("✅ GPS device is transmitting data")
            
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to GPS device: {e}")
        logger.error("❌ Check:")
        logger.error("   - Device path (/dev/ttyUSB0)")
        logger.error("   - Device permissions")
        logger.error("   - Hardware connections")

if __name__ == "__main__":
    asyncio.run(check_raw_gps_data())
