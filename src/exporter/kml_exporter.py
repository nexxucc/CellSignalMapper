"""
KML Exporter Module
Exports signal strength data to KML/KMZ format for Google Earth visualization
"""

import simplekml
import logging
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class KMLExporter:
    """Exports signal measurement data to KML format for Google Earth"""

    def __init__(self, config: Dict):
        """
        Initialize KML exporter

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.output_dir = Path(config['export']['output_dir'] if 'output_dir' in config['export']
                               else config['visualization']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _signal_to_color(self, signal_dbm: float) -> str:
        """
        Convert signal strength to color hex code

        Args:
            signal_dbm: Signal strength in dBm

        Returns:
            KML color string (AABBGGRR format)
        """
        vmin = self.config['visualization']['min_signal_threshold']
        vmax = self.config['visualization']['max_signal_threshold']

        # Normalize signal to 0-1 range
        normalized = (signal_dbm - vmin) / (vmax - vmin)
        normalized = np.clip(normalized, 0, 1)

        # Color gradient: Red (weak) -> Yellow -> Green (strong)
        if normalized < 0.5:
            # Red to Yellow
            r = 255
            g = int(255 * (normalized * 2))
            b = 0
        else:
            # Yellow to Green
            r = int(255 * (2 - normalized * 2))
            g = 255
            b = 0

        # KML format is AABBGGRR (alpha, blue, green, red)
        return f"ff{b:02x}{g:02x}{r:02x}"

    def export_to_kml(self,
                      df: pd.DataFrame,
                      output_filename: str = "signal_map.kml",
                      include_paths: bool = False) -> Path:
        """
        Export measurements to KML file

        Args:
            df: DataFrame containing measurements
            output_filename: Output filename
            include_paths: Whether to draw paths between measurement points

        Returns:
            Path to saved KML file
        """
        kml = simplekml.Kml(name="Cell Signal Strength Map")

        # Remove rows without GPS
        df_gps = df.dropna(subset=['latitude', 'longitude'])

        if df_gps.empty:
            logger.warning("No GPS data to export")
            return None

        # Group by band
        bands = df_gps['band'].unique()

        for band_name in bands:
            band_data = df_gps[df_gps['band'] == band_name].copy()

            # Create folder for this band
            band_folder = kml.newfolder(name=band_name)

            # If altitude layers are enabled, group by altitude
            if self.config['export']['altitude_layers'] and band_data['altitude'].notna().any():
                altitudes = band_data['altitude'].dropna().unique()
                altitudes = np.round(altitudes / 5) * 5  # Round to nearest 5m
                altitudes = np.unique(altitudes)

                for altitude in altitudes:
                    alt_data = band_data[
                        (band_data['altitude'] >= altitude - 5) &
                        (band_data['altitude'] <= altitude + 5)
                    ]

                    if not alt_data.empty:
                        alt_folder = band_folder.newfolder(name=f"{int(altitude)}m altitude")
                        self._add_points_to_folder(alt_folder, alt_data, include_paths)
            else:
                # No altitude separation
                self._add_points_to_folder(band_folder, band_data, include_paths)

        # Save
        output_path = self.output_dir / output_filename
        kml.save(str(output_path))

        logger.info(f"Exported {len(df_gps)} points to {output_path}")
        return output_path

    def _add_points_to_folder(self, folder, df: pd.DataFrame, include_paths: bool = False):
        """
        Add measurement points to a KML folder

        Args:
            folder: KML folder object
            df: DataFrame with measurements
            include_paths: Whether to draw paths between points
        """
        # Sort by timestamp if available
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp')

        # Add placemarks for each measurement
        for idx, row in df.iterrows():
            lat = row['latitude']
            lon = row['longitude']
            alt = row.get('altitude', 0)
            # Handle None altitude
            if alt is None or (isinstance(alt, float) and alt != alt):  # Check for None or NaN
                alt = 0
            signal = row['signal_dbm']
            freq = row['frequency_mhz']

            # Create placemark
            pnt = folder.newpoint()
            pnt.coords = [(lon, lat, alt)]

            # Name and description
            pnt.name = f"{signal:.1f} dBm"
            alt_str = f"{alt:.1f} m" if alt != 0 else "N/A"
            pnt.description = f"""
            <![CDATA[
            <b>Signal Strength:</b> {signal:.2f} dBm<br/>
            <b>Frequency:</b> {freq:.2f} MHz<br/>
            <b>Band:</b> {row['band']}<br/>
            <b>Location:</b> {lat:.6f}, {lon:.6f}<br/>
            <b>Altitude:</b> {alt_str}<br/>
            <b>Time:</b> {row.get('timestamp', 'N/A')}
            ]]>
            """

            # Style based on signal strength
            color = self._signal_to_color(signal)
            pnt.style.iconstyle.color = color
            pnt.style.iconstyle.scale = 0.8
            pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

            # Label style
            pnt.style.labelstyle.scale = 0.7

        # Add path connecting points
        if include_paths and len(df) > 1:
            linestring = folder.newlinestring(name="Measurement Path")
            coords = [(row['longitude'], row['latitude'], row.get('altitude', 0))
                     for _, row in df.iterrows()]
            linestring.coords = coords
            linestring.style.linestyle.color = 'ff0000ff'  # Red line
            linestring.style.linestyle.width = 2

    def export_heatmap_overlay(self,
                              df: pd.DataFrame,
                              output_filename: str = "signal_overlay.kml") -> Path:
        """
        Export as KML with ground overlay (for pre-generated heatmap images)

        Note: This creates KML structure for overlays. Actual overlay images
        need to be generated separately and referenced here.

        Args:
            df: DataFrame containing measurements
            output_filename: Output filename

        Returns:
            Path to KML file
        """
        kml = simplekml.Kml(name="Signal Strength Overlay")

        # Calculate bounds
        df_gps = df.dropna(subset=['latitude', 'longitude'])

        if df_gps.empty:
            logger.warning("No GPS data for overlay")
            return None

        north = df_gps['latitude'].max()
        south = df_gps['latitude'].min()
        east = df_gps['longitude'].max()
        west = df_gps['longitude'].min()

        # Add padding
        lat_padding = (north - south) * 0.1
        lon_padding = (east - west) * 0.1

        north += lat_padding
        south -= lat_padding
        east += lon_padding
        west -= lon_padding

        # Create ground overlay placeholder
        # Note: User needs to generate actual heatmap PNG and reference it here
        ground = kml.newgroundoverlay(name='Signal Heatmap')
        ground.icon.href = 'heatmap_overlay.png'  # User should replace with actual image
        ground.latlonbox.north = north
        ground.latlonbox.south = south
        ground.latlonbox.east = east
        ground.latlonbox.west = west
        ground.latlonbox.rotation = 0

        output_path = self.output_dir / output_filename
        kml.save(str(output_path))

        logger.info(f"Exported overlay KML to {output_path}")
        logger.info(f"Note: Place heatmap_overlay.png in same directory as KML")

        return output_path

    def export_coverage_zones(self,
                             df: pd.DataFrame,
                             threshold_dbm: float = -100,
                             output_filename: str = "coverage_zones.kml") -> Path:
        """
        Export coverage zones (good/weak signal areas) to KML

        Args:
            df: DataFrame containing measurements
            threshold_dbm: Signal threshold for good coverage
            output_filename: Output filename

        Returns:
            Path to KML file
        """
        kml = simplekml.Kml(name="Coverage Zones")

        df_gps = df.dropna(subset=['latitude', 'longitude'])

        if df_gps.empty:
            logger.warning("No GPS data for coverage zones")
            return None

        # Create folders for good and weak coverage
        good_folder = kml.newfolder(name=f"Good Coverage (≥{threshold_dbm} dBm)")
        weak_folder = kml.newfolder(name=f"Weak Coverage (<{threshold_dbm} dBm)")

        good_points = df_gps[df_gps['signal_dbm'] >= threshold_dbm]
        weak_points = df_gps[df_gps['signal_dbm'] < threshold_dbm]

        # Add good coverage points
        for _, row in good_points.iterrows():
            pnt = good_folder.newpoint()
            pnt.coords = [(row['longitude'], row['latitude'], row.get('altitude', 0))]
            pnt.name = f"{row['signal_dbm']:.1f} dBm"
            pnt.style.iconstyle.color = 'ff00ff00'  # Green
            pnt.style.iconstyle.scale = 0.6

        # Add weak coverage points
        for _, row in weak_points.iterrows():
            pnt = weak_folder.newpoint()
            pnt.coords = [(row['longitude'], row['latitude'], row.get('altitude', 0))]
            pnt.name = f"{row['signal_dbm']:.1f} dBm"
            pnt.style.iconstyle.color = 'ff0000ff'  # Red
            pnt.style.iconstyle.scale = 0.6

        output_path = self.output_dir / output_filename
        kml.save(str(output_path))

        logger.info(f"Exported coverage zones to {output_path}")
        logger.info(f"Good coverage: {len(good_points)} points, Weak: {len(weak_points)} points")

        return output_path
