# Troubleshooting Guide

This guide helps resolve common issues with the u-blox GPS RTK add-in.

## General Troubleshooting Steps

1. **Check Add-in Logs**: Always start by reviewing the add-in logs in HomeAssistant
2. **Verify Hardware**: Ensure GPS device is properly connected and powered
3. **Check Configuration**: Validate all configuration parameters
4. **Network Connectivity**: Verify internet access for NTRIP connections
5. **Restart Services**: Try restarting the add-in or HomeAssistant

## GPS Device Issues

### GPS Device Not Found

**Symptoms:**
- Add-in logs: "GPS device not found at /dev/ttyUSB0"
- No GPS data in HomeAssistant entities

**Causes & Solutions:**

1. **Wrong Device Path**
   ```bash
   # Check available USB devices
   ls /dev/tty*
   # Look for ttyUSB* or ttyACM* devices
   ```
   Update `gps_device` in configuration to correct path.

2. **USB Connection Issues**
   - Check physical USB cable connection
   - Try a different USB port
   - Test cable with another device

3. **Device Permissions**
   - Ensure add-in has USB device access enabled
   - Check that USB devices are mapped in configuration

4. **Device Already in Use**
   - Stop any other applications using the GPS device
   - Restart the add-in

### GPS Device Connected but No Fix

**Symptoms:**
- Device shows as connected
- Fix type remains "No Fix"
- Zero satellites visible

**Causes & Solutions:**

1. **Antenna Issues**
   - Ensure antenna has clear sky view
   - Move antenna away from buildings/obstacles
   - Check antenna cable connections
   - Verify antenna is suitable for GPS frequencies

2. **Cold Start**
   - Allow 5-15 minutes for initial GPS acquisition
   - Device may need to download almanac data

3. **Interference**
   - Move away from WiFi routers, cell towers
   - Check for nearby electronic devices causing interference
   - Use a GPS antenna with better filtering

### Poor GPS Accuracy

**Symptoms:**
- GPS fix available but accuracy > 5 meters
- Fix type shows "2D" or "3D" instead of "RTK"

**Causes & Solutions:**

1. **No RTK Corrections**
   - Verify NTRIP connection is active
   - Check `binary_sensor.ublox_ntrip_connected` status
   - Validate NTRIP credentials and settings

2. **Multipath Effects**
   - Ensure antenna has clear view in all directions
   - Avoid reflective surfaces (metal roofs, water)
   - Use ground plane under antenna if needed

3. **Atmospheric Conditions**
   - GPS accuracy varies with ionospheric activity
   - Performance may degrade during storms
   - RTK corrections help mitigate these effects

## NTRIP Connection Issues

### NTRIP Authentication Failed

**Symptoms:**
- Add-in logs: "NTRIP authentication failed"
- NTRIP connection shows as disconnected

**Solutions:**
1. Verify username and password are correct
2. Check account status with NTRIP provider
3. Ensure account hasn't expired
4. Try connecting with different NTRIP client to test credentials

### NTRIP Connection Timeout

**Symptoms:**
- Add-in logs: "NTRIP connection failed" or timeout errors
- Intermittent NTRIP connectivity

**Causes & Solutions:**

1. **Network Issues**
   - Check internet connectivity from HomeAssistant host
   - Test DNS resolution: `nslookup your-ntrip-caster.com`
   - Try different network or mobile hotspot

2. **Firewall/Proxy**
   - Ensure port 2101 (or your NTRIP port) is not blocked
   - Check for corporate firewall restrictions
   - Configure proxy settings if required

3. **NTRIP Caster Issues**
   - Try different mountpoint if available
   - Contact NTRIP provider for service status
   - Check provider's website for outages

### Wrong Mountpoint

**Symptoms:**
- Add-in logs: "NTRIP mountpoint not found"
- 404 errors in logs

**Solutions:**
1. Verify mountpoint name with NTRIP provider
2. Get source table from caster to see available mountpoints
3. Ensure mountpoint covers your geographic area
4. Check if mountpoint requires special permissions

## HomeAssistant Integration Issues

### Entities Not Created

**Symptoms:**
- GPS entities missing from HomeAssistant
- No device tracker or sensors visible

**Causes & Solutions:**

1. **Missing Access Token**
   - Configure `homeassistant_token` in add-in settings
   - Create long-lived access token in HomeAssistant
   - Ensure token has necessary permissions

2. **Wrong HomeAssistant URL**
   - For add-ins, use: `http://supervisor/core`
   - For external instances, use full URL with port

3. **API Connectivity**
   - Check HomeAssistant API is accessible
   - Verify no firewall blocking internal communication

### Entities Show "Unavailable"

**Symptoms:**
- Entities exist but show "unavailable" state
- No data updates in entity history

**Causes & Solutions:**

1. **GPS Not Connected**
   - Fix GPS device connection issues first
   - Check GPS status entities

2. **Add-in Crashed**
   - Check add-in logs for Python errors
   - Restart the add-in
   - Report bugs if crashes persist

3. **API Token Expired**
   - Regenerate HomeAssistant access token
   - Update token in add-in configuration

## Performance Issues

### High CPU Usage

**Symptoms:**
- HomeAssistant host showing high CPU usage
- Add-in consuming excessive resources

**Solutions:**
1. Reduce GPS update rate: `update_rate_hz: 1`
2. Limit constellations: `constellation: "GPS+GLONASS"`
3. Check for infinite loops in logs
4. Restart add-in to clear any memory leaks

### Slow GPS Updates

**Symptoms:**
- GPS data updates less frequently than configured
- Delayed location updates in HomeAssistant

**Causes & Solutions:**

1. **Serial Communication Issues**
   - Try lower baudrate: `gps_baudrate: 9600`
   - Check USB cable quality
   - Reduce update rate if data overrun occurs

2. **Network Congestion**
   - NTRIP corrections may be delayed
   - Check network bandwidth usage
   - Consider local RTK base station

## Configuration Issues

### Invalid Configuration

**Symptoms:**
- Add-in fails to start
- Configuration validation errors

**Solutions:**
1. Check YAML syntax for proper formatting
2. Validate all required fields are present
3. Ensure numeric values are within valid ranges
4. Reset to default configuration if needed

### Schema Validation Errors

**Common Fixes:**
- `gps_baudrate`: Must be between 9600-115200
- `update_rate_hz`: Must be between 1-10
- `ntrip_port`: Must be between 1-65535
- Boolean values: Use `true`/`false`, not `yes`/`no`

## Hardware-Specific Issues

### u-blox ZED-F9P Specific

1. **Firmware Version**
   - Ensure device has recent firmware
   - Some features may require specific firmware versions

2. **Configuration Conflicts**
   - Device may have conflicting stored configuration
   - Consider factory reset if issues persist

3. **Power Supply**
   - Ensure adequate USB power (500mA minimum)
   - Some hosts may not provide sufficient current

## Diagnostic Commands

### Check USB Devices
```bash
# List all USB devices
lsusb

# List serial devices
ls -la /dev/tty*

# Check device permissions
ls -la /dev/ttyUSB0
```

### Test GPS Communication
```bash
# Read raw GPS data (if accessible)
cat /dev/ttyUSB0

# Check device is responsive
echo -e '\xB5\x62\x06\x00\x14\x00\x01\x00\x00\x00\xD0\x08\x00\x00\x80\x25\x00\x00\x07\x00\x03\x00\x00\x00\x00\x00\xA2\xB5' > /dev/ttyUSB0
```

### Network Connectivity
```bash
# Test NTRIP caster connectivity
telnet your-ntrip-caster.com 2101

# Check DNS resolution
nslookup your-ntrip-caster.com
```

## Log Analysis

### Important Log Messages

**Successful Startup:**
```
Connected to GPS device at /dev/ttyUSB0 @ 38400 baud
GPS device configuration complete
Connected to NTRIP caster: your-caster.com
u-blox GPS RTK service started successfully
```

**Error Indicators:**
- `Failed to connect to GPS device`
- `NTRIP authentication failed`
- `Permission denied`
- `Device not found`
- `Connection timeout`

### Enabling Debug Logging

Add to add-in configuration for more detailed logs:
```yaml
log_level: DEBUG
```

## Getting Help

### Before Reporting Issues

1. Collect add-in logs from HomeAssistant
2. Note your hardware configuration
3. Include your add-in configuration (remove passwords)
4. Describe what you were trying to achieve
5. List troubleshooting steps already attempted

### Contact Information

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and usage help
- **Email**: geoff.s@greenforgelabs.com.au for direct support

### Information to Include

- HomeAssistant version
- Add-in version
- GPS device model and firmware
- NTRIP caster provider (if applicable)
- Complete error logs
- Configuration file (sanitized)
