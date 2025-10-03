"""
Heatmap Generator Module
Processes signal strength data and generates visualization heatmaps
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from scipy.interpolate import griddata
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    """Generates signal strength heatmaps from measurement data"""

    def __init__(self, config: Dict):
        """
        Initialize heatmap generator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.output_dir = Path(config['visualization']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_2d_heatmap(self,
                           df: pd.DataFrame,
                           band_name: str,
                           altitude: Optional[float] = None,
                           output_filename: Optional[str] = None) -> Path:
        """
        Generate 2D heatmap for a specific band and altitude

        Args:
            df: DataFrame containing measurements
            band_name: Name of the band to visualize
            altitude: Specific altitude to filter (None = all altitudes)
            output_filename: Custom output filename

        Returns:
            Path to saved heatmap image
        """
        # Filter data
        band_data = df[df['band'] == band_name].copy()

        if altitude is not None:
            band_data = band_data[
                (band_data['altitude'] >= altitude - 5) &
                (band_data['altitude'] <= altitude + 5)
            ]

        if band_data.empty:
            logger.warning(f"No data for band {band_name} at altitude {altitude}m")
            return None

        # Remove rows with missing GPS data
        band_data = band_data.dropna(subset=['latitude', 'longitude'])

        if band_data.empty:
            logger.warning(f"No GPS data available for band {band_name}")
            return None

        # Extract coordinates and signal strength
        lats = band_data['latitude'].values
        lons = band_data['longitude'].values
        signals = band_data['signal_dbm'].values

        # Create grid for interpolation
        resolution = self.config['visualization']['heatmap_resolution']

        lat_min, lat_max = lats.min(), lats.max()
        lon_min, lon_max = lons.min(), lons.max()

        # Add 10% padding
        lat_padding = (lat_max - lat_min) * 0.1
        lon_padding = (lon_max - lon_min) * 0.1

        grid_lat = np.linspace(lat_min - lat_padding, lat_max + lat_padding, resolution)
        grid_lon = np.linspace(lon_min - lon_padding, lon_max + lon_padding, resolution)

        grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

        # Interpolate signal strength
        grid_signal = griddata(
            points=(lons, lats),
            values=signals,
            xi=(grid_lon_mesh, grid_lat_mesh),
            method='cubic',
            fill_value=np.nan
        )

        # Create plot
        fig, ax = plt.subplots(figsize=(12, 10))

        # Apply signal thresholds
        vmin = self.config['visualization']['min_signal_threshold']
        vmax = self.config['visualization']['max_signal_threshold']

        # Plot heatmap
        cmap = plt.get_cmap(self.config['visualization']['color_scheme'])
        im = ax.contourf(
            grid_lon_mesh,
            grid_lat_mesh,
            grid_signal,
            levels=20,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            extend='both'
        )

        # Overlay measurement points
        scatter = ax.scatter(
            lons,
            lats,
            c=signals,
            s=50,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            edgecolors='black',
            linewidths=0.5,
            alpha=0.8
        )

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, label='Signal Strength (dBm)')

        # Labels and title
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

        title = f'{band_name} Signal Strength'
        if altitude is not None:
            title += f' at {altitude}m altitude'

        ax.set_title(title, fontsize=14, fontweight='bold')

        # Grid
        ax.grid(True, alpha=0.3)

        # Statistics text
        stats_text = f'Points: {len(band_data)}\n'
        stats_text += f'Min: {signals.min():.1f} dBm\n'
        stats_text += f'Max: {signals.max():.1f} dBm\n'
        stats_text += f'Mean: {signals.mean():.1f} dBm'

        ax.text(
            0.02, 0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
        )

        # Save
        if output_filename is None:
            alt_suffix = f"_alt{int(altitude)}m" if altitude is not None else ""
            output_filename = f"heatmap_{band_name}{alt_suffix}.png"

        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved heatmap to {output_path}")
        return output_path

    def generate_all_heatmaps(self, df: pd.DataFrame) -> List[Path]:
        """
        Generate heatmaps for all bands and altitudes in the data

        Args:
            df: DataFrame containing all measurements

        Returns:
            List of paths to generated heatmap files
        """
        output_files = []

        # Get unique bands
        bands = df['band'].unique()

        for band in bands:
            # Check if we have altitude data
            band_data = df[df['band'] == band]

            if band_data['altitude'].notna().any():
                # Generate separate heatmaps for each altitude
                altitudes = band_data['altitude'].dropna().unique()

                # Round altitudes to nearest 5m for grouping
                altitudes = np.round(altitudes / 5) * 5
                altitudes = np.unique(altitudes)

                for altitude in altitudes:
                    filepath = self.generate_2d_heatmap(df, band, altitude=altitude)
                    if filepath:
                        output_files.append(filepath)
            else:
                # No altitude data, generate single heatmap
                filepath = self.generate_2d_heatmap(df, band)
                if filepath:
                    output_files.append(filepath)

        logger.info(f"Generated {len(output_files)} heatmap(s)")
        return output_files

    def generate_signal_distribution_plot(self, df: pd.DataFrame, output_filename: str = "signal_distribution.png") -> Path:
        """
        Generate histogram of signal strength distribution

        Args:
            df: DataFrame containing measurements
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram
        ax1 = axes[0]
        bands = df['band'].unique()

        for band in bands:
            band_data = df[df['band'] == band]['signal_dbm']
            ax1.hist(band_data, bins=30, alpha=0.6, label=band)

        ax1.set_xlabel('Signal Strength (dBm)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Signal Strength Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Box plot
        ax2 = axes[1]
        band_data_list = [df[df['band'] == band]['signal_dbm'].values for band in bands]
        ax2.boxplot(band_data_list, labels=bands)
        ax2.set_ylabel('Signal Strength (dBm)')
        ax2.set_title('Signal Strength by Band')
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved distribution plot to {output_path}")
        return output_path

    def generate_coverage_map(self, df: pd.DataFrame, threshold_dbm: float = -100, output_filename: str = "coverage_map.png") -> Path:
        """
        Generate binary coverage map (signal above/below threshold)

        Args:
            df: DataFrame containing measurements
            threshold_dbm: Signal threshold for "coverage"
            output_filename: Output filename

        Returns:
            Path to saved map
        """
        # Remove rows without GPS
        df_gps = df.dropna(subset=['latitude', 'longitude'])

        if df_gps.empty:
            logger.warning("No GPS data for coverage map")
            return None

        fig, ax = plt.subplots(figsize=(12, 10))

        # Separate covered and uncovered points
        covered = df_gps[df_gps['signal_dbm'] >= threshold_dbm]
        uncovered = df_gps[df_gps['signal_dbm'] < threshold_dbm]

        # Plot
        if not uncovered.empty:
            ax.scatter(
                uncovered['longitude'],
                uncovered['latitude'],
                c='red',
                s=100,
                alpha=0.6,
                label=f'Weak Signal (< {threshold_dbm} dBm)',
                marker='x'
            )

        if not covered.empty:
            ax.scatter(
                covered['longitude'],
                covered['latitude'],
                c='green',
                s=100,
                alpha=0.6,
                label=f'Good Signal (≥ {threshold_dbm} dBm)',
                marker='o'
            )

        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title(f'Coverage Map (Threshold: {threshold_dbm} dBm)', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Statistics
        total_points = len(df_gps)
        covered_points = len(covered)
        coverage_pct = (covered_points / total_points * 100) if total_points > 0 else 0

        stats_text = f'Total Points: {total_points}\n'
        stats_text += f'Good Signal: {covered_points}\n'
        stats_text += f'Coverage: {coverage_pct:.1f}%'

        ax.text(
            0.02, 0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=11,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9)
        )

        plt.tight_layout()

        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved coverage map to {output_path}")
        return output_path
