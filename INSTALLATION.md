# Installation Guide

This guide walks you through installing and setting up the u-blox GPS RTK add-in for HomeAssistant.

## Prerequisites

### Hardware Requirements
- u-blox ZED-F9P GPS receiver
- USB cable (USB-A to USB-C or appropriate connector)
- GNSS antenna compatible with ZED-F9P
- HomeAssistant host with USB port access

### Software Requirements
- HomeAssistant OS, Supervised, or Container installation
- Add-in support enabled
- (Optional) NTRIP caster account for RTK corrections

## Step 1: Hardware Setup

### Connect GPS Device
1. Connect the GNSS antenna to your ZED-F9P receiver
2. Connect the ZED-F9P to your HomeAssistant host via USB
3. Position the antenna with clear sky view (ideally outdoors)
4. Power on the GPS receiver

### Verify USB Connection
1. SSH into your HomeAssistant host
2. Check for USB devices:
   ```bash
   ls /dev/tty*
   ```
3. Look for devices like `/dev/ttyUSB0` or `/dev/ttyACM0`
4. Note the device path for configuration

## Step 2: Add-in Installation

### Method 1: GitHub Repository (Recommended)
1. In HomeAssistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Add repository URL: `https://github.com/gsokoll/ublah`
4. Click **Add** and wait for repository to load
5. Find "u-blox GPS RTK" in the add-in list
6. Click **Install**

### Method 2: Local Installation
1. Clone this repository to your HomeAssistant add-ins directory
2. Restart HomeAssistant
3. The add-in should appear in the local add-ins section

## Step 3: Configuration

### Basic Configuration
1. Click on the installed "u-blox GPS RTK" add-in
2. Go to the **Configuration** tab
3. Configure the following settings:

```yaml
# GPS Device Settings
gps_device: "/dev/ttyUSB0"  # Update with your device path
gps_baudrate: 38400
update_rate_hz: 1
constellation: "GPS+GLONASS+GALILEO+BEIDOU"

# NTRIP Settings (optional)
ntrip_enabled: false  # Set to true to enable RTK
ntrip_host: ""
ntrip_port: 2101
ntrip_mountpoint: ""
ntrip_username: ""
ntrip_password: ""

# HomeAssistant Integration
homeassistant_url: "http://supervisor/core"
homeassistant_token: ""  # Add your long-lived access token
```

### HomeAssistant Access Token
1. In HomeAssistant, go to **Settings** → **People** → **Users**
2. Click on your user account
3. Scroll down to **Long-lived access tokens**
4. Click **Create Token**
5. Give it a name (e.g., "u-blox GPS RTK")
6. Copy the token and paste it in the add-in configuration

### NTRIP Configuration (Optional)
If you want RTK corrections for centimeter-level accuracy:

1. Obtain NTRIP caster credentials from your provider
2. Update the NTRIP settings in the configuration:
   ```yaml
   ntrip_enabled: true
   ntrip_host: "your-ntrip-caster.com"
   ntrip_port: 2101
   ntrip_mountpoint: "MOUNT_POINT_NAME"
   ntrip_username: "your_username"
   ntrip_password: "your_password"
   ```

## Step 4: Device Permissions

### USB Device Access
1. Go to add-in **Configuration** tab
2. Under **Network & USB**, ensure USB access is enabled
3. The add-in configuration already includes common USB device mappings

### Alternative Device Paths
If your GPS device uses a different path, update the configuration:
- Serial USB devices: `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc.
- ACM devices: `/dev/ttyACM0`, `/dev/ttyACM1`, etc.

## Step 5: Start the Add-in

1. Click **Start** on the add-in page
2. Monitor the **Log** tab for startup messages
3. Look for successful connection messages:
   ```
   Connected to GPS device at /dev/ttyUSB0 @ 38400 baud
   GPS device configuration complete
   u-blox GPS RTK service started successfully
   ```

## Step 6: Verify Installation

### Check HomeAssistant Entities
1. Go to **Settings** → **Devices & Services** → **Entities**
2. Filter by "ublox" to see GPS entities
3. Expected entities:
   - `device_tracker.ublox_gps`
   - `sensor.ublox_gps_fix_type`
   - `sensor.ublox_gps_satellites`
   - `sensor.ublox_gps_accuracy`
   - `binary_sensor.ublox_gps_connected`

### Test GPS Functionality
1. Check that `binary_sensor.ublox_gps_connected` shows "On"
2. Monitor `sensor.ublox_gps_satellites` for satellite count
3. Wait for GPS fix (may take 1-5 minutes outdoors)
4. Verify location in `device_tracker.ublox_gps`

## Common Installation Issues

### GPS Device Not Found
- **Problem**: Add-in logs show "GPS device not found"
- **Solution**: Check USB connection and update `gps_device` path

### Permission Denied
- **Problem**: "Permission denied" errors for USB device
- **Solution**: Ensure USB access is enabled in add-in configuration

### NTRIP Connection Failed
- **Problem**: NTRIP corrections not working
- **Solution**: Verify credentials and network connectivity

### No GPS Fix
- **Problem**: GPS shows "No Fix" status
- **Solution**: Ensure antenna has clear sky view, wait for satellite acquisition

## Advanced Configuration

### Multiple Constellations
Configure which GNSS constellations to use:
```yaml
constellation: "GPS+GLONASS+GALILEO"  # Exclude BEIDOU if needed
```

### Higher Update Rates
For applications requiring faster updates:
```yaml
update_rate_hz: 5  # 5Hz updates (maximum 10Hz)
```

### Custom Baudrate
If your device uses a different baudrate:
```yaml
gps_baudrate: 115200  # Common alternative baudrate
```

## Next Steps

After successful installation:
1. Add GPS entities to your HomeAssistant dashboard
2. Create automations based on GPS location
3. Monitor RTK performance if using NTRIP corrections
4. Consider creating backup configurations

## Support

If you encounter issues during installation:
1. Check the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) guide
2. Review add-in logs for error messages
3. Create an issue on GitHub with logs and configuration details
