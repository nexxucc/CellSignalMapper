"""
RTL-SDR Scanner Module - Command Line Interface Version
Uses rtl_power tool directly for maximum compatibility
"""

import subprocess
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
import time
import tempfile
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class RTLScannerCLI:
    """Interface for RTL-SDR based signal strength scanning using command-line tools"""

    def __init__(self, config: Dict):
        """
        Initialize RTL-SDR scanner using CLI tools

        Args:
            config: Configuration dictionary containing rtl_sdr settings
        """
        self.config = config
        self.is_initialized = False
        self.rtl_power_path = None

    def initialize(self) -> bool:
        """
        Initialize RTL-SDR device and locate rtl_power tool

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if rtl_power is available
            possible_paths = [
                r"C:\Users\jainv\Downloads\rtlsdr-bin-w64_static\rtl_power.exe",
                "rtl_power.exe",  # In PATH
                "/usr/bin/rtl_power",  # Linux
                "/usr/local/bin/rtl_power",  # Linux alternative
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    self.rtl_power_path = path
                    break
                elif path.endswith('.exe'):
                    # Try running it to see if it's in PATH
                    try:
                        subprocess.run([path, "--help"], capture_output=True, timeout=2)
                        self.rtl_power_path = path
                        break
                    except:
                        continue

            if not self.rtl_power_path:
                logger.error("rtl_power tool not found. Please install rtl-sdr tools.")
                return False

            logger.info(f"Found rtl_power at: {self.rtl_power_path}")

            # Test if RTL-SDR device is accessible
            try:
                test_path = self.rtl_power_path.replace("rtl_power.exe", "rtl_test.exe").replace("rtl_power", "rtl_test")
                logger.debug(f"Testing device with: {test_path}")
                result = subprocess.run(
                    [test_path, "-t"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )

                logger.debug(f"Test result stdout: {result.stdout[:200]}")
                logger.debug(f"Test result stderr: {result.stderr[:200]}")

                # Check both stdout and stderr (rtl_test writes to stderr)
                output = result.stdout + result.stderr
                if "Found" in output and "device" in output:
                    logger.info("RTL-SDR device detected successfully")
                    self.is_initialized = True
                    return True
                else:
                    logger.error(f"No RTL-SDR device found. Return code: {result.returncode}")
                    logger.error(f"Stdout: {result.stdout[:500]}")
                    logger.error(f"Stderr: {result.stderr[:500]}")
                    return False

            except subprocess.TimeoutExpired:
                # Timeout is OK - means device is working
                logger.info("RTL-SDR device detected (test timeout)")
                self.is_initialized = True
                return True
            except Exception as e:
                logger.error(f"Error testing RTL-SDR device: {e}")
                return False

        except Exception as e:
            logger.error(f"Error initializing RTL-SDR scanner: {e}")
            return False

    def scan_frequency_range(self, start_freq_hz: float, end_freq_hz: float,
                            integration_time: float = 1.0) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Scan a frequency range and return signal strength

        Args:
            start_freq_hz: Start frequency in Hz
            end_freq_hz: End frequency in Hz
            integration_time: Integration time in seconds

        Returns:
            Tuple of (frequencies_hz, power_db) or None on error
        """
        if not self.is_initialized:
            logger.error("Scanner not initialized")
            return None

        try:
            # Create temporary file for output
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
                tmp_path = tmp.name

            # Calculate parameters for rtl_power
            # rtl_power usage: rtl_power -f start:end:step -i interval output.csv
            freq_range_mhz = (end_freq_hz - start_freq_hz) / 1e6
            bin_size = int(freq_range_mhz * 1000)  # 1 kHz bins

            start_mhz = start_freq_hz / 1e6
            end_mhz = end_freq_hz / 1e6

            # Build command
            cmd = [
                self.rtl_power_path,
                "-f", f"{start_mhz}M:{end_mhz}M:1k",  # Freq range with 1kHz steps
                "-i", str(int(integration_time)),  # Integration interval
                "-1",  # Single scan
                "-d", str(self.config['rtl_sdr']['device_index']),  # Device index
                "-g", str(self.config['rtl_sdr']['gain']),  # Gain
                tmp_path
            ]

            logger.debug(f"Running: {' '.join(cmd)}")

            # Run rtl_power
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=integration_time + 10
            )

            if result.returncode != 0:
                logger.error(f"rtl_power error: {result.stderr}")
                os.unlink(tmp_path)
                return None

            # Parse output CSV
            # rtl_power CSV format: date, time, Hz low, Hz high, Hz step, samples, dB, dB, dB...
            try:
                with open(tmp_path, 'r') as f:
                    lines = f.readlines()

                os.unlink(tmp_path)

                if not lines:
                    logger.error("rtl_power produced no output")
                    return None

                # Parse the CSV line
                parts = lines[0].strip().split(',')
                hz_low = float(parts[2])
                hz_high = float(parts[3])
                hz_step = float(parts[4])

                # Parse power values, handling invalid/NaN values
                power_values = []
                for x in parts[6:]:
                    try:
                        # Try to convert to float
                        val = float(x.strip())
                        # Replace NaN/Inf with -999 (no signal)
                        if not (val == val and abs(val) < 1e10):  # Check for NaN and Inf
                            val = -999.0
                        power_values.append(val)
                    except (ValueError, OverflowError):
                        # If conversion fails, use -999 (no signal)
                        power_values.append(-999.0)

                # Generate frequency array
                num_bins = len(power_values)
                frequencies = np.linspace(hz_low, hz_high, num_bins)
                powers = np.array(power_values)

                logger.debug(f"Scanned {len(frequencies)} frequency bins from {hz_low/1e6:.2f} to {hz_high/1e6:.2f} MHz")

                return frequencies, powers

            except Exception as e:
                logger.error(f"Error parsing rtl_power output: {e}")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return None

        except subprocess.TimeoutExpired:
            logger.error("rtl_power timeout")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None
        except Exception as e:
            logger.error(f"Error scanning frequency range: {e}")
            return None

    def scan_lte_bands(self, bands_config: Dict) -> Dict[str, float]:
        """
        Scan configured LTE bands and return average signal strength

        Args:
            bands_config: Dictionary of band configurations

        Returns:
            Dictionary mapping band name to average power in dBm
        """
        results = {}

        for band_name, band_config in bands_config.items():
            if not band_config.get('enabled', False):
                logger.debug(f"Skipping disabled band: {band_name}")
                continue

            logger.info(f"Scanning {band_name}...")

            # Get downlink frequency range (handle both Hz and MHz formats)
            freq_start = float(band_config.get('downlink_start_mhz', band_config.get('downlink_start', 0)))
            freq_end = float(band_config.get('downlink_end_mhz', band_config.get('downlink_end', 0)))

            # Convert to Hz if in MHz
            if freq_start < 1e6:
                freq_start *= 1e6
            if freq_end < 1e6:
                freq_end *= 1e6

            scan_result = self.scan_frequency_range(
                freq_start,
                freq_end,
                integration_time=self.config.get('scan', {}).get('integration_time', 1.0)
            )

            if scan_result:
                frequencies, powers = scan_result
                avg_power = np.mean(powers)
                max_power = np.max(powers)

                # Store both summary and raw data
                results[band_name] = {
                    'average_power_dbm': float(avg_power),
                    'max_power_dbm': float(max_power),
                    'frequency_mhz': float(frequencies[np.argmax(powers)] / 1e6),
                    'num_samples': len(frequencies),
                    'raw_data': list(zip(frequencies, powers))  # Add raw (freq, power) pairs
                }

                logger.info(f"{band_name}: Avg={avg_power:.2f} dBm, Max={max_power:.2f} dBm")
            else:
                logger.warning(f"Failed to scan {band_name}")
                results[band_name] = {
                    'average_power_dbm': -999.0,
                    'max_power_dbm': -999.0,
                    'frequency_mhz': 0.0,
                    'num_samples': 0
                }

        return results

    def close(self):
        """Close RTL-SDR device"""
        self.is_initialized = False
        logger.info("RTL-SDR scanner closed")
