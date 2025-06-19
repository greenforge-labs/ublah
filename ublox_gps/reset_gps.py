#!/usr/bin/env python3
"""
Reset and reconfigure GPS device
Run this to force GPS device back to active UBX mode
"""

import asyncio
import serial_asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_gps_device():
    """Reset GPS device and force UBX output."""
    device_path = "/dev/ttyUSB0"
    
    # Try multiple baudrates
    baudrates = [38400, 9600, 115200, 19200, 4800]
    
    for baudrate in baudrates:
        logger.info(f"🔧 Trying to connect at {baudrate} baud...")
        
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=device_path,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=2
            )
            
            logger.info(f"✅ Connected at {baudrate} baud")
            
            # Send GPS reset commands
            commands = [
                # Software reset
                b'\xb5\x62\x06\x04\x04\x00\xff\xff\x02\x00\x0e\x61',
                # Enable UBX NAV-PVT messages
                b'\xb5\x62\x06\x01\x08\x00\x01\x07\x01\x00\x00\x00\x00\x00\x18\xe1',
                # Set baudrate to 38400
                b'\xb5\x62\x06\x00\x14\x00\x01\x00\x00\x00\xd0\x08\x00\x00\x00\x96\x00\x00\x07\x00\x03\x00\x00\x00\x00\x00\x93\x90',
            ]
            
            for i, cmd in enumerate(commands):
                logger.info(f"📤 Sending command {i+1}/{len(commands)}")
                writer.write(cmd)
                await writer.drain()
                await asyncio.sleep(1)
            
            # Check for response
            logger.info("📡 Listening for response...")
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                if data:
                    logger.info(f"📥 Received {len(data)} bytes: {data[:50].hex()}...")
                else:
                    logger.warning("No response from GPS device")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for GPS response")
            
            writer.close()
            await writer.wait_closed()
            
            # If we got this far, the device responded
            logger.info(f"✅ GPS device responded at {baudrate} baud")
            break
            
        except Exception as e:
            logger.debug(f"Failed at {baudrate} baud: {e}")
            continue
    
    logger.info("🔧 GPS reset completed. Restart your add-on to test.")

if __name__ == "__main__":
    asyncio.run(reset_gps_device())
