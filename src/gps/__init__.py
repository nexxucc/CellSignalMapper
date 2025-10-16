"""GPS module for coordinate acquisition"""

from .gps_module import GPSReader, GPSCoordinate, MockGPSReader
from .windows_gps import WindowsGPSReader

# MAVLink GPS support (Pixhawk/PX4)
try:
    from .mavlink_gps import MAVLinkGPSReader, MAVLinkGPSReaderWithCompass
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False
    MAVLinkGPSReader = None
    MAVLinkGPSReaderWithCompass = None

__all__ = [
    'GPSReader',
    'GPSCoordinate',
    'MockGPSReader',
    'WindowsGPSReader',
    'MAVLinkGPSReader',
    'MAVLinkGPSReaderWithCompass',
    'MAVLINK_AVAILABLE'
]
