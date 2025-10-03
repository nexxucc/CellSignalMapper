# Cell Signal Mapper - Control Flow Documentation

This document explains exactly what happens when you run the system, step by step.

---

## 1. Program Entry Point

### Command Line
```bash
python src/main.py --mode single
# OR
python src/main.py --mode continuous --interval 10
```

### What Happens First (main.py)

```
START
  ↓
Parse command line arguments
  • --mode: "single" or "continuous"
  • --interval: seconds between scans (continuous mode only)
  • --mock-gps: use fake GPS for testing
  • --config: path to config file (default: config/config.yaml)
  ↓
Load configuration file (config.yaml)
  • RTL-SDR settings (gain, sample rate)
  • LTE bands to scan
  • GPS settings
  • Export options (CSV, JSON, KML)
  ↓
Setup logging system
  • Console output (INFO level)
  • File logging (logs/signal_mapper_TIMESTAMP.log)
  ↓
Detect platform (Windows or Linux)
  ↓
Branch to selected mode:
  • single_scan_mode()  ←
  • continuous_scan_mode()
```

---

## 2. Single Scan Mode - Detailed Flow

```
SINGLE SCAN MODE
  ↓
┌─────────────────────────────────────┐
│ STEP 1: Initialize Components      │
└─────────────────────────────────────┘
  ↓
Create Scanner (RTLScannerCLI)
  • Load config settings
  • Find rtl_power executable
  • Store rtl_power path
  ↓
Create GPS Reader (platform-dependent)
  IF Windows:
    • WindowsGPSReader (uses WiFi location)
  ELSE:
    • GPSReader (uses serial GPS module)
  ↓
Create DataLogger
  • Setup data directory (data/)
  • Initialize empty measurement list
  ↓
┌─────────────────────────────────────┐
│ STEP 2: Initialize RTL-SDR         │
└─────────────────────────────────────┘
  ↓
scanner.initialize()
  ↓
  Find rtl_power.exe in known locations:
    1. C:\Users\...\Downloads\rtlsdr-bin-w64_static\rtl_power.exe
    2. System PATH
    3. /usr/bin/rtl_power (Linux)
  ↓
  Test RTL-SDR device with rtl_test.exe
    • Run: rtl_test -t
    • Check output for "Found X device(s)"
    • If found → SUCCESS
    • If not found → ERROR, exit
  ↓
Scanner ready ✓
  ↓
┌─────────────────────────────────────┐
│ STEP 3: Get GPS Position            │
└─────────────────────────────────────┘
  ↓
gps_reader.connect()
  ↓
  IF Windows:
    • Connect to Windows Location API
    • Request location permission
  ELSE:
    • Open serial port (e.g., /dev/ttyUSB0)
    • Set baud rate (9600)
    • Initialize NMEA parser
  ↓
gps_reader.wait_for_fix(timeout=30)
  ↓
  WHILE (no fix AND timeout not reached):
    • Read GPS data
    • Parse NMEA sentences ($GPGGA, $GPRMC)
    • Check satellite count
    • Extract lat, lon, alt
  ↓
  IF fix acquired:
    • Store GPSCoordinate object
    • latitude, longitude, altitude, num_satellites
  ELSE:
    • Warn user (no GPS)
    • latitude = None, longitude = None
  ↓
GPS position obtained (or None) ✓
  ↓
┌─────────────────────────────────────┐
│ STEP 4: Scan LTE Bands              │
└─────────────────────────────────────┘
  ↓
scanner.scan_lte_bands(config['bands'])
  ↓
  FOR EACH band in bands:
    ↓
    IF band['enabled'] == False:
      • Skip this band
      • Continue to next
    ↓
    Get frequency range:
      • start_freq = band['downlink_start']  (e.g., 869000000 Hz)
      • end_freq = band['downlink_end']      (e.g., 894000000 Hz)
    ↓
    ┌─────────────────────────────────────┐
    │ Sub-process: Scan Frequency Range   │
    └─────────────────────────────────────┘
      ↓
      Create temporary CSV file (for rtl_power output)
      ↓
      Build rtl_power command:
        rtl_power \
          -f 869M:894M:1k \     # Frequency: start:end:step
          -i 1 \                # Integration: 1 second
          -1 \                  # Single scan
          -d 0 \                # Device index
          -g 40 \               # Gain
          output.csv
      ↓
      Execute command (subprocess.run)
        • Wait for completion (1-2 seconds)
        • Capture stdout/stderr
      ↓
      Parse output CSV:
        Line format: date,time,Hz_low,Hz_high,Hz_step,samples,dB,dB,dB,...
        ↓
        Extract metadata:
          • hz_low, hz_high, hz_step
        ↓
        Extract power values (dB measurements):
          FOR EACH value in line[6:]:
            TRY:
              • Convert to float
              • If NaN or invalid → -999.0
            EXCEPT:
              • Use -999.0 (no signal)
        ↓
        Generate frequency array:
          frequencies = linspace(hz_low, hz_high, num_samples)
        ↓
        RETURN (frequencies, powers)
      ↓
    Calculate statistics:
      • avg_power = mean(powers)
      • max_power = max(powers)
      • peak_freq = frequencies[argmax(powers)]
      • num_samples = len(frequencies)
    ↓
    Store results:
      results[band_name] = {
        'average_power_dbm': avg_power,
        'max_power_dbm': max_power,
        'frequency_mhz': peak_freq / 1e6,
        'num_samples': num_samples,
        'raw_data': [(freq, power), ...]  # All measurements
      }
    ↓
  END FOR
  ↓
  RETURN all band results
  ↓
Scan complete ✓
  ↓
┌─────────────────────────────────────┐
│ STEP 5: Log Measurements            │
└─────────────────────────────────────┘
  ↓
data_logger.log_scan_results(lat, lon, alt, scan_results, timestamp)
  ↓
  FOR EACH band in scan_results:
    ↓
    Extract raw_data from band results
    ↓
    FOR EACH (frequency, power) in raw_data:
      ↓
      Create measurement entry:
        {
          'timestamp': '2025-10-02 22:26:09',
          'latitude': 12.843346,
          'longitude': 80.156625,
          'altitude': None,
          'band': 'band_5',
          'frequency_hz': 869500000,
          'frequency_mhz': 869.5,
          'signal_dbm': -55.2
        }
      ↓
      Append to logger.measurements list
    ↓
  END FOR
  ↓
Measurements logged (e.g., 4097 entries) ✓
  ↓
┌─────────────────────────────────────┐
│ STEP 6: Display Results             │
└─────────────────────────────────────┘
  ↓
Print to console:
  === Scan Results ===
  band_5:
    Average Power: -55.10 dBm
    Max Power: -45.43 dBm at 870.51 MHz
    Scanned 4097 frequency points
  ↓
┌─────────────────────────────────────┐
│ STEP 7: Export Data                 │
└─────────────────────────────────────┘
  ↓
IF config['export']['csv_enabled']:
  ↓
  data_logger.save_to_csv()
    ↓
    Create filename: signal_data_YYYYMMDD_HHMMSS.csv
    ↓
    Write header: timestamp,latitude,longitude,altitude,band,frequency_hz,frequency_mhz,signal_dbm
    ↓
    FOR EACH measurement:
      • Write CSV row
    ↓
    Save to: data/signal_data_20251002_222606.csv
  ↓
  CSV saved ✓
  ↓
IF config['export']['json_enabled']:
  ↓
  data_logger.save_to_json()
    ↓
    Create filename: signal_data_YYYYMMDD_HHMMSS.json
    ↓
    Convert measurements to JSON array
    ↓
    Save to: data/signal_data_20251002_222606.json
  ↓
  JSON saved ✓
  ↓
IF config['export']['kml_enabled']:
  ↓
  Create KMLExporter
  ↓
  Get DataFrame from logger
  ↓
  kml_exporter.export_to_kml(df)
    ↓
    Create KML document
    ↓
    FOR EACH band:
      • Create folder for band
      ↓
      FOR EACH measurement:
        ↓
        Create placemark:
          • Name: signal strength (e.g., "-55.2 dBm")
          • Coordinates: (lon, lat, alt)
          • Description: HTML with details
          • Icon color: based on signal strength
            - Strong (> -60): Green
            - Medium (-60 to -80): Yellow
            - Weak (< -80): Red
      ↓
    Save to: output/signal_map.kml
  ↓
  KML saved ✓
  ↓
┌─────────────────────────────────────┐
│ STEP 8: Cleanup                     │
└─────────────────────────────────────┘
  ↓
scanner.close()
  • Set is_initialized = False
  ↓
gps_reader.disconnect()
  • Close serial port (Linux)
  • Stop Windows location service
  ↓
Print: === Single Scan Complete ===
  ↓
END
```

---

## 3. Continuous Scan Mode - Detailed Flow

```
CONTINUOUS SCAN MODE
  ↓
Initialize components (same as single mode)
  • Scanner
  • GPS Reader
  • Data Logger
  ↓
┌─────────────────────────────────────┐
│ Main Scanning Loop                  │
└─────────────────────────────────────┘
  ↓
scan_count = 0
  ↓
WHILE True:
  ↓
  scan_count += 1
  ↓
  Print: "Scan #X at HH:MM:SS"
  ↓
  Get current GPS position
    • gps_reader.read_position()
    • May be different from last scan (drone moving)
  ↓
  Perform frequency scan
    • scanner.scan_lte_bands(config['bands'])
    • Same as single mode
  ↓
  Log measurements with timestamp & GPS
    • data_logger.log_scan_results(...)
  ↓
  Display quick summary:
    band_5: Avg=-55.2 dBm, Max=-45.1 dBm
    Total measurements: 12,291 (3 scans × 4,097)
  ↓
  Wait for interval:
    • sleep(interval seconds)  # e.g., 10 seconds
  ↓
  IF Ctrl+C pressed:
    • BREAK loop
  ↓
END WHILE
  ↓
┌─────────────────────────────────────┐
│ Post-Processing (after stopping)    │
└─────────────────────────────────────┘
  ↓
Save data (CSV, JSON, KML)
  • Same as single mode
  ↓
IF multiple unique GPS locations:
  ↓
  Generate heatmaps:
    ↓
    heatmap_gen.generate_all_heatmaps(df)
      ↓
      FOR EACH band:
        ↓
        Extract GPS coordinates and signal strength
        ↓
        Create interpolated grid (100×100 points)
          • Use scipy.griddata (cubic interpolation)
        ↓
        Plot contour heatmap:
          • X-axis: Longitude
          • Y-axis: Latitude
          • Color: Signal strength (dBm)
          • Overlay: Measurement points
        ↓
        Save: output/heatmap_band_5.png
      ↓
    ↓
    heatmap_gen.generate_signal_distribution_plot(df)
      • Histogram of signal strengths
      • Box plot by band
      • Save: output/signal_distribution.png
    ↓
    heatmap_gen.generate_coverage_map(df, threshold=-80)
      • Good signal (>= -80 dBm): Green circles
      • Weak signal (< -80 dBm): Red X marks
      • Save: output/coverage_map.png
    ↓
  Heatmaps generated ✓
  ↓
Print: === Continuous scan stopped ===
Print: Collected X scans, Y total measurements
  ↓
Cleanup and exit
  ↓
END
```

---

## 4. Key Functions - Internal Details

### scanner.scan_frequency_range()

**Purpose:** Scan a specific frequency range and return power measurements

```python
def scan_frequency_range(start_freq_hz, end_freq_hz, integration_time):

    # Create temporary file for rtl_power output
    tmp_file = tempfile.NamedTemporaryFile(suffix='.csv')

    # Calculate parameters
    start_mhz = start_freq_hz / 1e6  # Convert Hz to MHz
    end_mhz = end_freq_hz / 1e6

    # Build rtl_power command
    cmd = [
        rtl_power_path,
        "-f", f"{start_mhz}M:{end_mhz}M:1k",  # Freq range with 1kHz steps
        "-i", str(integration_time),          # Integration time (seconds)
        "-1",                                 # Single scan flag
        "-d", str(device_index),              # RTL-SDR device ID
        "-g", str(gain),                      # Gain setting
        tmp_file.name                         # Output CSV path
    ]

    # Execute rtl_power
    result = subprocess.run(cmd, capture_output=True, timeout=integration_time+10)

    # Parse CSV output
    with open(tmp_file.name) as f:
        line = f.readline()

    parts = line.split(',')
    hz_low = float(parts[2])
    hz_high = float(parts[3])
    power_values = [safe_float(x) for x in parts[6:]]  # Handle NaN

    # Generate frequency array
    frequencies = np.linspace(hz_low, hz_high, len(power_values))
    powers = np.array(power_values)

    return (frequencies, powers)
```

**What happens inside rtl_power:**
1. Tunes RTL-SDR to start frequency
2. Captures IQ samples (In-phase/Quadrature)
3. Computes FFT → frequency spectrum
4. Converts to power: P(dBm) = 10 * log10(|FFT|²)
5. Steps to next frequency, repeats
6. Writes all power values to CSV

---

### gps_reader.read_position() - Windows

**Purpose:** Get current GPS coordinates from Windows Location Services

```python
def read_position(timeout=10):

    # PowerShell script to access Windows Location API
    ps_script = '''
    Add-Type -AssemblyName System.Device
    $watcher = New-Object System.Device.Location.GeoCoordinateWatcher
    $watcher.Start()

    # Wait for location fix (max 30 seconds)
    $timeout = 30
    $counter = 0
    while (($watcher.Status -ne 'Ready') -and ($counter -lt $timeout)) {
        Start-Sleep -Milliseconds 100
        $counter += 0.1
    }

    # Get coordinates
    if ($watcher.Status -eq 'Ready') {
        $coord = $watcher.Position.Location
        @{
            latitude = $coord.Latitude
            longitude = $coord.Longitude
            altitude = $coord.Altitude
        } | ConvertTo-Json
    }

    $watcher.Stop()
    '''

    # Run PowerShell
    result = subprocess.run(['powershell', '-Command', ps_script],
                          capture_output=True, timeout=timeout)

    # Parse JSON output
    data = json.loads(result.stdout)

    # Create GPSCoordinate object
    coord = GPSCoordinate(
        latitude=data['latitude'],
        longitude=data['longitude'],
        altitude=data['altitude'] if valid else None,
        num_satellites=8,  # Windows doesn't provide this
        timestamp=datetime.now()
    )

    return coord
```

**How Windows Location works:**
1. Uses WiFi access points nearby
2. Compares to Microsoft's location database
3. Triangulates approximate position
4. Typically accurate to ±10-50 meters
5. No altitude (or unreliable)

---

### data_logger.save_to_csv()

**Purpose:** Export all measurements to CSV file

```python
def save_to_csv(filename=None):

    # Auto-generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"signal_data_{timestamp}.csv"

    output_path = Path('data') / filename

    # Write CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'timestamp',
            'latitude',
            'longitude',
            'altitude',
            'band',
            'frequency_hz',
            'frequency_mhz',
            'signal_dbm'
        ])

        writer.writeheader()

        for measurement in self.measurements:
            writer.writerow(measurement)

    return output_path
```

**CSV Format:**
```
timestamp,latitude,longitude,altitude,band,frequency_hz,frequency_mhz,signal_dbm
2025-10-02 22:26:09,12.843346,80.156625,,band_5,869000000,869.0,-56.2
2025-10-02 22:26:09,12.843346,80.156625,,band_5,869001000,869.001,-55.8
...
```

---

### kml_exporter.export_to_kml()

**Purpose:** Create Google Earth KML file with 3D visualization

```python
def export_to_kml(df, output_filename='signal_map.kml'):

    # Create KML document
    kml = simplekml.Kml()

    # Group by band
    for band_name in df['band'].unique():

        # Create folder for this band
        folder = kml.newfolder(name=band_name)

        # Get band data
        band_data = df[df['band'] == band_name]

        # Create placemark for each measurement
        for idx, row in band_data.iterrows():

            lat = row['latitude']
            lon = row['longitude']
            alt = row['altitude'] if row['altitude'] else 0
            signal = row['signal_dbm']
            freq = row['frequency_mhz']

            # Create point
            pnt = folder.newpoint()
            pnt.coords = [(lon, lat, alt)]  # KML uses lon,lat order!

            # Name (shown on map)
            pnt.name = f"{signal:.1f} dBm"

            # Description (popup when clicked)
            pnt.description = f"""
            <b>Signal:</b> {signal:.2f} dBm<br/>
            <b>Frequency:</b> {freq:.2f} MHz<br/>
            <b>Location:</b> {lat:.6f}, {lon:.6f}<br/>
            <b>Altitude:</b> {alt:.0f} m
            """

            # Color based on signal strength
            if signal > -60:
                color = 'ff00ff00'  # Green (strong)
            elif signal > -80:
                color = 'ff00ffff'  # Yellow (medium)
            else:
                color = 'ff0000ff'  # Red (weak)

            pnt.style.iconstyle.color = color
            pnt.style.iconstyle.scale = 0.8

    # Save KML
    output_path = Path('output') / output_filename
    kml.save(str(output_path))

    return output_path
```

**KML Structure:**
```xml
<kml>
  <Document>
    <Folder name="band_5">
      <Placemark>
        <name>-55.2 dBm</name>
        <Point>
          <coordinates>80.156625,12.843346,0</coordinates>
        </Point>
        <Style>
          <IconStyle>
            <color>ff00ffff</color>  <!-- Yellow -->
          </IconStyle>
        </Style>
      </Placemark>
      ...
    </Folder>
  </Document>
</kml>
```

---

## 5. Data Flow Summary

```
User Command
    ↓
main.py (entry point)
    ↓
    ├→ Load config.yaml
    ├→ Setup logging
    └→ Route to mode
        ↓
    ┌───────────────┐
    │  Single Scan  │
    └───────────────┘
        ↓
    ┌─────────────────────────────────┐
    │ Initialize Components           │
    ├─────────────────────────────────┤
    │ • RTLScannerCLI                 │
    │   └→ Find rtl_power.exe         │
    │   └→ Test RTL-SDR device        │
    │                                 │
    │ • GPSReader (platform-specific) │
    │   └→ Windows: Location Services │
    │   └→ Linux: Serial GPS          │
    │                                 │
    │ • DataLogger                    │
    │   └→ Create data directory      │
    └─────────────────────────────────┘
        ↓
    ┌─────────────────────────────────┐
    │ Get GPS Position                │
    ├─────────────────────────────────┤
    │ Input: None                     │
    │ Process: Read GPS module        │
    │ Output: GPSCoordinate           │
    │   • latitude: 12.843346         │
    │   • longitude: 80.156625        │
    │   • altitude: None              │
    └─────────────────────────────────┘
        ↓
    ┌─────────────────────────────────┐
    │ Scan LTE Bands                  │
    ├─────────────────────────────────┤
    │ Input: config['bands']          │
    │                                 │
    │ For band_5:                     │
    │   scan_frequency_range(         │
    │     869 MHz → 894 MHz,          │
    │     1 second integration         │
    │   )                             │
    │   ↓                             │
    │   rtl_power execution           │
    │   ↓                             │
    │   Parse CSV output              │
    │   ↓                             │
    │   Return:                       │
    │     frequencies[4097]           │
    │     powers[4097]                │
    │                                 │
    │ Calculate stats:                │
    │   • avg_power = -55.10 dBm      │
    │   • max_power = -45.43 dBm      │
    │   • peak_freq = 870.51 MHz      │
    └─────────────────────────────────┘
        ↓
    ┌─────────────────────────────────┐
    │ Log Measurements                │
    ├─────────────────────────────────┤
    │ For each (freq, power):         │
    │   Create entry:                 │
    │     {                           │
    │       timestamp,                │
    │       lat, lon, alt,            │
    │       band,                     │
    │       frequency,                │
    │       signal_dbm                │
    │     }                           │
    │                                 │
    │ Store in memory: 4097 entries   │
    └─────────────────────────────────┘
        ↓
    ┌─────────────────────────────────┐
    │ Export Data                     │
    ├─────────────────────────────────┤
    │ • CSV: data/signal_data.csv     │
    │   → 4097 rows                   │
    │                                 │
    │ • JSON: data/signal_data.json   │
    │   → Structured array            │
    │                                 │
    │ • KML: output/signal_map.kml    │
    │   → Google Earth format         │
    │   → Color-coded placemarks      │
    └─────────────────────────────────┘
        ↓
    Cleanup & Exit
```

---

## 6. Error Handling Flow

```
Any Step
    ↓
  TRY:
    Execute operation
    ↓
  EXCEPT Exception as e:
    ↓
    Log error: logger.error(f"Error: {e}")
    ↓
    Check error type:
    ├→ RTL-SDR not found
    │   └→ Log: "RTL-SDR device not detected"
    │   └→ Exit gracefully
    │
    ├→ GPS timeout
    │   └→ Warn: "No GPS fix available"
    │   └→ Continue with lat=None, lon=None
    │
    ├→ Invalid frequency in config
    │   └→ Catch ValueError
    │   └→ Skip this band, continue
    │
    ├→ rtl_power returns NaN
    │   └→ Convert to -999.0
    │   └→ Continue processing
    │
    └→ File I/O error
        └→ Log error
        └→ Try alternative path
        └→ If fails, exit

  FINALLY:
    ↓
    Close all resources:
    • scanner.close()
    • gps_reader.disconnect()
    • Save any buffered data
```

---

## 7. Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Scanner initialization | 1-2 sec | Find rtl_power, test device |
| GPS acquisition | 1-5 sec | Windows: instant, Serial: up to 30s |
| Frequency scan (Band 5) | 1.5 sec | 25 MHz range, 4097 samples |
| Data logging | <0.1 sec | In-memory append |
| CSV export | 0.5 sec | 4097 rows write |
| JSON export | 0.3 sec | Serialization |
| KML export | 2 sec | 4097 placemarks generation |
| **Total (single scan)** | **~6 sec** | From start to KML ready |

---

This control flow documentation provides a complete picture of how your system works internally. Use this to explain the technical details to your professor! 🚀
