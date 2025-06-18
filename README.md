# u-blox GPS RTK Add-in for HomeAssistant

A HomeAssistant add-in that provides RTK GPS functionality using u-blox ZED-F9P devices with NTRIP correction data.

## Overview

This add-in connects to a u-blox ZED-F9P GPS receiver via USB and provides high-precision GPS location data to HomeAssistant. It supports RTK corrections via NTRIP casters for centimeter-level accuracy, making it ideal for rover applications, precision agriculture, surveying, and other applications requiring high-accuracy positioning.

## Features

- **High-Precision GPS**: Supports u-blox ZED-F9P for RTK positioning
- **NTRIP Corrections**: Compatible with Emlid, AUSCORS, and generic NTRIP casters
- **HomeAssistant Integration**: Native entities for location, status, and GPS metrics
- **Configurable**: Support for multiple constellations and update rates
- **Robust**: Automatic reconnection and error handling
- **Monitoring**: Real-time status and performance metrics

## HomeAssistant Entities

The add-in creates the following entities in HomeAssistant:

### Device Tracker
- `device_tracker.ublox_gps` - GPS location with high precision coordinates

### Sensors
- `sensor.ublox_gps_fix_type` - GPS fix type (2D, 3D, RTK Float, RTK Fixed)
- `sensor.ublox_gps_satellites` - Number of satellites in view
- `sensor.ublox_gps_accuracy` - Horizontal accuracy in centimeters
- `sensor.ublox_gps_altitude` - Altitude above mean sea level in meters
- `sensor.ublox_gps_speed` - Ground speed in m/s
- `sensor.ublox_gps_heading` - Heading/course in degrees

### Binary Sensors
- `binary_sensor.ublox_gps_connected` - GPS device connection status
- `binary_sensor.ublox_ntrip_connected` - NTRIP caster connection status

## Requirements

### Hardware
- u-blox ZED-F9P GPS receiver
- USB connection to HomeAssistant host
- GNSS antenna suitable for RTK operation

### Software
- HomeAssistant with add-in support
- NTRIP caster access (optional but recommended for RTK)

## Installation

1. **Add Repository**: Add this repository to your HomeAssistant add-in repositories
2. **Install Add-in**: Install the "u-blox GPS RTK" add-in
3. **Connect Hardware**: Connect your ZED-F9P device via USB
4. **Configure**: Set up the add-in configuration (see Configuration section)
5. **Start**: Start the add-in

## Configuration

Configure the add-in through the HomeAssistant add-in configuration interface:

### GPS Settings
```yaml
gps_device: "/dev/ttyUSB0"          # USB device path
gps_baudrate: 38400                 # Serial baudrate
update_rate_hz: 1                   # GPS update rate (1-10 Hz)
constellation: "GPS+GLONASS+GALILEO+BEIDOU"  # GNSS constellations
```

### NTRIP Settings (Optional)
```yaml
ntrip_enabled: true
ntrip_host: "rtk.your-provider.com"
ntrip_port: 2101
ntrip_mountpoint: "YOUR_MOUNTPOINT"
ntrip_username: "your_username"
ntrip_password: "your_password"
```

### HomeAssistant Integration
```yaml
homeassistant_url: "http://supervisor/core"
homeassistant_token: "your_long_lived_access_token"
```

## Supported NTRIP Casters

- **Emlid**: Commercial RTK service with global coverage
- **AUSCORS**: Australian government RTK network
- **Generic NTRIP**: Any standard NTRIP caster

## Usage

### Basic GPS Tracking
1. Configure GPS device settings
2. Start the add-in
3. Monitor GPS entities in HomeAssistant

### RTK Mode
1. Configure NTRIP caster settings
2. Ensure clear sky view for GPS antenna
3. Wait for RTK convergence (typically 1-5 minutes)
4. Monitor fix type - "RTK Fixed" indicates highest accuracy

### Performance Monitoring
- Check `sensor.ublox_gps_accuracy` for current precision
- Monitor `sensor.ublox_gps_satellites` for signal quality
- Use `binary_sensor.ublox_ntrip_connected` to verify corrections

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting guide.

### Common Issues
- **GPS device not found**: Check USB connection and device path
- **NTRIP connection failed**: Verify credentials and network connectivity
- **Poor accuracy**: Ensure clear sky view and RTK convergence

## Development

### Building
```bash
docker build -t ublox-gps-rtk .
```

### Testing
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussion**: Use GitHub Discussions for questions and ideas
- **Email**: geoff.s@greenforgelabs.com.au

## Acknowledgments

- u-blox for the excellent ZED-F9P GPS receiver
- HomeAssistant community for the add-in framework
- NTRIP caster providers for RTK correction services
