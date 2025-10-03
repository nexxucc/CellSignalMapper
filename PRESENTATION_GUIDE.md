# Cell Signal Mapper - Presentation Guide

**Project:** Drone-Based Cellular Network Coverage Mapping System
**Hardware:** RTL-SDR V4, Raspberry Pi 5 (Future), GPS Module
**Software:** Python, Signal Processing, Data Visualization

---

## 1. Project Overview (2 minutes)

### Problem Statement
**"How do we map cellular network coverage in 3D space for analysis and optimization?"**

Traditional methods:
- ❌ Drive testing - slow, only ground level, expensive
- ❌ Crowdsourced data - unreliable, privacy concerns
- ❌ Simulation software - doesn't match real-world conditions

**Our Solution:**
✅ Drone-mounted Software-Defined Radio (SDR) system
✅ Real-time signal measurement at multiple altitudes
✅ GPS-tagged data for precise 3D mapping
✅ Cost-effective (uses $30 RTL-SDR instead of $10k equipment)

---

## 2. Technical Architecture (3 minutes)

### System Components

```
┌─────────────────────────────────────────────────┐
│               CELL SIGNAL MAPPER                │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │   RTL-SDR    │ ───────>│  Raspberry Pi 5 │  │
│  │   Receiver   │   USB   │   (Main Comp.)  │  │
│  └──────────────┘         └─────────────────┘  │
│         ▲                          │           │
│         │                          ▼           │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │  700-2700MHz │         │   GPS Module    │  │
│  │   Antenna    │         │  (Location Tag) │  │
│  └──────────────┘         └─────────────────┘  │
│                                                 │
│         Mounted on Drone                        │
└─────────────────────────────────────────────────┘
```

### Key Technologies

1. **RTL-SDR V4 (Software-Defined Radio)**
   - Frequency Range: 24 MHz - 1.766 GHz
   - Scans: LTE Band 5 (850 MHz) - primary band in India
   - Cost: ₹2,500 vs ₹8,00,000 for professional equipment

2. **Raspberry Pi 5**
   - Controls RTL-SDR via Python
   - Processes signal data in real-time
   - Logs GPS-tagged measurements

3. **GPS Module**
   - Provides latitude, longitude, altitude
   - Syncs with drone telemetry

---

## 3. How It Works - Technical Flow (4 minutes)

### Step-by-Step Process

**Phase 1: Initialization**
```
1. Load config.yaml (frequency bands, scan parameters)
2. Initialize RTL-SDR hardware
3. Connect to GPS module
4. Create data logging system
```

**Phase 2: Signal Scanning**
```
FOR each measurement point:
    1. Get GPS coordinates (lat, lon, altitude)
    2. Scan frequency range (869-894 MHz for Band 5)
       - rtl_power scans in 1kHz steps
       - Integration time: 1 second per scan
       - Outputs: 4,097 frequency samples

    3. Process signal data:
       - Convert raw FFT → Power (dBm)
       - Calculate: Average, Max, Peak frequency
       - Handle errors (NaN → -999 dBm)

    4. Log measurement:
       - Timestamp
       - GPS coordinates
       - Frequency + Signal strength pairs
```

**Phase 3: Data Export**
```
After scanning:
    1. Save CSV (spreadsheet analysis)
    2. Save JSON (structured data)
    3. Generate KML (Google Earth 3D view)
    4. Create visualizations:
       - Signal distribution histogram
       - Coverage map (good/weak zones)
       - Heatmap (if multiple GPS points)
```

### Signal Strength Scale
- **-40 to -60 dBm:** Excellent (near tower)
- **-60 to -80 dBm:** Good (normal service)
- **-80 to -100 dBm:** Fair (edge of coverage)
- **-100 to -120 dBm:** Poor (no service)
- **-999 dBm:** No signal detected

---

## 4. Software Architecture (3 minutes)

### Module Structure

```
CellSignalMapper/
├── config/
│   └── config.yaml          # All settings in one file
│
├── src/
│   ├── main.py              # Entry point
│   │
│   ├── scanner/             # Signal Scanning
│   │   └── rtl_scanner_cli.py  # RTL-SDR interface
│   │
│   ├── gps/                 # GPS/Location
│   │   ├── gps_module.py       # Serial GPS (Raspberry Pi)
│   │   └── windows_gps.py      # Windows Location (testing)
│   │
│   ├── utils/               # Data Management
│   │   └── data_logger.py      # CSV/JSON logging
│   │
│   ├── processor/           # Analysis
│   │   └── heatmap_generator.py  # Visualizations
│   │
│   └── exporter/            # Export Formats
│       └── kml_exporter.py     # Google Earth KML
│
├── data/                    # Output: Raw measurements
├── output/                  # Output: Maps & graphs
└── logs/                    # Debug logs
```

### Design Principles
1. **Modular:** Each component has one responsibility
2. **Platform-agnostic:** Runs on Windows (testing) and Linux (Pi)
3. **Robust:** Handles errors gracefully (never crashes)
4. **Scalable:** Easy to add more frequency bands

---

## 5. Key Algorithms & Techniques (3 minutes)

### 1. Frequency Scanning (rtl_power)
```
Input: Frequency range (869-894 MHz)
Process:
    - Step through in 1kHz increments
    - At each frequency:
        * Capture RF samples (2.048 MSPS)
        * Compute FFT (Fast Fourier Transform)
        * Convert to power: 10 * log10(|FFT|²)
    - Output: Power spectrum (dBm vs Frequency)
```

**Why rtl_power?**
- Efficient: Scans 25 MHz in ~2 seconds
- Accurate: FFT-based spectral analysis
- Standard: Used by SDR community worldwide

### 2. GPS Coordinate Tagging
```python
while scanning:
    position = gps.read_position()

    if position valid:
        lat = position.latitude
        lon = position.longitude
        alt = position.altitude
    else:
        # Use last known position or skip

    log(lat, lon, alt, signal_data, timestamp)
```

### 3. Signal Interpolation (Heatmap)
```
Input: Scattered GPS points with signal strength
Process:
    1. Create regular grid (100x100 points)
    2. Cubic interpolation between measurements
    3. Generate contour map with color gradient
Output: Smooth heatmap visualization
```

**Mathematical basis:** Scipy's `griddata()` uses Delaunay triangulation + cubic interpolation

---

## 6. Real Results & Demo (2 minutes)

### Actual Test Results (Your Data)

**Location:** Chennai, India (12.843°N, 80.156°E)
**Band:** LTE Band 5 (869-894 MHz)
**Hardware:** RTL-SDR Blog V4

**Results:**
- ✅ 4,097 frequency samples per scan
- ✅ Average signal: -55 dBm (good coverage)
- ✅ Peak signal: -45 dBm @ 870.5 MHz (strong tower)
- ✅ Scan time: 1.5 seconds

**Interpretation:**
- Cell tower detected at 870.5 MHz
- Signal strength indicates ~500m-1km from tower
- Band 5 provides indoor penetration (lower frequency)

### Demo Files to Show
1. `data/signal_data_YYYYMMDD.csv` - Raw measurements
2. `output/signal_map.kml` - Open in Google Earth
3. `output/signal_distribution.png` - Histogram
4. `output/coverage_map.png` - Coverage zones

---

## 7. Challenges & Solutions (2 minutes)

### Challenge 1: Hardware Limitations
**Problem:** RTL-SDR V4 only scans 24-1766 MHz
**Impact:** Misses Band 40 (2300 MHz) - India's primary band
**Solution:** Focus on Band 5 (850 MHz) for proof-of-concept
**Future:** Upgrade to HackRF One (up to 6 GHz)

### Challenge 2: Python Library Compatibility
**Problem:** pyrtlsdr DLL loading issues on Windows
**Solution:** Use command-line `rtl_power` via subprocess
**Benefit:** More stable, cross-platform compatible

### Challenge 3: GPS Accuracy
**Problem:** Windows WiFi positioning has no altitude
**Solution:**
- Testing: Use Windows Location Services (lat/lon only)
- Production: External GPS module on Pi (full 3D)

### Challenge 4: Data Volume
**Problem:** 4,097 points per scan = large files
**Solution:**
- Efficient storage (CSV: 500KB, compressed JSON)
- Batch processing for visualization
- Configurable sampling density

---

## 8. Applications & Future Work (2 minutes)

### Current Capabilities
✅ Maps LTE Band 5 coverage in 2D/3D
✅ Identifies cell tower locations
✅ Detects coverage gaps (dead zones)
✅ Generates shareable reports (KML, CSV)

### Potential Applications

1. **Telecom Operators**
   - Validate tower coverage claims
   - Optimize tower placement
   - Troubleshoot customer complaints

2. **Urban Planning**
   - Assess connectivity for new developments
   - Plan smart city infrastructure
   - Ensure emergency service coverage

3. **Research**
   - Study RF propagation in different terrains
   - Analyze interference patterns
   - Validate simulation models

### Future Enhancements

**Phase 2: Hardware Upgrade**
- HackRF One SDR → Full LTE spectrum (2300 MHz)
- Better GPS (RTK) → Centimeter accuracy
- Directional antenna → Identify tower direction

**Phase 3: Advanced Features**
- Real-time dashboard (live mapping)
- Multi-band simultaneous scanning
- Signal quality metrics (SINR, CQI)
- Machine learning for tower identification

**Phase 4: Drone Automation**
- Autonomous flight patterns
- Altitude-layered scanning (10m, 20m, 30m)
- Collision avoidance integration
- Multi-drone swarm coverage

---

## 9. Technical Specifications Summary

| Parameter | Value |
|-----------|-------|
| **Frequency Range** | 24 MHz - 1.766 GHz |
| **Current Band** | LTE Band 5 (869-894 MHz) |
| **Scan Resolution** | 1 kHz steps (4,097 points) |
| **Scan Time** | 1.5 seconds per band |
| **GPS Accuracy** | ±3-5 meters (standard GPS) |
| **Data Rate** | ~500 KB per scan |
| **Power Consumption** | ~2.5W (Pi 5 + RTL-SDR) |
| **Cost** | ₹15,000 (vs ₹8,00,000 professional) |

---

## 10. Q&A Preparation

### Expected Questions & Answers

**Q: Why RTL-SDR instead of a phone?**
A: Phones only report connected tower signal. RTL-SDR scans all frequencies independently, detecting even towers you're not connected to. Plus, phones can't measure specific frequencies or operate autonomously on drones.

**Q: How accurate is signal strength measurement?**
A: RTL-SDR has ±2-3 dB accuracy, sufficient for coverage mapping. Professional equipment ($$) has ±0.5 dB but costs 100x more.

**Q: Can this detect 5G?**
A: Current hardware (RTL-SDR V4) only up to 1.766 GHz. 5G uses 3.3-3.6 GHz in India. Need HackRF One (₹30,000) for 5G scanning.

**Q: How does GPS work on a drone?**
A: Raspberry Pi connects to external GPS module via UART/USB. Drone's GPS and our GPS sync to same satellites, giving consistent altitude data.

**Q: What if GPS fails?**
A: System logs measurements with NULL coordinates. Can still analyze signal distribution, just can't map spatially. We also store last-known position as fallback.

**Q: Regulatory concerns about RF scanning?**
A: RTL-SDR is receive-only (no transmission), legal worldwide. Like an FM radio, just more sophisticated. No transmission license needed.

**Q: Drone flight time limitations?**
A: Typical 20-30 min flight. System scans every 10 seconds → 120-180 measurements per flight. For larger areas, multiple flights or battery swaps.

**Q: How to process data for large areas?**
A: Use continuous scan mode. Python pandas handles millions of rows. For visualization, we interpolate between points using scipy.

---

## Presentation Tips

### Structure (15 minutes total)
1. **Problem (1 min):** Why we need better coverage mapping
2. **Solution (1 min):** Drone + SDR approach
3. **Architecture (3 min):** Hardware + Software overview
4. **Technical Details (4 min):** How it works, algorithms
5. **Demo (3 min):** Show actual results, KML visualization
6. **Challenges (2 min):** What we learned, how we solved
7. **Future (1 min):** Applications, next steps

### What to Emphasize
✅ **Cost-effectiveness:** ₹15k vs ₹8L
✅ **Innovation:** Combining drone + SDR + GPS
✅ **Real results:** Working system with actual data
✅ **Scalability:** Easy to extend (more bands, better hardware)
✅ **Practical use:** Telecom operators, urban planning

### What to Keep Simple
- Don't explain FFT math (just say "converts signal to frequency domain")
- Don't dive into GPS protocols (just "provides location")
- Don't explain Python libraries (just "processes data")
- Focus on WHAT it does, not HOW every line of code works

### Visual Aids to Prepare
1. Architecture diagram (draw hardware connections)
2. Control flow diagram (show scanning process)
3. Screenshot of Google Earth KML (3D visualization)
4. Coverage map showing good/weak zones
5. Bar chart comparing cost vs professional equipment

---

## Key Talking Points

**Opening:**
*"Imagine mapping an entire city's cellular coverage from the air in hours, not weeks, using a ₹15,000 drone system instead of ₹8 lakh equipment. That's what we built."*

**Technical Highlight:**
*"Our system scans 4,097 frequency points per second, GPS-tags each measurement, and generates Google Earth visualizations automatically - all running on a Raspberry Pi."*

**Impact:**
*"This technology can help telecom operators optimize coverage, cities plan infrastructure, and researchers validate RF propagation models - democratizing access to expensive spectrum analysis tools."*

**Closing:**
*"We've proven the concept works with real-world data. Next step is deploying on a drone and scaling to cover entire urban areas. The future of coverage mapping is aerial, affordable, and automated."*

---

Good luck with your presentation! 🚀
