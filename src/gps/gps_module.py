"""
GPS Module
Handles GPS coordinate acquisition from serial GPS devices
Optional: HMC5883L compass support via I2C
"""

import serial
import pynmea2
import logging
from typing import Optional, Tuple, Dict
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class GPSCoordinate:
    """Container for GPS coordinate data"""

    def __init__(self,
                 latitude: float,
                 longitude: float,
                 altitude: Optional[float] = None,
                 num_satellites: int = 0,
                 heading: Optional[float] = None,
                 timestamp: Optional[datetime] = None):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.num_satellites = num_satellites
        self.heading = heading  # Compass heading in degrees (0-360)
        self.timestamp = timestamp or datetime.now()

    def __repr__(self):
        heading_str = f", heading={self.heading:.1f}°" if self.heading is not None else ""
        return f"GPSCoordinate(lat={self.latitude:.6f}, lon={self.longitude:.6f}, alt={self.altitude}m, sats={self.num_satellites}{heading_str})"

    def is_valid(self, min_satellites: int = 4) -> bool:
        """Check if GPS fix is valid"""
        return (self.latitude != 0 and
                self.longitude != 0 and
                self.num_satellites >= min_satellites)


class GPSReader:
    """Interface for reading GPS data from serial device"""

    def __init__(self, config: Dict):
        """
        Initialize GPS reader

        Args:
            config: Configuration dictionary containing GPS settings
        """
        self.config = config
        self.serial_port = None
        self.is_connected = False
        self.last_valid_position: Optional[GPSCoordinate] = None

    def connect(self) -> bool:
        """
        Connect to GPS device and optional compass

        Returns:
            True if successful, False otherwise
        """
        if not self.config['gps']['enabled']:
            logger.info("GPS is disabled in configuration")
            return False

        try:
            self.serial_port = serial.Serial(
                port=self.config['gps']['port'],
                baudrate=self.config['gps']['baud_rate'],
                timeout=self.config['gps']['timeout']
            )

            self.is_connected = True
            logger.info(f"GPS connected on {self.config['gps']['port']}")
            return True

        except serial.SerialException as e:
            logger.error(f"Failed to connect to GPS: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to GPS: {e}")
            self.is_connected = False
            return False

    def read_position(self, timeout: float = 5.0) -> Optional[GPSCoordinate]:
        """
        Read current GPS position

        Args:
            timeout: Maximum time to wait for valid GPS data (seconds)

        Returns:
            GPSCoordinate object or None if no valid fix
        """
        if not self.is_connected:
            logger.warning("GPS not connected")
            return self.last_valid_position

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            try:
                line = self.serial_port.readline().decode('ascii', errors='ignore').strip()

                if not line:
                    continue

                # Try to parse NMEA sentence
                if line.startswith('$'):
                    try:
                        msg = pynmea2.parse(line)

                        # Parse GGA sentence (position fix)
                        if isinstance(msg, pynmea2.types.talker.GGA):
                            if msg.latitude and msg.longitude:
                                coord = GPSCoordinate(
                                    latitude=msg.latitude,
                                    longitude=msg.longitude,
                                    altitude=msg.altitude if msg.altitude else None,
                                    num_satellites=msg.num_sats if msg.num_sats else 0,
                                    timestamp=datetime.now()
                                )

                                # Check if fix is valid
                                min_sats = self.config['gps']['min_satellites']
                                if coord.is_valid(min_sats):
                                    self.last_valid_position = coord
                                    logger.debug(f"GPS fix: {coord}")
                                    return coord
                                else:
                                    logger.debug(f"GPS fix insufficient: {coord.num_satellites} sats < {min_sats} required")

                    except pynmea2.ParseError:
                        # Ignore malformed sentences
                        pass

            except Exception as e:
                logger.error(f"Error reading GPS data: {e}")
                time.sleep(0.1)

        # Timeout reached
        logger.warning(f"GPS timeout after {timeout}s")
        return self.last_valid_position

    def wait_for_fix(self, timeout: float = 60.0) -> Optional[GPSCoordinate]:
        """
        Wait for initial GPS fix

        Args:
            timeout: Maximum time to wait (seconds)

        Returns:
            GPSCoordinate or None if timeout
        """
        logger.info(f"Waiting for GPS fix (timeout: {timeout}s)...")
        coord = self.read_position(timeout=timeout)

        if coord and coord.is_valid(self.config['gps']['min_satellites']):
            logger.info(f"GPS fix acquired: {coord}")
            return coord
        else:
            logger.warning("Failed to acquire GPS fix")
            return None

    def get_last_position(self) -> Optional[GPSCoordinate]:
        """
        Get last known valid position

        Returns:
            Last valid GPSCoordinate or None
        """
        return self.last_valid_position

    def disconnect(self):
        """Disconnect from GPS device"""
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                logger.info("GPS disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting GPS: {e}")

        self.is_connected = False

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


class MockGPSReader(GPSReader):
    """
    Mock GPS reader for testing without hardware
    Simulates GPS movement in a grid pattern
    """

    def __init__(self, config: Dict, start_lat: float = 28.6139, start_lon: float = 77.2090):
        """
        Initialize mock GPS reader

        Args:
            config: Configuration dictionary
            start_lat: Starting latitude (default: New Delhi)
            start_lon: Starting longitude
        """
        super().__init__(config)
        self.current_lat = start_lat
        self.current_lon = start_lon
        self.current_alt = 10.0
        self.counter = 0

    def connect(self) -> bool:
        """Simulate GPS connection"""
        logger.info("Mock GPS connected (simulated)")
        self.is_connected = True
        return True

    def read_position(self, timeout: float = 5.0) -> Optional[GPSCoordinate]:
        """
        Generate simulated GPS position

        Returns:
            Simulated GPSCoordinate
        """
        if not self.is_connected:
            return None

        # Simulate movement in a grid
        self.counter += 1
        offset = 0.0001 * (self.counter % 10)  # ~11m spacing

        coord = GPSCoordinate(
            latitude=self.current_lat + offset,
            longitude=self.current_lon + offset,
            altitude=self.current_alt,
            num_satellites=8,
            timestamp=datetime.now()
        )

        self.last_valid_position = coord
        time.sleep(0.1)  # Simulate read delay

        return coord

    def wait_for_fix(self, timeout: float = 60.0) -> Optional[GPSCoordinate]:
        """Simulate GPS fix acquisition"""
        logger.info("Mock GPS fix acquired (simulated)")
        return self.read_position()


