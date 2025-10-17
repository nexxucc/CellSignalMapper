"""
Interactive Heatmap Generator
Creates beautiful interactive web maps from cell signal data
Optimized for single-band (Band 5 LTE 850 MHz) data
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import numpy as np
import folium
from folium import plugins
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

logger = logging.getLogger(__name__)


class InteractiveHeatmapGenerator:
    """
    Generate interactive heatmap visualizations from flight data
    Works with any flight pattern (no grid required)
    """

    def __init__(self, config: Dict):
        """
        Initialize heatmap generator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.output_dir = Path(config['visualization']['output_dir']) / 'visualizations'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Visualization settings
        self.heatmap_config = config['visualization'].get('heatmap', {})
        self.signal_thresholds = config['visualization'].get('signal_thresholds', {})

    def load_flight_data(self, json_path: str) -> List[Dict]:
        """
        Load flight data from JSON file

        Args:
            json_path: Path to JSON file from scan

        Returns:
            List of measurement dictionaries
        """
        logger.info(f"Loading flight data from {json_path}")

        with open(json_path, 'r') as f:
            data = json.load(f)

        measurements = data.get('measurements', [])
        logger.info(f"Loaded {len(measurements)} measurements")

        # Filter out measurements without valid GPS
        valid_measurements = [
            m for m in measurements
            if m.get('latitude') is not None and m.get('longitude') is not None
        ]

        logger.info(f"Found {len(valid_measurements)} measurements with valid GPS coordinates")

        if len(valid_measurements) == 0:
            raise ValueError("No measurements with valid GPS coordinates found!")

        return valid_measurements

    def extract_signal_data(self, measurements: List[Dict], band_name: str = 'band_5') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract coordinates and signal strength for a specific band

        Args:
            measurements: List of measurement dictionaries
            band_name: Band to extract (default: band_5)

        Returns:
            Tuple of (latitudes, longitudes, signal_strengths) as numpy arrays
        """
        lats = []
        lons = []
        signals = []

        for m in measurements:
            lat = m.get('latitude')
            lon = m.get('longitude')

            # Check if this measurement is for the requested band
            if m.get('band') != band_name:
                continue

            # Get signal strength directly from measurement
            signal = m.get('signal_dbm')

            if lat is not None and lon is not None and signal is not None:
                # Filter out invalid signal values
                if -150 < signal < -30:  # Reasonable range for cell signals
                    lats.append(lat)
                    lons.append(lon)
                    signals.append(signal)

        logger.info(f"Extracted {len(signals)} valid signal measurements for {band_name}")

        return np.array(lats), np.array(lons), np.array(signals)

    def interpolate_grid(self, lats: np.ndarray, lons: np.ndarray, signals: np.ndarray,
                        resolution_meters: int = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Interpolate signal data onto a regular grid using IDW (Inverse Distance Weighting)

        Args:
            lats: Latitude array
            lons: Longitude array
            signals: Signal strength array
            resolution_meters: Grid resolution in meters

        Returns:
            Tuple of (grid_lats, grid_lons, grid_signals)
        """
        logger.info("Interpolating signal data onto regular grid...")

        # Calculate bounding box
        lat_min, lat_max = lats.min(), lats.max()
        lon_min, lon_max = lons.min(), lons.max()

        # Add padding (5%)
        lat_padding = (lat_max - lat_min) * 0.05
        lon_padding = (lon_max - lon_min) * 0.05

        lat_min -= lat_padding
        lat_max += lat_padding
        lon_min -= lon_padding
        lon_max += lon_padding

        # Estimate number of grid points based on resolution
        # Rough conversion: 1 degree latitude ≈ 111 km
        lat_range_km = (lat_max - lat_min) * 111
        lon_range_km = (lon_max - lon_min) * 111 * np.cos(np.radians(lats.mean()))

        num_lat_points = max(20, int(lat_range_km * 1000 / resolution_meters))
        num_lon_points = max(20, int(lon_range_km * 1000 / resolution_meters))

        # Create grid
        grid_lats = np.linspace(lat_min, lat_max, num_lat_points)
        grid_lons = np.linspace(lon_min, lon_max, num_lon_points)
        grid_lat_mesh, grid_lon_mesh = np.meshgrid(grid_lats, grid_lons)

        # Interpolate using griddata (IDW-like with linear method)
        points = np.column_stack((lats, lons))
        grid_signals = griddata(
            points,
            signals,
            (grid_lat_mesh, grid_lon_mesh),
            method='linear',
            fill_value=np.nan
        )

        logger.info(f"Created {num_lat_points}x{num_lon_points} interpolation grid")

        return grid_lat_mesh, grid_lon_mesh, grid_signals

    def get_signal_color(self, signal_dbm: float) -> str:
        """
        Get color for signal strength based on thresholds

        Args:
            signal_dbm: Signal strength in dBm

        Returns:
            Color string (hex format)
        """
        excellent = self.signal_thresholds.get('excellent', -60)
        good = self.signal_thresholds.get('good', -70)
        fair = self.signal_thresholds.get('fair', -80)
        poor = self.signal_thresholds.get('poor', -90)

        if signal_dbm >= excellent:
            return '#00ff00'  # Bright green
        elif signal_dbm >= good:
            return '#7fff00'  # Yellow-green
        elif signal_dbm >= fair:
            return '#ffff00'  # Yellow
        elif signal_dbm >= poor:
            return '#ff8800'  # Orange
        else:
            return '#ff0000'  # Red

    def get_signal_quality(self, signal_dbm: float) -> Tuple[str, str]:
        """
        Get signal quality label and rating

        Args:
            signal_dbm: Signal strength in dBm

        Returns:
            Tuple of (quality_label, rating_stars)
        """
        excellent = self.signal_thresholds.get('excellent', -60)
        good = self.signal_thresholds.get('good', -70)
        fair = self.signal_thresholds.get('fair', -80)
        poor = self.signal_thresholds.get('poor', -90)

        if signal_dbm >= excellent:
            return "Excellent", "⭐⭐⭐⭐⭐"
        elif signal_dbm >= good:
            return "Good", "⭐⭐⭐⭐"
        elif signal_dbm >= fair:
            return "Fair", "⭐⭐⭐"
        elif signal_dbm >= poor:
            return "Weak", "⭐⭐"
        else:
            return "Poor", "⭐"

    def generate_interactive_map(self, json_path: str, band_name: str = 'band_5',
                                 output_filename: Optional[str] = None) -> Path:
        """
        Generate interactive heatmap from flight data

        Args:
            json_path: Path to JSON flight data file
            band_name: Band to visualize (default: band_5)
            output_filename: Optional custom output filename

        Returns:
            Path to generated HTML file
        """
        logger.info(f"Generating interactive heatmap for {band_name}...")

        # Load data
        measurements = self.load_flight_data(json_path)
        lats, lons, signals = self.extract_signal_data(measurements, band_name)

        if len(signals) == 0:
            raise ValueError(f"No valid signal data found for {band_name}")

        # Calculate map center
        center_lat = lats.mean()
        center_lon = lons.mean()

        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=15,
            tiles='OpenStreetMap',
            control_scale=True
        )

        # Add satellite layer option
        folium.TileLayer('Esri.WorldImagery', name='Satellite', overlay=False).add_to(m)

        # Create heatmap data (for folium HeatMap plugin)
        # Format: [[lat, lon, weight], ...]
        # Normalize signals to 0-1 range for heatmap
        signal_min, signal_max = signals.min(), signals.max()
        signal_normalized = (signals - signal_min) / (signal_max - signal_min) if signal_max > signal_min else np.ones_like(signals)

        heatmap_data = [
            [lat, lon, weight]
            for lat, lon, weight in zip(lats, lons, signal_normalized)
        ]

        # Add heatmap layer
        heatmap = plugins.HeatMap(
            heatmap_data,
            name='Signal Heatmap',
            min_opacity=self.heatmap_config.get('min_opacity', 0.4),
            max_zoom=self.heatmap_config.get('max_zoom', 18),
            radius=self.heatmap_config.get('radius_pixels', 15),
            blur=20,
            gradient={
                0.0: 'darkred',
                0.3: 'red',
                0.5: 'orange',
                0.7: 'yellow',
                0.85: 'yellowgreen',
                1.0: 'green'
            }
        )
        m.add_child(heatmap)

        # Add individual data points as markers
        # Group measurements by location (lat/lon) to avoid too many markers
        location_groups = {}
        for measurement in measurements:
            if measurement.get('band') == band_name:
                lat = measurement.get('latitude')
                lon = measurement.get('longitude')
                if lat and lon:
                    key = (round(lat, 5), round(lon, 5))  # Group nearby points
                    if key not in location_groups:
                        location_groups[key] = []
                    location_groups[key].append(measurement)

        marker_cluster = plugins.MarkerCluster(name='Data Points')

        for i, (loc_key, loc_measurements) in enumerate(location_groups.items()):
            # Use average signal for this location
            avg_signal = np.mean([m['signal_dbm'] for m in loc_measurements])
            lat, lon = loc_key

            quality, rating = self.get_signal_quality(avg_signal)
            color = self.get_signal_color(avg_signal)

            # Get first measurement for time/altitude
            first_m = loc_measurements[0]

            # Create popup HTML
            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 0 0 10px 0;">📍 Location #{i+1}</h4>
                <hr style="margin: 5px 0;">
                <p style="margin: 5px 0;"><b>🛰️ Signal Strength</b></p>
                <p style="margin: 5px 0 5px 20px;">
                    {avg_signal:.1f} dBm<br>
                    Quality: {quality} {rating}<br>
                    ({len(loc_measurements)} samples)
                </p>
                <p style="margin: 5px 0;"><b>📍 Location</b></p>
                <p style="margin: 5px 0 5px 20px;">
                    Lat: {lat:.6f}°<br>
                    Lon: {lon:.6f}°<br>
                    Alt: {first_m.get('altitude', 'N/A')}m
                </p>
                <p style="margin: 5px 0;"><b>📻 Frequency</b></p>
                <p style="margin: 5px 0 5px 20px;">{first_m.get('frequency_mhz', 'N/A'):.2f} MHz</p>
                <p style="margin: 5px 0;"><b>🕒 Time</b></p>
                <p style="margin: 5px 0 5px 20px;">{first_m.get('timestamp', 'N/A').split('T')[0] if first_m.get('timestamp') else 'N/A'}<br>
                {first_m.get('timestamp', 'N/A').split('T')[1][:8] if first_m.get('timestamp') and 'T' in first_m.get('timestamp') else ''}</p>
            </div>
            """

            # Add marker
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=1
            ).add_to(marker_cluster)

        marker_cluster.add_to(m)

        # Add flight path
        path_coords = [[lat, lon] for lat, lon in zip(lats, lons)]
        folium.PolyLine(
            path_coords,
            color='blue',
            weight=2,
            opacity=0.6,
            popup='Flight Path'
        ).add_to(m)

        # Add layer control
        folium.LayerControl().add_to(m)

        # Add legend
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 50px; width: 200px; height: 180px;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
            <p style="margin: 0 0 10px 0;"><b>Signal Strength Legend</b></p>
            <p style="margin: 5px 0;"><span style="color: #00ff00;">⬤</span> Excellent (&gt; {self.signal_thresholds.get('excellent', -60)} dBm)</p>
            <p style="margin: 5px 0;"><span style="color: #7fff00;">⬤</span> Good (&gt; {self.signal_thresholds.get('good', -70)} dBm)</p>
            <p style="margin: 5px 0;"><span style="color: #ffff00;">⬤</span> Fair (&gt; {self.signal_thresholds.get('fair', -80)} dBm)</p>
            <p style="margin: 5px 0;"><span style="color: #ff8800;">⬤</span> Weak (&gt; {self.signal_thresholds.get('poor', -90)} dBm)</p>
            <p style="margin: 5px 0;"><span style="color: #ff0000;">⬤</span> Poor (&lt; {self.signal_thresholds.get('poor', -90)} dBm)</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        # Add summary info box
        summary_html = f"""
        <div style="position: fixed;
                    top: 10px; right: 10px; width: 250px;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
            <h4 style="margin: 0 0 10px 0;">Flight Summary</h4>
            <p style="margin: 5px 0;"><b>Band:</b> {band_name.replace('_', ' ').title()}</p>
            <p style="margin: 5px 0;"><b>Measurements:</b> {len(signals)}</p>
            <p style="margin: 5px 0;"><b>Avg Signal:</b> {signals.mean():.1f} dBm</p>
            <p style="margin: 5px 0;"><b>Max Signal:</b> {signals.max():.1f} dBm</p>
            <p style="margin: 5px 0;"><b>Min Signal:</b> {signals.min():.1f} dBm</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(summary_html))

        # Save map
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'interactive_map_{band_name}_{timestamp}.html'

        output_path = self.output_dir / output_filename
        m.save(str(output_path))

        logger.info(f"✓ Interactive map saved to: {output_path}")
        logger.info(f"  Open in browser to view!")

        return output_path
