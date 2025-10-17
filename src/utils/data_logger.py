"""
Data Logger Module
Handles logging of signal strength measurements with GPS coordinates and timestamps
"""

import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class DataLogger:
    """Logs signal measurement data to various formats"""

    def __init__(self, config: Dict):
        """
        Initialize data logger

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.data_dir = Path(config['logging']['data_dir'])
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Create session ID based on timestamp
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # In-memory storage for current session
        self.measurements: List[Dict] = []

    def log_measurement(self,
                       latitude: Optional[float],
                       longitude: Optional[float],
                       altitude: Optional[float],
                       band_name: str,
                       frequency: float,
                       signal_strength: float,
                       timestamp: Optional[datetime] = None) -> None:
        """
        Log a single measurement

        Args:
            latitude: GPS latitude in decimal degrees
            longitude: GPS longitude in decimal degrees
            altitude: Altitude in meters
            band_name: Name of the LTE band
            frequency: Frequency in Hz
            signal_strength: Signal strength in dBm
            timestamp: Measurement timestamp (uses current time if None)
        """
        if timestamp is None:
            timestamp = datetime.now()

        measurement = {
            'timestamp': timestamp.isoformat(),
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'band': band_name,
            'frequency_mhz': frequency / 1e6,
            'signal_dbm': signal_strength,
            'session_id': self.session_id
        }

        self.measurements.append(measurement)

        logger.debug(f"Logged measurement: {band_name} @ {frequency/1e6:.2f} MHz = {signal_strength:.2f} dBm")

    def log_scan_results(self,
                        latitude: Optional[float],
                        longitude: Optional[float],
                        altitude: Optional[float],
                        scan_results: Dict[str, List[tuple]],
                        timestamp: Optional[datetime] = None) -> None:
        """
        Log results from a complete band scan

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            altitude: Altitude in meters
            scan_results: Dictionary of {band_name: [(freq, power), ...]}
            timestamp: Measurement timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()

        for band_name, results in scan_results.items():
            # Handle both old format [(freq, power), ...] and new format {'raw_data': [...]}
            if isinstance(results, dict):
                raw_data = results.get('raw_data', [])
            else:
                raw_data = results

            for freq, power in raw_data:
                self.log_measurement(
                    latitude=latitude,
                    longitude=longitude,
                    altitude=altitude,
                    band_name=band_name,
                    frequency=freq,
                    signal_strength=power,
                    timestamp=timestamp
                )

    def save_to_csv(self, filename: Optional[str] = None) -> Path:
        """
        Save measurements to CSV file

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved CSV file
        """
        if filename is None:
            filename = f"signal_data_{self.session_id}.csv"

        filepath = self.data_dir / filename

        if not self.measurements:
            logger.warning("No measurements to save")
            return filepath

        # Convert to DataFrame and save
        df = pd.DataFrame(self.measurements)
        df.to_csv(filepath, index=False)

        logger.info(f"Saved {len(self.measurements)} measurements to {filepath}")
        return filepath

    def save_to_json(self, filename: Optional[str] = None) -> Path:
        """
        Save measurements to JSON file

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved JSON file
        """
        if filename is None:
            filename = f"signal_data_{self.session_id}.json"

        filepath = self.data_dir / filename

        if not self.measurements:
            logger.warning("No measurements to save")
            return filepath

        with open(filepath, 'w') as f:
            json.dump({
                'session_id': self.session_id,
                'num_measurements': len(self.measurements),
                'measurements': self.measurements
            }, f, indent=2)

        logger.info(f"Saved {len(self.measurements)} measurements to {filepath}")
        return filepath

    def get_dataframe(self) -> pd.DataFrame:
        """
        Get measurements as pandas DataFrame

        Returns:
            DataFrame containing all measurements
        """
        return pd.DataFrame(self.measurements)

    def get_measurements_by_band(self, band_name: str) -> List[Dict]:
        """
        Get all measurements for a specific band

        Args:
            band_name: Name of the band

        Returns:
            List of measurement dictionaries
        """
        return [m for m in self.measurements if m['band'] == band_name]

    def get_measurements_by_location(self,
                                    latitude: float,
                                    longitude: float,
                                    radius_meters: float = 10) -> List[Dict]:
        """
        Get measurements near a specific location

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Search radius in meters

        Returns:
            List of measurements within radius
        """
        # Simple approximation: 1 degree ≈ 111 km
        lat_delta = radius_meters / 111000
        # Use cosine correction for longitude, prevent division by zero
        import math
        lon_delta = radius_meters / (111000 * max(0.01, abs(math.cos(math.radians(latitude)))))

        nearby = []
        for m in self.measurements:
            if m['latitude'] is None or m['longitude'] is None:
                continue

            lat_diff = abs(m['latitude'] - latitude)
            lon_diff = abs(m['longitude'] - longitude)

            if lat_diff <= lat_delta and lon_diff <= lon_delta:
                nearby.append(m)

        return nearby

    def get_summary_statistics(self) -> Dict:
        """
        Calculate summary statistics for the session

        Returns:
            Dictionary of statistics
        """
        if not self.measurements:
            return {}

        df = self.get_dataframe()

        stats = {
            'total_measurements': len(self.measurements),
            'session_id': self.session_id,
            'bands_scanned': df['band'].unique().tolist(),
            'signal_stats': {
                'min_dbm': float(df['signal_dbm'].min()),
                'max_dbm': float(df['signal_dbm'].max()),
                'mean_dbm': float(df['signal_dbm'].mean()),
                'median_dbm': float(df['signal_dbm'].median())
            },
            'spatial_coverage': {
                'has_gps': df['latitude'].notna().sum(),
                'no_gps': df['latitude'].isna().sum()
            }
        }

        if df['latitude'].notna().any():
            stats['spatial_coverage']['lat_range'] = [
                float(df['latitude'].min()),
                float(df['latitude'].max())
            ]
            stats['spatial_coverage']['lon_range'] = [
                float(df['longitude'].min()),
                float(df['longitude'].max())
            ]

        return stats

    def clear_measurements(self):
        """Clear all measurements from memory"""
        self.measurements = []
        logger.info("Cleared all measurements from memory")

    def __len__(self):
        """Return number of measurements"""
        return len(self.measurements)
