"""
Windows GPS Module
Uses Windows Location API to get GPS coordinates from laptop
"""

import logging
from typing import Optional
from datetime import datetime
import time
import subprocess
import json

from .gps_module import GPSCoordinate

logger = logging.getLogger(__name__)


class WindowsGPSReader:
    """GPS reader for Windows laptops using PowerShell location API"""

    def __init__(self, config: dict):
        """
        Initialize Windows GPS reader

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.is_connected = False
        self.last_valid_position: Optional[GPSCoordinate] = None
        self._powershell_script = None

    def connect(self) -> bool:
        """
        Connect to Windows location services

        Returns:
            True if successful, False otherwise
        """
        if not self.config['gps']['enabled']:
            logger.info("GPS is disabled in configuration")
            return False

        try:
            logger.info("Connecting to Windows Location Services...")
            logger.info("IMPORTANT: Enable Location in Windows Settings:")
            logger.info("  Settings > Privacy & security > Location > Location services: ON")
            logger.info("  Allow apps to access your location: ON")

            # Create PowerShell script to access location
            self._powershell_script = '''
Add-Type -AssemblyName System.Device
$watcher = New-Object System.Device.Location.GeoCoordinateWatcher
$watcher.Start()
$timeout = 30
$counter = 0
while (($watcher.Status -ne 'Ready') -and ($counter -lt $timeout)) {
    Start-Sleep -Milliseconds 100
    $counter += 0.1
}
if ($watcher.Status -eq 'Ready') {
    $coord = $watcher.Position.Location
    @{
        latitude = $coord.Latitude
        longitude = $coord.Longitude
        altitude = $coord.Altitude
    } | ConvertTo-Json
} else {
    Write-Error "Location not available"
}
$watcher.Stop()
'''

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Windows GPS: {e}")
            self.is_connected = False
            return False

    def read_position(self, timeout: float = 5.0) -> Optional[GPSCoordinate]:
        """
        Read current GPS position from Windows

        Args:
            timeout: Maximum time to wait for valid GPS data (seconds)

        Returns:
            GPSCoordinate object or None if no valid fix
        """
        if not self.is_connected:
            logger.warning("GPS not connected")
            return self.last_valid_position

        try:
            # Run PowerShell script to get location
            result = subprocess.run(
                ['powershell', '-Command', self._powershell_script],
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())

                lat = data.get('latitude')
                lon = data.get('longitude')
                alt = data.get('altitude')

                # Check if coordinates are valid (not NaN)
                if lat and lon and not (lat == 0 and lon == 0):
                    # Handle NaN altitude
                    if alt and str(alt).lower() != 'nan':
                        altitude = float(alt)
                    else:
                        altitude = None

                    coord = GPSCoordinate(
                        latitude=float(lat),
                        longitude=float(lon),
                        altitude=altitude,
                        num_satellites=8,  # Windows doesn't provide this
                        timestamp=datetime.now()
                    )

                    self.last_valid_position = coord
                    logger.debug(f"Windows GPS fix: {coord}")
                    return coord
                else:
                    logger.warning("Windows returned invalid coordinates (0,0) or NaN")
                    return self.last_valid_position
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.warning(f"Failed to get Windows location: {error_msg}")

                if "Location not available" in error_msg:
                    logger.error("Location Services may be disabled or no location providers available")
                    logger.error("Check: Settings > Privacy > Location")

                return self.last_valid_position

        except subprocess.TimeoutExpired:
            logger.warning(f"GPS timeout after {timeout}s")
            return self.last_valid_position
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse location data: {e}")
            return self.last_valid_position
        except Exception as e:
            logger.error(f"Error reading Windows GPS: {e}")
            return self.last_valid_position

    def wait_for_fix(self, timeout: float = 60.0) -> Optional[GPSCoordinate]:
        """
        Wait for initial GPS fix

        Args:
            timeout: Maximum time to wait (seconds)

        Returns:
            GPSCoordinate or None if timeout
        """
        logger.info(f"Waiting for Windows GPS fix (timeout: {timeout}s)...")
        logger.info("Make sure Location Services are enabled in Windows Settings")

        coord = self.read_position(timeout=timeout)

        if coord and coord.is_valid(min_satellites=1):  # Windows GPS always "valid" if we get coords
            logger.info(f"GPS fix acquired: {coord}")
            return coord
        else:
            logger.warning("Failed to acquire GPS fix from Windows")
            logger.warning("Check: Settings > Privacy > Location")
            return None

    def get_last_position(self) -> Optional[GPSCoordinate]:
        """
        Get last known valid position

        Returns:
            Last valid GPSCoordinate or None
        """
        return self.last_valid_position

    def disconnect(self):
        """Disconnect from Windows GPS"""
        logger.info("Windows GPS disconnected")
        self.is_connected = False

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
