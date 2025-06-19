# Project Planning - Ublox GPS RTK Add-in

## Project Overview
HomeAssistant add-in providing RTK GPS functionality using u-blox ZED-F9P/ZED-F9R devices with NTRIP correction data for centimeter-level accuracy.

## Architecture Goals
- **Modularity**: Clear separation between GPS handling, NTRIP client, and HA interface
- **Device Support**: Unified support for both ZED-F9P and ZED-F9R devices
- **Sensor Fusion**: Leverage ZED-F9R's dead reckoning and inertial sensor capabilities
- **Reliability**: Robust error handling and automatic recovery
- **Performance**: Efficient message processing and minimal memory footprint

## Current Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   UbloxGPS      │    │   GPS Handler    │    │  NTRIP Client     │
│   Service       │◄──►│  - Serial Comm   │    │  - RTCM Data      │
│   (main.py)     │    │  - UBX/NMEA      │    │  - Corrections    │
└─────────────────┘    │  - Configuration │    └───────────────────┘
         │              └──────────────────┘              │
         ▼                        │                       │
┌─────────────────┐              │                       │
│ HomeAssistant   │◄─────────────┘                       │
│ Interface       │◄───────────────────────────────────────┘
│ - Entities      │
│ - State Updates │
└─────────────────┘
```

## File Structure & Conventions
```
ublox_gps/
├── __init__.py          # Package initialization
├── main.py              # Service orchestrator  
├── gps_handler.py       # GPS device communication
├── ntrip_client.py      # RTCM correction handling
├── ha_interface.py      # HomeAssistant integration
├── config.py            # Configuration management
└── utils.py             # Shared utilities
```

## Naming Conventions
- **Classes**: PascalCase (e.g., `GPSHandler`, `NTRIPClient`)
- **Methods**: snake_case (e.g., `process_ubx_message`, `send_corrections`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `SUPPORTED_MESSAGES`, `DEFAULT_BAUDRATE`)
- **Files**: snake_case (e.g., `gps_handler.py`, `ntrip_client.py`)

## ZED-F9R Enhancement Strategy
### Phase 1: Core ZED-F9R Support
- Add HNR-PVT and ESF-INS message parsing for sensor fusion
- Implement UBX-CFG-NAVSPG and UBX-CFG-DYNMODEL configuration
- Enhanced fix type detection with RTK Float/Fixed states

### Phase 2: RTCM Enhancement  
- RTCM message filtering (1005, 1077, 1087, 1097, 1127)
- Message validation and statistics

### Phase 3: Robustness & Features
- Enhanced error handling and recovery
- Data validation and quality assurance
- Performance monitoring and diagnostics

## Code Style Guidelines
- **Python Style**: Follow PEP 8 with 4-space indentation
- **Type Hints**: Use type annotations for all function parameters and returns
- **Documentation**: Docstrings for all classes and public methods
- **Error Handling**: Comprehensive try/catch with appropriate logging
- **Async/Await**: Use async patterns for I/O operations

## Testing Strategy
- Unit tests for message parsing and configuration logic
- Integration tests for device communication
- Mock testing for NTRIP client functionality
- End-to-end testing with HomeAssistant integration

## Dependencies
- **pyubx2**: UBX message parsing and generation
- **pynmea2**: NMEA message parsing  
- **pyserial**: Serial communication
- **aiohttp**: Async HTTP for NTRIP client
- **pyyaml**: Configuration file parsing
