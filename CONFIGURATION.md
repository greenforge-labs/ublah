# Configuration Reference

This document provides detailed information about all configuration options for the u-blox GPS RTK add-in.

## Configuration Schema

The add-in configuration is defined in `config.yaml` and validated against the schema. All settings can be modified through the HomeAssistant add-in configuration interface.

## GPS Device Settings

### `gps_device`
- **Type**: String
- **Default**: `/dev/ttyUSB0`
- **Description**: Path to the GPS device in the filesystem
- **Valid Values**: Any valid device path (e.g., `/dev/ttyUSB0`, `/dev/ttyACM0`)
- **Example**: `"/dev/ttyUSB1"`

### `gps_baudrate`
- **Type**: Integer
- **Default**: `38400`
- **Range**: 9600 - 115200
- **Description**: Serial communication baudrate with GPS device
- **Common Values**: 
  - `9600` - Basic communication
  - `38400` - Standard for ZED-F9P
  - `115200` - High-speed communication
- **Example**: `115200`

### `update_rate_hz`
- **Type**: Integer
- **Default**: `1`
- **Range**: 1 - 10
- **Description**: GPS position update frequency in Hertz
- **Notes**: 
  - Higher rates consume more CPU and bandwidth
  - RTK corrections work best at 1Hz
  - Consider device capabilities and network bandwidth
- **Example**: `5`

### `constellation`
- **Type**: List of Strings
- **Default**: `["GPS", "GLONASS", "GALILEO", "BEIDOU"]`
- **Valid Values**: 
  - `GPS` - US Global Positioning System
  - `GLONASS` - Russian GNSS
  - `GALILEO` - European GNSS
  - `BEIDOU` - Chinese GNSS
  - `QZSS` - Japanese regional system
  - `SBAS` - Satellite-Based Augmentation Systems
- **Examples**:
  ```yaml
  constellation: ["GPS", "GLONASS"]           # Dual constellation
  constellation: ["GPS", "GLONASS", "GALILEO"] # Triple constellation
  ```

## NTRIP Settings

### `ntrip_enabled`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Enable/disable NTRIP RTK corrections
- **Notes**: Set to `false` for basic GPS mode without RTK
- **Example**: `false`

### `ntrip_host`
- **Type**: String
- **Default**: `""`
- **Description**: Hostname or IP address of NTRIP caster
- **Format**: Domain name or IP address (without protocol)
- **Examples**:
  - `"rtk.emlid.com"` - Emlid RTK service
  - `"auscors.ga.gov.au"` - Australian CORS
  - `"192.168.1.100"` - Local RTK base station

### `ntrip_port`
- **Type**: Integer
- **Default**: `2101`
- **Range**: 1 - 65535
- **Description**: TCP port for NTRIP connection
- **Notes**: Standard NTRIP port is 2101
- **Example**: `2101`

### `ntrip_mountpoint`
- **Type**: String
- **Default**: `""`
- **Description**: NTRIP mountpoint/stream identifier
- **Format**: Alphanumeric string, usually uppercase
- **Notes**: Must match available mountpoint on caster
- **Examples**:
  - `"SYDN00AUS0"` - Sydney CORS station
  - `"RTCM3_GPS"` - Generic RTCM3 stream
  - `"VRS_3_4G"` - Virtual Reference Station

### `ntrip_username`
- **Type**: String (Optional)
- **Default**: `""`
- **Description**: Username for NTRIP authentication
- **Security**: Stored in plain text in configuration
- **Example**: `"user123"`

### `ntrip_password`
- **Type**: String (Optional)
- **Default**: `""`
- **Description**: Password for NTRIP authentication
- **Security**: Stored in plain text in configuration
- **Notes**: Use strong passwords and consider regular rotation
- **Example**: `"secure_password"`

## HomeAssistant Integration

### `homeassistant_url`
- **Type**: String
- **Default**: `"http://supervisor/core"`
- **Description**: URL for HomeAssistant API access
- **Valid Values**:
  - `"http://supervisor/core"` - For add-ins (recommended)
  - `"http://homeassistant.local:8123"` - External access
  - `"https://your-domain.com"` - Remote access
- **Example**: `"http://192.168.1.100:8123"`

### `homeassistant_token`
- **Type**: String (Optional)
- **Default**: `""`
- **Description**: Long-lived access token for HomeAssistant API
- **Security**: Keep secure and rotate regularly
- **Format**: Long alphanumeric string
- **Notes**: Required for entity creation and updates

## Advanced Configuration

### Environment Variables

The add-in also supports environment variables for certain settings:

- `LOG_LEVEL`: Set logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `CONFIG_PATH`: Override configuration file path
- `DATA_PATH`: Override data directory path

### Device Mapping

The add-in automatically maps common USB device paths:
```yaml
devices:
  - "/dev/ttyUSB0:/dev/ttyUSB0:rwm"
  - "/dev/ttyUSB1:/dev/ttyUSB1:rwm"
  - "/dev/ttyACM0:/dev/ttyACM0:rwm"
  - "/dev/ttyACM1:/dev/ttyACM1:rwm"
```

### Privileged Access

Required for direct hardware access:
```yaml
privileged:
  - SYS_RAWIO
```

## Configuration Examples

### Basic GPS Tracking
```yaml
gps_device: "/dev/ttyUSB0"
gps_baudrate: 38400
update_rate_hz: 1
constellation: ["GPS", "GLONASS"]
ntrip_enabled: false
homeassistant_url: "http://supervisor/core"
homeassistant_token: "your_token_here"
```

### RTK with Emlid Service
```yaml
gps_device: "/dev/ttyUSB0"
gps_baudrate: 38400
update_rate_hz: 1
constellation: ["GPS", "GLONASS", "GALILEO", "BEIDOU"]
ntrip_enabled: true
ntrip_host: "rtk.emlid.com"
ntrip_port: 2101
ntrip_mountpoint: "your_mountpoint"
ntrip_username: "your_username"
ntrip_password: "your_password"
homeassistant_url: "http://supervisor/core"
homeassistant_token: "your_token_here"
```

### High-Frequency Updates
```yaml
gps_device: "/dev/ttyUSB0"
gps_baudrate: 115200
update_rate_hz: 5
constellation: ["GPS", "GLONASS"]
ntrip_enabled: true
ntrip_host: "your_caster.com"
ntrip_port: 2101
ntrip_mountpoint: "HIGH_FREQ_STREAM"
ntrip_username: "user"
ntrip_password: "pass"
homeassistant_url: "http://supervisor/core"
homeassistant_token: "your_token_here"
```

### Local RTK Base Station
```yaml
gps_device: "/dev/ttyUSB0"
gps_baudrate: 38400
update_rate_hz: 1
constellation: ["GPS", "GLONASS", "GALILEO"]
ntrip_enabled: true
ntrip_host: "192.168.1.200"  # Local base station IP
ntrip_port: 2101
ntrip_mountpoint: "BASE_STATION"
ntrip_username: ""  # No authentication for local station
ntrip_password: ""
homeassistant_url: "http://supervisor/core"
homeassistant_token: "your_token_here"
```

## Configuration Validation

The add-in validates all configuration values on startup:

### Validation Rules
- **Required fields**: `gps_device`, `homeassistant_url`
- **Numeric ranges**: All numeric values checked against valid ranges
- **String formats**: URLs and device paths validated
- **Boolean values**: Must be `true` or `false`
- **Dependencies**: NTRIP settings required when `ntrip_enabled: true`

### Common Validation Errors
- Invalid device path format
- Baudrate outside valid range
- Missing NTRIP credentials when enabled
- Invalid HomeAssistant URL format
- Empty required fields

## Security Considerations

### Credential Storage
- NTRIP credentials stored in plain text
- HomeAssistant tokens stored in plain text
- Consider using secrets management for production

### Network Security
- NTRIP connections typically unencrypted
- Use VPN for public networks
- Firewall rules may be needed for NTRIP ports

### Access Control
- HomeAssistant tokens should have minimal required permissions
- Regular token rotation recommended
- Monitor for unauthorized access attempts

## Performance Tuning

### Low-Resource Systems
```yaml
update_rate_hz: 1
constellation: ["GPS", "GLONASS"]  # Limit to 2 constellations
gps_baudrate: 38400  # Standard baudrate
```

### High-Performance Systems
```yaml
update_rate_hz: 10
constellation: ["GPS", "GLONASS", "GALILEO", "BEIDOU"]
gps_baudrate: 115200
```

### Network-Constrained Environments
```yaml
update_rate_hz: 1
ntrip_enabled: false  # Disable if no reliable internet
```

## Troubleshooting Configuration

### Validation Failures
1. Check YAML syntax and indentation
2. Verify all required fields are present
3. Ensure values are within valid ranges
4. Check for typos in field names

### Connection Issues
1. Verify device paths exist: `ls /dev/tty*`
2. Test NTRIP connectivity: `telnet host port`
3. Validate HomeAssistant API access
4. Check network connectivity and firewall rules

### Performance Issues
1. Reduce update rate if system overloaded
2. Limit constellations for better performance
3. Lower baudrate if USB communication unstable
4. Monitor system resources and adjust accordingly
