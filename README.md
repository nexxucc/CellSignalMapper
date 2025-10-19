# Cell Signal Mapper

Drone-based cellular signal strength mapping system using RTL-SDR, Pixhawk autopilot, and Raspberry Pi 5.

## Overview

This system maps cellular network coverage by scanning LTE bands during autonomous drone flights. It integrates with Pixhawk flight controller for GPS data via MAVLink protocol and uses RTL-SDR for RF signal measurement.

**Outputs:**

- Signal strength heatmaps (PNG)
- Google Earth 3D overlays (KML)
- Raw measurement data (CSV/JSON)
- Coverage analysis reports

**Current Capabilities:**

- LTE Band 5 (850 MHz): 869-894 MHz downlink ✅
- GPS positioning via Pixhawk MAVLink
- Autonomous scanning during flight
- Real-time data logging with timestamps

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Drone Platform                       │
│                                                         │
│  ┌────────────┐  MAVLink   ┌──────────────────┐        │
│  │  Pixhawk   │◄──────────►│ Raspberry Pi 5   │        │
│  │ Autopilot  │  GPS/Telem │  (Processing)    │        │
│  └─────┬──────┘            └────────┬─────────┘        │
│        │                            │                   │
│   ┌────▼────┐                  ┌────▼────┐             │
│   │   GPS   │                  │ RTL-SDR │             │
│   │ Module  │                  │   V4    │             │
│   └─────────┘                  └────┬────┘             │
│                                     │                   │
│                                ┌────▼────┐             │
│                                │ Antenna │             │
│                                │700-2700 │             │
│                                │   MHz   │             │
│                                └─────────┘             │
└─────────────────────────────────────────────────────────┘

Data Flow:
GPS → Pixhawk → MAVLink → Raspberry Pi → Data Logger
                              ↓
                          RTL-SDR → RF Signal → Processing
```

**Key Components:**

- **Pixhawk Flight Controller**: Provides GPS coordinates, telemetry, and flight control
- **Raspberry Pi 5**: Runs scanning software, processes MAVLink data
- **RTL-SDR V4**: Software-Defined Radio for LTE signal measurement (24-1766 MHz)
- **GPS Module**: Connected to Pixhawk (NEO-M8N or similar)
- **Wideband Antenna**: 700-2700 MHz omnidirectional

---

## Hardware Requirements

### Core Components

- **Pixhawk Flight Controller** (4/5/6 series)
- **GPS Module** (NEO-M8N, M9N, or compatible) connected to Pixhawk
- **Raspberry Pi 5** (4GB+ RAM)
- **RTL-SDR V4** dongle
- **700-2700 MHz antenna** (wideband omnidirectional)
- **Drone frame** with 500g+ payload capacity

### Connections

1. **Pixhawk ↔ Raspberry Pi**:

   - UART (TELEM1/TELEM2): TX, RX, GND
   - USB (optional backup connection)
   - Power sharing or separate BEC
2. **RTL-SDR ↔ Raspberry Pi**:

   - USB connection
   - Antenna to SDR
3. **GPS ↔ Pixhawk**:

   - GPS port on Pixhawk

### Recommended Additions

- Ferrite beads for EMI suppression
- Shielded USB cables
- Dedicated 5V BEC for Pi
- Vibration damping mounts
- Power module for Pixhawk

---

## Software Installation

### 1. Raspberry Pi Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv git \
    librtlsdr-dev rtl-sdr i2c-tools

# Clone repository
cd ~
git clone <your-repo-url>
cd CellSignalMapper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 2. RTL-SDR Configuration

```bash
# Blacklist conflicting DVB-T driver
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl-sdr.conf
sudo rmmod dvb_usb_rtl28xxu 2>/dev/null || true

# Test RTL-SDR
rtl_test -t
# Should show "Found 1 device(s)"
```

### 3. MAVLink/MAVProxy Setup

```bash
# Install MAVProxy (if not already installed)
pip install mavproxy pymavlink

# MAVProxy should auto-detect Pixhawk on /dev/ttyAMA0 or /dev/ttyUSB0
# System will automatically read GPS from MAVLink telemetry
```

### 4. Enable UART (if using GPIO connection)

```bash
sudo raspi-config
# Interface Options → Serial Port
# "Login shell over serial?" → No
# "Serial port hardware enabled?" → Yes
sudo reboot
```

---

## Configuration

Edit `config/config.yaml`:

### RTL-SDR Settings

```yaml
rtl_sdr:
  device_index: 0
  sample_rate: 2048000
  gain: 40  # or 'auto'
  ppm_error: 0  # Frequency correction (use rtl_test -p to find)
```

### LTE Band Configuration

```yaml
bands:
  band_5:
    name: "LTE Band 5 (850 MHz)"
    enabled: true
    downlink_start: 869000000  # 869 MHz
    downlink_end: 894000000    # 894 MHz
    scan_points: 10

  band_3:
    enabled: false  # Requires SDR >1.8 GHz
  band_40:
    enabled: false  # Requires SDR >2.3 GHz
```

### Scanning Parameters

```yaml
scan:
  integration_time: 1.0  # Seconds (optimized for mobile mapping)
```

### GPS Settings (MAVLink)

```yaml
gps:
  enabled: true
  port: "/dev/serial0"  # MAVLink telemetry port
  baud_rate: 57600      # Standard MAVLink baud (or 115200)
  timeout: 1.0
  min_satellites: 4

  # Optional: Compass from Pixhawk
  compass_enabled: false
  compass_i2c_address: 0x1E
```

### Flight Parameters

```yaml
flight:
  altitude_levels: [10, 20, 30, 50]  # Meters
  grid_spacing: 50  # Meters between measurement points
  hover_time: 3  # Seconds per measurement point
```

---

## Usage

### Test System (Ground)

```bash
cd ~/CellSignalMapper
source venv/bin/activate

# Single scan test (mock GPS for indoor testing)
python3 src/main.py --mode single --mock-gps

# Single scan with real Pixhawk GPS
python3 src/main.py --mode single
```

**Expected output:**

```
INFO - Cell Signal Mapper initialized
INFO - GPS connected via MAVLink
INFO - GPS fix acquired: GPSCoordinate(lat=XX.XXXX, lon=YY.YYYY, alt=ZZm, sats=8)
INFO - Scanning band_5...
INFO - band_5: Avg=-55.20 dBm, Max=-45.30 dBm
```

### Continuous Scanning (Flight)

```bash
# Auto-stops after 15 minutes (default)
python3 src/main.py --mode continuous

# Custom duration (20 minutes)
python3 src/main.py --mode continuous --duration 20

# Custom scan interval (1 second between scans)
python3 src/main.py --mode continuous --interval 1
```

**Flight Workflow:**

1. Power on drone (Pixhawk boots)
2. SSH to Raspberry Pi: `ssh drone@10.149.47.166`
3. Start scanner: `python3 src/main.py --mode continuous`
4. Wait for "GPS fix acquired"
5. Arm and launch drone
6. Execute flight plan
7. Land drone
8. Scanner auto-stops or press `Ctrl+C`
9. Download data files from `data/` and `output/`

---

## Output Files

### Data Directory (`data/`)

- `signal_data_YYYYMMDD_HHMMSS.csv` - Raw measurements
  - Columns: timestamp, latitude, longitude, altitude, band, frequency_hz, signal_dbm
- `signal_data_YYYYMMDD_HHMMSS.json` - Structured data with metadata

### Visualizations (`output/`)

- `heatmap_band_5_*.png` - Signal strength heatmaps by altitude
- `signal_distribution.png` - Histogram and box plots
- `coverage_map.png` - Binary coverage map (good/weak zones)
- `signal_map_YYYYMMDD_HHMMSS.kml` - Google Earth 3D visualization

### Logs (`logs/`)

- `signal_mapper_YYYYMMDD_HHMMSS.log` - Detailed debug logs

---

## Viewing Results

### Google Earth

```bash
# On Windows/Mac after downloading files
1. Open Google Earth Pro
2. File → Open → Select output/signal_map_*.kml
3. Use altitude slider to view different flight levels
4. Click markers to see signal strength details
```

### Data Analysis

```python
import pandas as pd

# Load CSV
df = pd.read_csv('data/signal_data_20250119_143000.csv')

# Basic statistics
print(df.describe())

# Filter strong signals
strong_signals = df[df['signal_dbm'] > -70]
print(f"Strong signal locations: {len(strong_signals)}")

# Group by altitude
by_altitude = df.groupby('altitude')['signal_dbm'].mean()
print(by_altitude)
```

---

## Performance Characteristics

### Optimized Settings (Current Configuration)

**Integration Time: 1.0 seconds**

- Minimum required by rtl_power
- Optimal for mobile/drone mapping
- LTE signals are strong and continuous
- Prioritizes spatial coverage over integration depth

**Scan Interval: 0.5 seconds**

- Cycle time: ~1.85s per scan (1.2s RTL-SDR + 0.1s GPS + 0.55s overhead)
- Sample spacing: 9-18 meters (at 5-10 m/s drone speed)
- Excellent spatial resolution for heatmap interpolation

**Expected Performance (15-minute flight):**

```
Flight duration:       15 minutes (900 seconds)
Total scans:           ~487 scans
Frequency bins/scan:   ~25,000 (1 kHz resolution)
Total measurements:    ~12.2 million frequency points
File size (CSV):       ~400-500 MB
File size (JSON):      ~600-800 MB
```

---

## Troubleshooting

### Pixhawk/MAVLink Issues

**GPS not detected:**

```bash
# Check MAVLink connection
mavproxy.py --master=/dev/ttyAMA0 --baudrate 57600

# Should show:
# "GPS: 3D Fix, 12 satellites"
# "MAVLink connection OK"

# If not working, check:
ls -l /dev/ttyAMA0  # or /dev/ttyUSB0
sudo usermod -a -G dialout $USER  # Add user to serial group
sudo reboot
```

**Wrong baud rate:**

```yaml
# Try these common rates in config.yaml:
baud_rate: 57600   # Most common
baud_rate: 115200  # High-speed telemetry
baud_rate: 921600  # Very high-speed (Pi 5 only)
```

### RTL-SDR Issues

**Device not detected:**

```bash
# Check USB connection
lsusb | grep Realtek
# Should show: "Realtek Semiconductor Corp. RTL2838 DVB-T"

# Test device
rtl_test -t

# Check permissions
sudo usermod -a -G plugdev $USER
sudo reboot
```

**Poor signal reception:**

- Check antenna connections
- Mount antenna away from motors/ESCs
- Add ferrite beads to USB cable
- Increase gain: `gain: 49` in config.yaml
- Verify frequency correction: `rtl_test -p`

### Drone EMI (Electromagnetic Interference)

**Symptoms:** Noisy signals, GPS dropouts, RTL-SDR errors

**Solutions:**

- Use shielded USB cables
- Mount RTL-SDR away from power lines and ESCs
- Add RF shielding to Pi case
- Use separate power supply for Pi (via BEC)
- Increase physical distance between components
- Test system on ground with motors running

---

## Technical Details

### RTL-SDR V4 Specifications

- **Frequency Range:** 24 MHz - 1.766 GHz
- **Tuner:** Rafael Micro R828D
- **ADC:** 8-bit, up to 2.4 MSPS
- **Interface:** USB 2.0
- **Sensitivity:** Typ. -105 dBm @ 1 GHz

### Frequency Scanning Process

Uses `rtl_power` command-line tool for spectrum analysis:

```bash
# Example command (automated by system)
rtl_power -f 869M:894M:1k -i 1 -1 -d 0 -g 40 output.csv

# Parameters:
# -f: Frequency range (start:end:step)
# -i: Integration time (seconds)
# -1: Single scan
# -d: Device index
# -g: Gain (dB)
```

**Process:**

1. Set frequency range (869-894 MHz for Band 5)
2. Set integration time (1 second)
3. Capture RF spectrum via FFT
4. Calculate power spectral density
5. Output CSV with frequency bins and power levels (dBm)

### Signal Strength Interpretation

**dBm Scale:**

```
-40 to -60 dBm:  Excellent (next to tower)
-60 to -80 dBm:  Good (normal coverage)
-80 to -100 dBm: Weak (edge of coverage)
-100 to -120 dBm: Very weak (unreliable)
< -120 dBm:      No service
```

### MAVLink GPS Data

System automatically extracts from MAVLink telemetry:

- `GLOBAL_POSITION_INT` message (lat, lon, alt)
- `GPS_RAW_INT` message (satellites, HDOP)
- Update rate: 1-10 Hz (configured in Pixhawk)

---

## LTE Band Support

### Current: Band 5 (850 MHz)

- **Frequency:** 869-894 MHz downlink ✅
- **Coverage:** Rural, indoor penetration
- **Operators:** All major Indian carriers
- **Scannable:** Fully within RTL-SDR V4 range

### Future Expansion (Hardware Upgrade Required)

**Band 3 (1800 MHz):** Requires SDR >1.8 GHz

- Upgrade to: HackRF One, LimeSDR Mini, or Airspy
- Enable in config.yaml after upgrade

**Band 40 (2300 MHz):** Requires SDR >2.3 GHz

- Same hardware upgrades
- System auto-scans all enabled bands

**5G NR Bands:** Planned support

- Requires 3.5+ GHz SDR capability

---

## Safety & Regulations

⚠️ **Important Safety Notes:**

**Drone Operations:**

- Follow local drone regulations (DGCA in India)
- Maintain visual line-of-sight
- Avoid airports, restricted areas, and crowds
- Check NOTAM before flight
- Ensure secure mounting of all equipment
- Monitor battery levels closely
- Have emergency landing procedures ready

**RF Safety:**

- RTL-SDR is receive-only (passive scanning)
- No transmission - no RF safety concerns
- Legal to scan public cellular frequencies

**Data Privacy:**

- System captures only signal strength, not content
- No phone numbers, calls, or messages intercepted
- Complies with legal passive monitoring regulations

---

## Project Structure

```
CellSignalMapper/
├── config/
│   └── config.yaml              # Main configuration
├── src/
│   ├── main.py                  # Entry point
│   ├── scanner/
│   │   ├── rtl_scanner_cli.py   # RTL-SDR control
│   │   └── __init__.py
│   ├── gps/
│   │   ├── gps_module.py        # MAVLink GPS reader
│   │   ├── windows_gps.py       # Windows testing GPS
│   │   └── __init__.py
│   ├── utils/
│   │   └── data_logger.py       # CSV/JSON logging
│   ├── processor/
│   │   └── heatmap_generator.py # Visualization
│   └── exporter/
│       └── kml_exporter.py      # Google Earth export
├── data/                        # Output CSV/JSON files
├── output/                      # Visualizations (PNG/KML)
├── logs/                        # Application logs
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## Known Issues & Bugs Fixed

### Critical Bugs Resolved (v1.1.0)

1. ✅ RTL-SDR integration time minimum enforcement (was breaking scans)
2. ✅ Scanner timeout variable mismatch
3. ✅ Temporary file cleanup in exception handlers
4. ✅ Consistent raw_data structure in scan results
5. ✅ KML filename collision (now uses unique timestamps)
6. ✅ Variable shadowing in visualization code
7. ✅ NaN value handling in signal processing

**Current Status:** Production-ready for flight testing

---

## Calibration

### RTL-SDR Frequency Correction

```bash
# Find PPM error
rtl_test -p

# Example output:
# "Real sample rate: 2048483 current PPM: 235"

# Update config.yaml:
rtl_sdr:
  ppm_error: 235
```

### Signal Strength Calibration

Optional: Compare with professional equipment

- Use known cell tower location
- Take reference measurements with calibrated equipment
- Calculate offset if needed
- Typically RTL-SDR V4 is accurate within ±3 dB

---

## Future Enhancements

### Planned Features

- [ ] Real-time web dashboard
- [ ] Automated flight plan generation
- [ ] LTE cell tower ID decoding (via OsmocomBB)
- [ ] Multi-operator comparison
- [ ] 5G NR band support
- [ ] Machine learning coverage prediction
- [ ] Interference detection and mapping

### Hardware Upgrades

- **HackRF One** (1 MHz - 6 GHz) - Full LTE + 5G support
- **LimeSDR Mini** (10 MHz - 3.5 GHz) - Budget wideband option
- **Airspy R2** (24 MHz - 1.8 GHz) - Better sensitivity

---

## Contributing

Contributions welcome! Areas of interest:

- Additional LTE band support
- Improved signal processing algorithms
- Real-time visualization
- PX4/ArduPilot mission integration
- Battery optimization
- Alternative SDR hardware support

---

## Credits

**Built with:**

- [pyrtlsdr](https://github.com/roger-/pyrtlsdr) - RTL-SDR Python wrapper
- [MAVProxy](https://github.com/ArduPilot/MAVProxy) - MAVLink telemetry
- [simplekml](https://simplekml.readthedocs.io/) - KML generation
- [matplotlib](https://matplotlib.org/) - Visualization
- [scipy](https://scipy.org/) - Signal processing
- [pynmea2](https://github.com/Knio/pynmea2) - NMEA GPS parsing

**Special thanks to:**

- RTL-SDR.com community
- ArduPilot/PX4 developers
- Open-source SDR community

---

## License

MIT License - See LICENSE file

---

## Status

**Version:** 1.1.0
**Status:** Production-ready for flight testing
**Last Updated:** January 2025
**Hardware:** Pixhawk + Raspberry Pi 5 + RTL-SDR V4
**GPS:** MAVLink via Pixhawk autopilot

---

## Quick Reference Commands

# System check

rtl_test -t                          # Test RTL-SDR
mavproxy.py --master=/dev/ttyAMA0    # Test MAVLink

# Run scanner

python3 src/main.py --mode single    # Single scan
python3 src/main.py --mode continuous --duration 15  # 15-min flight

# View logs

tail -f logs/signal_mapper_*.log
