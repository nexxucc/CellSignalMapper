"""
Cell Signal Mapper - Main Application
Drone-based cellular signal strength mapping system
"""

import yaml
import logging
import argparse
from pathlib import Path
from datetime import datetime
import sys
import time

import platform

from scanner import RTLScannerCLI
from gps import GPSReader, MockGPSReader, WindowsGPSReader
from utils import DataLogger
from processor import HeatmapGenerator
from exporter import KMLExporter


def setup_logging(config: dict) -> None:
    """Setup logging configuration"""
    log_level = getattr(logging, config['logging']['log_level'])

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # File handler (if enabled)
    handlers = [console_handler]

    if config['logging']['log_to_file']:
        log_dir = Path(config['logging']['log_dir'])
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"signal_mapper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

    logging.info(f"Logging initialized (level: {config['logging']['log_level']})")


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file"""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def get_gps_reader(config: dict, use_mock_gps: bool = False):
    """
    Get appropriate GPS reader based on platform

    Args:
        config: Configuration dictionary
        use_mock_gps: Use simulated GPS data

    Returns:
        GPS reader instance
    """
    if use_mock_gps:
        return MockGPSReader(config)
    elif platform.system() == 'Windows':
        return WindowsGPSReader(config)
    else:
        return GPSReader(config)


def get_scanner(config: dict):
    """
    Get RTL-SDR scanner instance

    Args:
        config: Configuration dictionary

    Returns:
        Scanner instance
    """
    return RTLScannerCLI(config)


def single_scan_mode(config: dict, use_mock_gps: bool = False):
    """
    Perform a single scan at current location

    Args:
        config: Configuration dictionary
        use_mock_gps: Use simulated GPS data
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Starting Single Scan Mode ===")

    # Initialize components
    scanner = get_scanner(config)
    gps_reader = get_gps_reader(config, use_mock_gps)
    data_logger = DataLogger(config)

    try:
        # Initialize RTL-SDR
        if not scanner.initialize():
            logger.error("Failed to initialize RTL-SDR")
            return

        # Connect GPS
        if config['gps']['enabled']:
            if not gps_reader.connect():
                logger.warning("GPS connection failed, proceeding without GPS")
            else:
                logger.info("Waiting for GPS fix...")
                gps_reader.wait_for_fix(timeout=30)

        # Get current position
        gps_coord = gps_reader.read_position() if gps_reader.is_connected else None

        if gps_coord:
            logger.info(f"GPS Position: {gps_coord}")
            lat, lon, alt = gps_coord.latitude, gps_coord.longitude, gps_coord.altitude
        else:
            logger.warning("No GPS fix available")
            lat, lon, alt = None, None, None

        # Perform scan
        logger.info("Starting signal scan...")
        scan_results = scanner.scan_lte_bands(config['bands'])

        # Log results
        timestamp = datetime.now()
        data_logger.log_scan_results(lat, lon, alt, scan_results, timestamp)

        # Display results
        logger.info("\n=== Scan Results ===")
        for band_name, results in scan_results.items():
            if results and isinstance(results, dict):
                logger.info(f"{band_name}:")
                logger.info(f"  Average Power: {results.get('average_power_dbm', 0):.2f} dBm")
                logger.info(f"  Max Power: {results.get('max_power_dbm', 0):.2f} dBm at {results.get('frequency_mhz', 0):.2f} MHz")
                logger.info(f"  Scanned {results.get('num_samples', 0)} frequency points")

        # Save data
        logger.info("\n=== Saving Data ===")
        if config['export']['csv_enabled']:
            csv_path = data_logger.save_to_csv()
            logger.info(f"CSV: {csv_path}")

        if config['export']['json_enabled']:
            json_path = data_logger.save_to_json()
            logger.info(f"JSON: {json_path}")

        # Generate visualizations
        if len(data_logger) > 0:
            df = data_logger.get_dataframe()

            if config['export']['kml_enabled'] and df['latitude'].notna().any():
                logger.info("Generating KML export...")
                kml_exporter = KMLExporter(config)
                kml_path = kml_exporter.export_to_kml(df)
                logger.info(f"KML: {kml_path}")

        logger.info("\n=== Single Scan Complete ===")

    except KeyboardInterrupt:
        logger.info("Scan interrupted by user")
    except Exception as e:
        logger.error(f"Error during scan: {e}", exc_info=True)
    finally:
        scanner.close()
        gps_reader.disconnect()


def continuous_scan_mode(config: dict, interval: int = 10, use_mock_gps: bool = False):
    """
    Continuously scan at regular intervals (for drone flight)

    Args:
        config: Configuration dictionary
        interval: Seconds between scans
        use_mock_gps: Use simulated GPS data
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Starting Continuous Scan Mode ===")
    logger.info(f"Scan interval: {interval} seconds")

    # Initialize components
    scanner = get_scanner(config)
    gps_reader = get_gps_reader(config, use_mock_gps)
    data_logger = DataLogger(config)

    try:
        # Initialize RTL-SDR
        if not scanner.initialize():
            logger.error("Failed to initialize RTL-SDR")
            return

        # Connect GPS
        if config['gps']['enabled']:
            if gps_reader.connect():
                logger.info("Waiting for initial GPS fix...")
                gps_reader.wait_for_fix(timeout=60)
            else:
                logger.warning("GPS connection failed, proceeding without GPS")

        scan_count = 0

        while True:
            scan_count += 1
            logger.info(f"\n=== Scan #{scan_count} ===")

            # Get current position
            gps_coord = gps_reader.read_position(timeout=2) if gps_reader.is_connected else None

            if gps_coord:
                logger.info(f"Position: {gps_coord}")
                lat, lon, alt = gps_coord.latitude, gps_coord.longitude, gps_coord.altitude
            else:
                logger.warning("No GPS fix")
                lat, lon, alt = None, None, None

            # Perform scan
            scan_results = scanner.scan_lte_bands(config['bands'])

            # Log results
            timestamp = datetime.now()
            data_logger.log_scan_results(lat, lon, alt, scan_results, timestamp)

            # Display quick summary
            for band_name, results in scan_results.items():
                if results and isinstance(results, dict):
                    logger.info(f"{band_name}: Avg={results.get('average_power_dbm', 0):.2f} dBm, Max={results.get('max_power_dbm', 0):.2f} dBm")

            logger.info(f"Total measurements: {len(data_logger)}")

            # Wait for next scan
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("\n=== Continuous scan stopped by user ===")

        # Save all collected data
        logger.info("Saving data...")

        if config['export']['csv_enabled']:
            csv_path = data_logger.save_to_csv()
            logger.info(f"CSV: {csv_path}")

        if config['export']['json_enabled']:
            json_path = data_logger.save_to_json()
            logger.info(f"JSON: {json_path}")

        # Generate visualizations
        if len(data_logger) > 0:
            df = data_logger.get_dataframe()

            # Heatmaps
            if df['latitude'].notna().any():
                logger.info("Generating heatmaps...")
                heatmap_gen = HeatmapGenerator(config)
                heatmap_gen.generate_all_heatmaps(df)
                heatmap_gen.generate_signal_distribution_plot(df)
                heatmap_gen.generate_coverage_map(df)

            # KML export
            if config['export']['kml_enabled'] and df['latitude'].notna().any():
                logger.info("Generating KML exports...")
                kml_exporter = KMLExporter(config)
                kml_exporter.export_to_kml(df, include_paths=True)
                kml_exporter.export_coverage_zones(df)

            # Summary statistics
            stats = data_logger.get_summary_statistics()
            logger.info("\n=== Session Summary ===")
            logger.info(f"Total measurements: {stats['total_measurements']}")
            logger.info(f"Bands scanned: {', '.join(stats['bands_scanned'])}")
            logger.info(f"Signal range: {stats['signal_stats']['min_dbm']:.1f} to {stats['signal_stats']['max_dbm']:.1f} dBm")

        logger.info("\n=== Scan Session Complete ===")

    except Exception as e:
        logger.error(f"Error during continuous scan: {e}", exc_info=True)
    finally:
        scanner.close()
        gps_reader.disconnect()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Cell Signal Mapper - Drone-based cellular coverage mapping"
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['single', 'continuous'],
        default='single',
        help='Scan mode: single (one scan) or continuous (repeated scans)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Interval between scans in continuous mode (seconds)'
    )

    parser.add_argument(
        '--mock-gps',
        action='store_true',
        help='Use simulated GPS data for testing'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config(args.config)

        # Setup logging
        setup_logging(config)

        logger = logging.getLogger(__name__)
        logger.info("Cell Signal Mapper initialized")
        logger.info(f"Config: {args.config}")
        logger.info(f"Mode: {args.mode}")

        # Run appropriate mode
        if args.mode == 'single':
            single_scan_mode(config, use_mock_gps=args.mock_gps)
        else:
            continuous_scan_mode(config, interval=args.interval, use_mock_gps=args.mock_gps)

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
