"""GPS module for coordinate acquisition"""

from .gps_module import GPSReader, GPSCoordinate, MockGPSReader
from .windows_gps import WindowsGPSReader

__all__ = ['GPSReader', 'GPSCoordinate', 'MockGPSReader', 'WindowsGPSReader']
