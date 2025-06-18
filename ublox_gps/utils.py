"""
Utility functions for u-blox GPS RTK add-in.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    return c * r

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the bearing between two points on the earth.
    Returns bearing in degrees (0-360).
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    
    return bearing

def format_coordinates(lat: float, lon: float, precision: int = 6) -> Tuple[str, str]:
    """
    Format coordinates for display.
    Returns tuple of (formatted_lat, formatted_lon).
    """
    lat_dir = 'N' if lat >= 0 else 'S'
    lon_dir = 'E' if lon >= 0 else 'W'
    
    lat_str = f"{abs(lat):.{precision}f}°{lat_dir}"
    lon_str = f"{abs(lon):.{precision}f}°{lon_dir}"
    
    return lat_str, lon_str

def format_dms(decimal_degrees: float) -> str:
    """
    Convert decimal degrees to degrees, minutes, seconds format.
    """
    degrees = int(abs(decimal_degrees))
    minutes_float = (abs(decimal_degrees) - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    direction = 'N' if decimal_degrees >= 0 else 'S'
    if abs(decimal_degrees) > 180:  # Longitude
        direction = 'E' if decimal_degrees >= 0 else 'W'
    
    return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"

def get_fix_quality_description(fix_type: str) -> str:
    """
    Get human-readable description of GPS fix quality.
    """
    descriptions = {
        "No Fix": "No GPS signal",
        "Dead Reckoning": "Dead reckoning only",
        "2D Fix": "2D position fix",
        "3D Fix": "3D position fix",
        "GNSS + Dead Reckoning": "Combined GNSS and dead reckoning",
        "Time Only Fix": "Time-only fix",
        "RTK Float": "RTK float solution",
        "RTK Fixed": "RTK fixed solution (highest accuracy)",
        "DGPS": "Differential GPS"
    }
    return descriptions.get(fix_type, f"Unknown fix type: {fix_type}")

def is_rtk_fix(fix_type: str) -> bool:
    """Check if the fix type indicates RTK correction."""
    rtk_types = ["RTK Float", "RTK Fixed"]
    return fix_type in rtk_types

def get_accuracy_category(accuracy_cm: float) -> str:
    """
    Categorize GPS accuracy for display.
    """
    if accuracy_cm <= 5:
        return "Excellent (RTK)"
    elif accuracy_cm <= 50:
        return "Very Good"
    elif accuracy_cm <= 200:
        return "Good"
    elif accuracy_cm <= 500:
        return "Fair"
    else:
        return "Poor"

def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate GPS coordinates.
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180

class PerformanceMonitor:
    """Monitor GPS performance metrics."""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.accuracy_history = []
        self.fix_history = []
        self.satellite_history = []
        self.timestamps = []
    
    def add_measurement(self, accuracy: float, fix_type: str, satellites: int):
        """Add a new measurement to the performance monitor."""
        now = datetime.utcnow()
        
        self.accuracy_history.append(accuracy)
        self.fix_history.append(fix_type)
        self.satellite_history.append(satellites)
        self.timestamps.append(now)
        
        # Remove old measurements outside the window
        cutoff_time = now - timedelta(seconds=self.window_size)
        while self.timestamps and self.timestamps[0] < cutoff_time:
            self.timestamps.pop(0)
            self.accuracy_history.pop(0)
            self.fix_history.pop(0)
            self.satellite_history.pop(0)
    
    def get_average_accuracy(self) -> Optional[float]:
        """Get average accuracy over the monitoring window."""
        if not self.accuracy_history:
            return None
        return sum(self.accuracy_history) / len(self.accuracy_history)
    
    def get_average_satellites(self) -> Optional[float]:
        """Get average satellite count over the monitoring window."""
        if not self.satellite_history:
            return None
        return sum(self.satellite_history) / len(self.satellite_history)
    
    def get_rtk_availability(self) -> Optional[float]:
        """Get percentage of time with RTK fix."""
        if not self.fix_history:
            return None
        
        rtk_count = sum(1 for fix in self.fix_history if is_rtk_fix(fix))
        return (rtk_count / len(self.fix_history)) * 100
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            'avg_accuracy_cm': self.get_average_accuracy(),
            'avg_satellites': self.get_average_satellites(),
            'rtk_availability_percent': self.get_rtk_availability(),
            'measurement_count': len(self.accuracy_history),
            'window_size_seconds': self.window_size
        }

async def retry_with_backoff(
    func, 
    max_retries: int = 3, 
    initial_delay: float = 1.0, 
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """
    Retry a function with exponential backoff.
    """
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except exceptions as e:
            if attempt == max_retries:
                logger.error(f"Function failed after {max_retries} retries: {e}")
                raise
            
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
            delay *= backoff_factor

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def get_constellation_from_satellite_id(satellite_id: int) -> str:
    """
    Determine constellation from satellite ID.
    Based on standard GNSS satellite numbering.
    """
    if 1 <= satellite_id <= 32:
        return "GPS"
    elif 65 <= satellite_id <= 96:
        return "GLONASS"
    elif 120 <= satellite_id <= 158:
        return "SBAS"
    elif 159 <= satellite_id <= 163:
        return "SBAS"
    elif 173 <= satellite_id <= 182:
        return "IMES"
    elif 193 <= satellite_id <= 202:
        return "QZSS"
    elif 211 <= satellite_id <= 246:
        return "Galileo"
    elif 301 <= satellite_id <= 336:
        return "BeiDou"
    else:
        return "Unknown"
