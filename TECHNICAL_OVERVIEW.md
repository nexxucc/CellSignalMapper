# Cell Signal Mapper - Technical Overview

**Project:** Drone-Based Cellular Signal Strength Mapping System
**Hardware:** RTL-SDR V4, Raspberry Pi 5, GPS Module
**Objective:** Map LTE cellular network coverage using Software-Defined Radio

---

## 1. System Architecture

### Hardware Components

```
┌─────────────────────────────────────────────────┐
│            Signal Mapping System                │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │   RTL-SDR    │ ───USB──│  Raspberry Pi 5 │  │
│  │   V4 SDR     │         │  (Processing)   │  │
│  └──────────────┘         └─────────────────┘  │
│         ▲                          │           │
│         │                          ▼           │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │ 700-2700MHz  │         │   GPS Module    │  │
│  │   Antenna    │         │   (UART/USB)    │  │
│  └──────────────┘         └─────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Component Functions

**RTL-SDR V4:**
- Software-Defined Radio receiver
- Frequency range: 24 MHz - 1.766 GHz
- Tuner: Rafael Micro R828D
- ADC: 8-bit, 2.048 MSPS
- Interface: USB 2.0

**Raspberry Pi 5:**
- Controls RTL-SDR via USB
- Runs Python signal processing code
- Logs data with GPS timestamps
- Manages data export

**GPS Module:**
- Provides spatial coordinates
- Outputs: Latitude, Longitude, Altitude
- Protocol: NMEA (serial) or USB
- Update rate: 1 Hz typical

---

## 2. Software Architecture

### Module Structure

```
src/
├── main.py                      # Entry point
│
├── scanner/                     # RTL-SDR Control
│   └── rtl_scanner_cli.py      # Frequency scanning
│
├── gps/                        # Location Services
│   ├── gps_module.py           # Serial GPS (Pi)
│   └── windows_gps.py          # Windows testing
│
├── utils/                      # Data Management
│   └── data_logger.py          # CSV/JSON logging
│
├── processor/                  # Analysis
│   └── heatmap_generator.py    # Visualization
│
└── exporter/                   # Output
    └── kml_exporter.py         # Google Earth export
```

### Data Flow

```
Antenna → RTL-SDR → USB → Python Script → Data Files
             ↓                      ↑
         RF Signal              GPS Module
                                    ↓
                            (lat, lon, alt)
```

---

## 3. Technical Implementation

### Frequency Scanning Process

**Tool Used:** `rtl_power` (command-line SDR spectrum analyzer)

**Process:**
```
1. Set frequency range: 869 MHz - 894 MHz (LTE Band 5)
2. Set step size: 1 kHz
3. Set integration time: 1 second
4. Execute scan:
   - RTL-SDR tunes to each frequency
   - Captures IQ samples (In-phase/Quadrature)
   - Computes FFT (Fast Fourier Transform)
   - Converts to power: P(dBm) = 10 × log₁₀(|FFT|²)
5. Output: CSV with frequency vs power data
```

**Code Implementation:**
```python
# Build rtl_power command
cmd = [
    "rtl_power",
    "-f", "869M:894M:1k",      # Freq: start:end:step
    "-i", "1",                  # Integration: 1 second
    "-1",                       # Single scan
    "-d", "0",                  # Device index
    "-g", "40",                 # Gain (dB)
    "output.csv"                # Output file
]

# Execute
subprocess.run(cmd, timeout=10)

# Parse CSV output
frequencies, powers = parse_rtl_power_output("output.csv")
```

### GPS Coordinate Acquisition

**Linux/Raspberry Pi (Serial GPS):**
```python
import serial
import pynmea2

# Open serial port
ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)

# Read NMEA sentences
while True:
    line = ser.readline().decode('ascii')

    if line.startswith('$GPGGA'):  # GPS fix data
        msg = pynmea2.parse(line)
        lat = msg.latitude
        lon = msg.longitude
        alt = msg.altitude
        break
```

**Windows (WiFi-based location):**
```python
import subprocess
import json

# PowerShell script to access Windows Location API
ps_script = '''
Add-Type -AssemblyName System.Device
$watcher = New-Object System.Device.Location.GeoCoordinateWatcher
$watcher.Start()

# Wait for fix
while ($watcher.Status -ne 'Ready') {
    Start-Sleep -Milliseconds 100
}

# Get coordinates
$coord = $watcher.Position.Location
@{
    latitude = $coord.Latitude
    longitude = $coord.Longitude
} | ConvertTo-Json
'''

result = subprocess.run(['powershell', '-Command', ps_script])
data = json.loads(result.stdout)
```

### Data Logging

**Measurement Structure:**
```python
measurement = {
    'timestamp': '2025-10-03 00:01:07',
    'latitude': 12.843346,
    'longitude': 80.156625,
    'altitude': 0,
    'band': 'band_5',
    'frequency_hz': 869500000,
    'frequency_mhz': 869.5,
    'signal_dbm': -55.2
}
```

**Storage Format:**
- In-memory: Python list of dictionaries
- On disk: CSV (spreadsheet), JSON (structured data)
- Visualization: KML (Google Earth format)

---

## 4. Algorithms & Signal Processing

### Fast Fourier Transform (FFT)

**Purpose:** Convert time-domain signal to frequency domain

**How it works:**
1. RTL-SDR captures IQ samples (complex numbers)
2. Apply FFT: X[k] = Σ x[n] × e^(-j2πkn/N)
3. Result: Frequency bins with complex amplitudes
4. Compute power: P = |X[k]|²
5. Convert to dBm: P_dBm = 10 × log₁₀(P)

**Why FFT:**
- Identifies which frequencies have signals
- Separates cell tower signals from noise
- Efficient: O(n log n) complexity

### Signal Strength Interpretation

**dBm Scale (logarithmic power measurement):**
- 0 dBm = 1 milliwatt
- -30 dBm = 0.001 milliwatts
- Every -3 dB ≈ half the power

**Typical LTE Signal Levels:**
- -40 to -60 dBm: Strong (close to tower)
- -60 to -80 dBm: Good (normal service)
- -80 to -100 dBm: Weak (edge of coverage)
- Below -100 dBm: Poor (no service)

### Spatial Interpolation (Heatmaps)

**Problem:** Measurements are at discrete GPS points, need continuous map

**Solution:** Cubic interpolation using Delaunay triangulation

```python
from scipy.interpolate import griddata

# Input: Scattered points
lons = [80.156, 80.157, 80.158, ...]  # Longitude
lats = [12.843, 12.844, 12.845, ...]  # Latitude
signals = [-55, -60, -58, ...]         # Signal strength

# Create regular grid
grid_lon, grid_lat = np.meshgrid(
    np.linspace(lon_min, lon_max, 100),
    np.linspace(lat_min, lat_max, 100)
)

# Interpolate
grid_signal = griddata(
    points=(lons, lats),
    values=signals,
    xi=(grid_lon, grid_lat),
    method='cubic'  # Smooth interpolation
)

# Result: 100×100 grid of interpolated signal values
```

---

## 5. System Operation Modes

### Mode 1: Single Scan

**Use Case:** Measure signal at current fixed location

**Process:**
```
1. Initialize RTL-SDR and GPS
2. Get current GPS position (once)
3. Scan frequency range (1.5 seconds)
4. Log measurements with GPS tag
5. Export to CSV, JSON, KML
6. Shutdown
```

**Output:** 4,097 measurements at one GPS location

### Mode 2: Continuous Scan

**Use Case:** Mapping while moving (drone, car, walking)

**Process:**
```
LOOP:
    1. Get current GPS position
    2. Scan frequency range
    3. Log measurements with new GPS
    4. Wait for interval (e.g., 10 seconds)
    5. Repeat until stopped (Ctrl+C)

POST-PROCESSING:
    - Generate heatmap (multiple GPS points)
    - Create coverage map
    - Export all data
```

**Output:** Multiple GPS-tagged scan sessions, spatial heatmaps

---

## 6. Control Flow - Detailed

### Main Program Flow

```
START
  ↓
Parse arguments (--mode, --interval)
  ↓
Load config.yaml
  ↓
Setup logging
  ↓
Initialize components:
  ├── RTLScannerCLI
  ├── GPS Reader
  └── Data Logger
  ↓
IF mode == "single":
  ├── Get GPS position
  ├── Scan frequencies
  ├── Log data
  └── Export (CSV, JSON, KML)
  ↓
ELSE IF mode == "continuous":
  ├── LOOP:
  │   ├── Get GPS position
  │   ├── Scan frequencies
  │   ├── Log data
  │   ├── Sleep(interval)
  │   └── Repeat
  ├── Generate heatmaps
  └── Export all data
  ↓
Cleanup (close SDR, GPS)
  ↓
END
```

### Scanner Initialization

```
RTLScannerCLI.initialize()
  ↓
Find rtl_power executable:
  1. Check: C:\...\rtlsdr-bin-w64_static\rtl_power.exe
  2. Check: System PATH
  3. Check: /usr/bin/rtl_power (Linux)
  ↓
Test RTL-SDR device:
  Run: rtl_test -t
  Check output for "Found X device(s)"
  ↓
IF device found:
  Return TRUE
ELSE:
  Log error, Return FALSE
```

### Frequency Scanning

```
scan_frequency_range(start_hz, end_hz, integration_time)
  ↓
Create temp CSV file
  ↓
Build rtl_power command:
  rtl_power -f START:END:STEP -i TIME -1 output.csv
  ↓
Execute subprocess:
  subprocess.run(cmd, timeout=TIME+10)
  ↓
Parse CSV output:
  Read line: "date,time,hz_low,hz_high,hz_step,samples,dB,dB,..."
  Extract: hz_low, hz_high, power_values[]
  ↓
Generate frequency array:
  frequencies = linspace(hz_low, hz_high, len(power_values))
  ↓
Handle invalid values:
  FOR each power value:
    TRY: convert to float
    EXCEPT: use -999.0 (invalid marker)
  ↓
Return: (frequencies[], powers[])
```

### GPS Position Reading

```
gps_reader.read_position(timeout)
  ↓
IF platform == Windows:
  ├── Execute PowerShell script
  ├── Parse JSON output
  └── Return GPSCoordinate(lat, lon, alt=None)
  ↓
ELSE (Linux/Pi):
  ├── Read serial port
  ├── Parse NMEA sentence ($GPGGA)
  └── Return GPSCoordinate(lat, lon, alt)
  ↓
IF timeout or error:
  Return None
```

### Data Export

```
Export Process:
  ↓
CSV Export:
  ├── Open: data/signal_data_TIMESTAMP.csv
  ├── Write header row
  ├── FOR each measurement:
  │   └── Write: timestamp,lat,lon,alt,band,freq,signal
  └── Close file
  ↓
JSON Export:
  ├── Convert measurements to JSON array
  └── Save: data/signal_data_TIMESTAMP.json
  ↓
KML Export:
  ├── Create KML document
  ├── FOR each band:
  │   ├── Create folder
  │   └── FOR each measurement:
  │       ├── Create placemark at (lon, lat, alt)
  │       ├── Set color based on signal strength
  │       └── Add description
  └── Save: output/signal_map.kml
```

---

## 7. Technical Specifications

### RTL-SDR Hardware

| Parameter | Value |
|-----------|-------|
| Frequency Range | 24 MHz - 1.766 GHz |
| ADC Resolution | 8-bit |
| Sample Rate | 2.048 MSPS |
| Tuner | Rafael Micro R828D |
| Interface | USB 2.0 |
| Gain Range | 0 - 50 dB |

### LTE Band Coverage (India)

| Band | Downlink Frequency | Scannable? |
|------|-------------------|------------|
| Band 5 | 869-894 MHz | ✅ Yes |
| Band 8 | 925-960 MHz | ✅ Yes |
| Band 3 | 1805-1880 MHz | ⚠️ Partial (up to 1766 MHz) |
| Band 40 | 2300-2400 MHz | ❌ No (above range) |

### Scan Performance

| Metric | Value |
|--------|-------|
| Frequency Resolution | 1 kHz |
| Samples per Band | 4,097 |
| Scan Time (Band 5) | 1.5 seconds |
| GPS Acquisition | 1-5 seconds |
| Data Points per Scan | 4,097 |

---

## 8. Error Handling

### RTL-SDR Errors

```python
try:
    scanner.initialize()
except Exception as e:
    if "not found" in str(e):
        log("RTL-SDR device not detected")
    elif "permission" in str(e):
        log("USB permission denied")
    else:
        log(f"Unknown error: {e}")
    exit(1)
```

### GPS Errors

```python
coord = gps_reader.read_position(timeout=30)

if coord is None:
    log("GPS timeout - proceeding without location")
    lat, lon, alt = None, None, None
else:
    lat, lon, alt = coord.latitude, coord.longitude, coord.altitude
```

### Signal Processing Errors

```python
# Handle NaN values from rtl_power
for value in power_values:
    try:
        power = float(value)
        if not (power == power):  # Check for NaN
            power = -999.0
    except ValueError:
        power = -999.0  # Invalid marker

    cleaned_values.append(power)
```

---

## 9. Configuration

### config.yaml Structure

```yaml
# RTL-SDR Settings
rtl_sdr:
  device_index: 0
  sample_rate: 2048000  # 2.048 MHz
  gain: 40              # dB

# LTE Bands
bands:
  band_5:
    enabled: true
    downlink_start: 869000000  # Hz
    downlink_end: 894000000    # Hz

# Scanning
scan:
  integration_time: 1.0  # seconds

# GPS
gps:
  enabled: true
  port: "/dev/ttyUSB0"   # Serial port (Pi)
  baud_rate: 9600

# Export
export:
  csv_enabled: true
  json_enabled: true
  kml_enabled: true
```

---

## 10. Output Formats

### CSV Format
```
timestamp,latitude,longitude,altitude,band,frequency_hz,frequency_mhz,signal_dbm
2025-10-03 00:01:07,12.843346,80.156625,0,band_5,869000000,869.0,-56.2
2025-10-03 00:01:07,12.843346,80.156625,0,band_5,869001000,869.001,-55.8
...
```

### JSON Format
```json
[
  {
    "timestamp": "2025-10-03 00:01:07",
    "latitude": 12.843346,
    "longitude": 80.156625,
    "altitude": 0,
    "band": "band_5",
    "frequency_hz": 869000000,
    "frequency_mhz": 869.0,
    "signal_dbm": -56.2
  },
  ...
]
```

### KML Format (Google Earth)
```xml
<kml>
  <Document>
    <Placemark>
      <name>-56.2 dBm</name>
      <Point>
        <coordinates>80.156625,12.843346,0</coordinates>
      </Point>
      <Style>
        <IconStyle>
          <color>ff00ffff</color>
        </IconStyle>
      </Style>
    </Placemark>
  </Document>
</kml>
```

---

## 11. Platform Compatibility

### Windows (Testing)
- GPS: Windows Location Services (WiFi-based)
- RTL-SDR: USB drivers via Zadig (WinUSB)
- Python: Anaconda distribution

### Linux/Raspberry Pi (Production)
- GPS: Serial GPS module (UART/USB)
- RTL-SDR: Native librtlsdr
- Python: System Python 3.x

### Code Portability
```python
import platform

if platform.system() == 'Windows':
    gps_reader = WindowsGPSReader(config)
else:
    gps_reader = GPSReader(config)  # Serial GPS
```

---

This technical overview covers all implementation details without business aspects. Use this to explain how the system actually works.
