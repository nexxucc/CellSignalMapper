"""
MAVLink GPS Module
Reads GPS data from Pixhawk/PX4 flight controller via MAVLink protocol
"""

import logging
from typing import Optional, Dict
from datetime import datetime
import time

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False

from .gps_module import GPSCoordinate

logger = logging.getLogger(__name__)


class MAVLinkGPSReader:
    """
    GPS reader that gets data from Pixhawk via MAVLink protocol
    Compatible with the existing GPSReader interface
    """

    def __init__(self, config: Dict):
        """
        Initialize MAVLink GPS reader

        Args:
            config: Configuration dictionary containing GPS settings
        """
        self.config = config
        self.master = None
        self.is_connected = False
        self.last_valid_position: Optional[GPSCoordinate] = None

        # MAVLink-specific settings
        self.mavlink_port = config['gps'].get('mavlink_port', '/dev/ttyACM0')
        self.mavlink_baud = config['gps'].get('mavlink_baud', 57600)

    def connect(self) -> bool:
        """
        Connect to Pixhawk via MAVLink

        Returns:
            True if successful, False otherwise
        """
        if not self.config['gps']['enabled']:
            logger.info("GPS is disabled in configuration")
            return False

        if not MAVLINK_AVAILABLE:
            logger.error("pymavlink library not installed. Install with: pip install pymavlink")
            return False

        try:
            logger.info(f"Connecting to Pixhawk on {self.mavlink_port} at {self.mavlink_baud} baud...")

            # Create MAVLink connection
            self.master = mavutil.mavlink_connection(
                self.mavlink_port,
                baud=self.mavlink_baud
            )

            # Wait for heartbeat with timeout
            logger.info("Waiting for Pixhawk heartbeat...")
            self.master.wait_heartbeat(timeout=10)

            logger.info(f"✓ Connected to Pixhawk (system {self.master.target_system}, component {self.master.target_component})")

            # Request GPS data stream at 1 Hz
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                1,  # 1 Hz
                1   # Start streaming
            )

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Pixhawk: {e}")
            logger.error("Check:")
            logger.error(f"  1. Pixhawk is connected to {self.mavlink_port}")
            logger.error(f"  2. Baud rate is {self.mavlink_baud}")
            logger.error(f"  3. User is in dialout group: sudo usermod -a -G dialout $USER")
            self.is_connected = False
            return False

    def read_position(self, timeout: float = 5.0) -> Optional[GPSCoordinate]:
        """
        Read current GPS position from Pixhawk

        Args:
            timeout: Maximum time to wait for GPS data (seconds)

        Returns:
            GPSCoordinate object or None if no valid fix
        """
        if not self.is_connected:
            logger.warning("Not connected to Pixhawk")
            return self.last_valid_position

        try:
            # Wait for GPS_RAW_INT message
            start_time = time.time()

            while (time.time() - start_time) < timeout:
                msg = self.master.recv_match(
                    type='GPS_RAW_INT',
                    blocking=True,
                    timeout=1
                )

                if msg:
                    # Parse GPS data
                    # MAVLink GPS_RAW_INT message format:
                    # lat/lon are in 1E7 degrees (need to divide by 10,000,000)
                    # alt is in mm (need to divide by 1000)
                    lat = msg.lat / 1e7
                    lon = msg.lon / 1e7
                    alt = msg.alt / 1000.0  # Convert mm to meters
                    sats = msg.satellites_visible
                    fix_type = msg.fix_type

                    # Check if we have a valid fix
                    # Fix types: 0=No GPS, 1=No Fix, 2=2D Fix, 3=3D Fix
                    if lat != 0 and lon != 0:
                        coord = GPSCoordinate(
                            latitude=lat,
                            longitude=lon,
                            altitude=alt if alt > 0 else None,
                            num_satellites=sats,
                            timestamp=datetime.now()
                        )

                        # Check fix quality
                        min_sats = self.config['gps'].get('min_satellites', 4)

                        if fix_type >= 2 and sats >= min_sats:
                            # Valid fix
                            self.last_valid_position = coord
                            logger.debug(f"MAVLink GPS: {coord} (fix_type={fix_type})")
                            return coord
                        elif fix_type >= 2:
                            # Has fix but not enough satellites
                            logger.debug(f"GPS fix but only {sats} satellites (need {min_sats})")
                            self.last_valid_position = coord
                            return coord
                        else:
                            # No fix yet
                            logger.debug(f"Waiting for GPS fix (fix_type={fix_type}, sats={sats})")

            # Timeout reached
            logger.warning(f"GPS timeout after {timeout}s")
            return self.last_valid_position

        except Exception as e:
            logger.error(f"Error reading GPS from Pixhawk: {e}")
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
        logger.info("Note: GPS needs clear sky view (go outside if indoors)")

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            coord = self.read_position(timeout=5)

            if coord and coord.is_valid(self.config['gps'].get('min_satellites', 4)):
                logger.info(f"GPS fix acquired: {coord}")
                return coord

            # Check if we're getting any GPS messages
            msg = self.master.recv_match(type='GPS_RAW_INT', blocking=False)
            if msg:
                logger.info(f"GPS status: fix_type={msg.fix_type}, sats={msg.satellites_visible}")

            time.sleep(2)

        logger.warning("Failed to acquire GPS fix")
        return self.last_valid_position

    def get_last_position(self) -> Optional[GPSCoordinate]:
        """
        Get last known valid position

        Returns:
            Last valid GPSCoordinate or None
        """
        return self.last_valid_position

    def disconnect(self):
        """Disconnect from Pixhawk"""
        if self.master is not None:
            try:
                self.master.close()
                logger.info("Disconnected from Pixhawk")
            except Exception as e:
                logger.error(f"Error disconnecting from Pixhawk: {e}")

        self.is_connected = False

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


class MAVLinkGPSReaderWithCompass(MAVLinkGPSReader):
    """
    Extended MAVLink GPS reader that also reads compass heading from Pixhawk
    """

    def read_position(self, timeout: float = 5.0) -> Optional[GPSCoordinate]:
        """
        Read GPS position with compass heading

        Args:
            timeout: Maximum time to wait (seconds)

        Returns:
            GPSCoordinate with heading data
        """
        coord = super().read_position(timeout)

        if coord and self.is_connected:
            # Try to get compass heading from Pixhawk
            try:
                msg = self.master.recv_match(
                    type='VFR_HUD',
                    blocking=False
                )

                if msg:
                    heading = msg.heading  # Heading in degrees (0-360)
                    coord.heading = heading
                    logger.debug(f"Compass heading: {heading:.1f}°")

            except Exception as e:
                logger.debug(f"Could not read compass: {e}")

        return coord
