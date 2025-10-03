# Cell Signal Mapper

Drone-based cellular signal strength mapping system using RTL-SDR and Raspberry Pi 5.

## Overview

This system maps cellular network coverage by scanning LTE bands while a drone flies a predetermined pattern. It generates:
- Signal strength heatmaps
- Google Earth KML overlays
- Coverage analysis reports
- CSV/JSON data exports

### Current Capabilities

**Hardware Constraints:**
- RTL-SDR V4: 24-1766 MHz scanning range
- Currently supports **LTE Band 5 (850 MHz)** in India
  - Downlink: 869-894 MHz ✅
  - Best for rural/indoor penetration coverage

**Future Expansion:**
The system is designed to support additional bands when hardware is upgraded:
- Band 3 (1800 MHz) - requires SDR capable of 1805-1880 MHz
- Band 40 (2300 MHz) - requires SDR capable of 2300-2400 MHz
- 5G bands - requires wideband SDR

## Hardware Requirements

### Minimum Setup
- **RTL-SDR V4** dongle (24-1766 MHz)
- **Raspberry Pi 5** (4GB+ RAM recommended)
- **GPS Module** (serial/USB, NMEA compatible)
- **700-2700 MHz antenna** (wideband omnidirectional)
- **Drone** with payload capacity for Pi 5 + accessories (~500g)

### Recommended Additions
- Ferrite beads for EMI suppression
- Shielded USB cables
- Dedicated 5V BEC or power regulator
- Gimbal or vibration damping mount

## Software Installation

### On Raspberry Pi 5

1. **Install system dependencies:**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git librtlsdr-dev
```

2. **Clone repository:**
```bash
cd ~
git clone <your-repo-url>
cd CellSignalMapper
```

3. **Create virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

4. **Install Python packages:**
```bash
pip install -r requirements.txt
```

5. **Install RTL-SDR drivers:**
```bash
# Blacklist DVB-T driver that conflicts with RTL-SDR
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl-sdr.conf
sudo rmmod dvb_usb_rtl28xxu  # Unload if currently loaded
```

6. **Test RTL-SDR:**
```bash
rtl_test -t
```

7. **Configure GPS:**
Edit `config/config.yaml` and set correct GPS serial port:
```yaml
gps:
  port: "/dev/ttyUSB0"  # or /dev/ttyAMA0 for GPIO serial
```

## Configuration

Edit `config/config.yaml` to customize:

### RTL-SDR Settings
```yaml
rtl_sdr:
  device_index: 0
  sample_rate: 2.048e6
  gain: 40  # or 'auto'
  ppm_error: 0  # Frequency correction
```

### Band Selection
Enable/disable bands based on your hardware:
```yaml
bands:
  band_5:
    enabled: true  # 850 MHz - works with RTL-SDR V4
  band_3:
    enabled: false  # 1800 MHz - requires upgrade
  band_40:
    enabled: false  # 2300 MHz - requires upgrade
```

### Flight Parameters
```yaml
flight:
  altitude_levels: [10, 20, 30, 50]  # Meters
  grid_spacing: 50  # Meters between points
  hover_time: 3  # Seconds per measurement
```

## Usage

### Test Mode (No Drone)

**Single scan with mock GPS:**
```bash
cd src
python3 main.py --mode single --mock-gps
```

This tests the system without requiring actual GPS or drone hardware.

### Single Scan (Stationary)

**With real GPS:**
```bash
python3 main.py --mode single
```

Performs one scan at current location and exits.

### Continuous Scan (Drone Flight)

**Start continuous scanning:**
```bash
python3 main.py --mode continuous --interval 10
```

- Scans every 10 seconds
- Logs GPS coordinates with each measurement
- Press `Ctrl+C` to stop and generate outputs

**Recommended workflow:**
1. Start continuous scan on ground
2. Wait for GPS fix
3. Launch drone and begin flight pattern
4. Let scanner run throughout flight
5. Land drone and press Ctrl+C
6. System automatically generates all visualizations

## Output Files

After scanning, check these directories:

### Data Files
- `data/signal_data_YYYYMMDD_HHMMSS.csv` - Raw measurements
- `data/signal_data_YYYYMMDD_HHMMSS.json` - Structured data

### Visualizations
- `output/heatmap_*.png` - Signal strength heatmaps by band/altitude
- `output/signal_distribution.png` - Histogram and box plots
- `output/coverage_map.png` - Binary coverage map

### Google Earth Files
- `output/signal_map.kml` - Measurement points colored by signal strength
- `output/coverage_zones.kml` - Good/weak coverage zones

### Logs
- `logs/signal_mapper_YYYYMMDD_HHMMSS.log` - Detailed debug logs

## Viewing Results

### Google Earth
1. Open Google Earth Pro
2. File → Open → Select `signal_map.kml`
3. Use altitude slider to view different flight levels
4. Click markers to see signal details

### Analysis
```bash
# View CSV in pandas
python3
>>> import pandas as pd
>>> df = pd.read_csv('data/signal_data_20250101_120000.csv')
>>> df.describe()
```

## Troubleshooting

### RTL-SDR Not Detected
```bash
# Check if device is connected
lsusb | grep Realtek

# Test device
rtl_test -t

# Check permissions
sudo usermod -a -G plugdev $USER
# Log out and back in
```

### GPS Not Working
```bash
# Find GPS device
ls /dev/tty*

# Test GPS output
cat /dev/ttyUSB0  # Should see NMEA sentences

# Check permissions
sudo chmod 666 /dev/ttyUSB0
```

### Poor Signal Reception
- Check antenna connections
- Ensure antenna is away from drone motors/ESCs
- Add ferrite beads to USB cable
- Increase gain in config (try 40-50)
- Verify frequency correction (ppm_error)

### Drone EMI Issues
- Use shielded USB cables
- Mount SDR away from power lines
- Add RF shielding to Pi case
- Use separate power supply for Pi
- Increase physical distance from ESCs

## Calibration

For accurate signal measurements:

1. **PPM Correction:**
```bash
# Find your RTL-SDR frequency error
rtl_test -p
# Set ppm_error in config.yaml
```

2. **Signal Calibration:**
- Use known cell tower location
- Compare readings with professional equipment
- Adjust offset in `rtl_scanner.py` line 72

## Future Enhancements

### When Upgrading SDR Hardware

To enable all Indian LTE bands, upgrade to:
- **HackRF One** (1 MHz - 6 GHz) - ~$300
- **LimeSDR Mini** (10 MHz - 3.5 GHz) - ~$150

Then enable additional bands in `config.yaml`:
```yaml
bands:
  band_3:
    enabled: true
    downlink_start: 1805e6
    downlink_end: 1880e6
  band_40:
    enabled: true
    downlink_start: 2300e6
    downlink_end: 2400e6
```

No code changes needed - system automatically scans all enabled bands.

### Planned Features
- Real-time web dashboard
- Automated drone flight control integration
- LTE cell tower ID decoding
- Multi-operator comparison
- 5G NR support
- Machine learning coverage prediction

## Project Structure

```
CellSignalMapper/
├── config/
│   └── config.yaml          # Main configuration
├── src/
│   ├── main.py             # Main application
│   ├── scanner/            # RTL-SDR interface
│   ├── gps/                # GPS coordinate acquisition
│   ├── utils/              # Data logging utilities
│   ├── processor/          # Heatmap generation
│   └── exporter/           # KML/CSV export
├── data/                   # Measurement data (CSV/JSON)
├── output/                 # Visualizations (PNG/KML)
├── logs/                   # Application logs
└── requirements.txt        # Python dependencies
```

## Contributing

This is a proof-of-concept system. Contributions welcome for:
- Additional LTE band support
- Improved signal processing algorithms
- Real-time visualization
- Drone autopilot integration
- Battery optimization

## License

MIT License - See LICENSE file

## Safety Notes

⚠️ **Important:**
- Follow local drone regulations
- Maintain line-of-sight with drone
- Avoid flying near airports/restricted areas
- Ensure secure mounting of all equipment
- Test thoroughly on ground before flight
- Monitor battery levels closely
- Have emergency landing plan

## Credits

Built with:
- pyrtlsdr - RTL-SDR Python wrapper
- simplekml - KML generation
- matplotlib - Visualization
- scipy - Signal processing
- pynmea2 - GPS parsing

---

**Status:** Proof of Concept
**Version:** 1.0.0
**Last Updated:** 2025
