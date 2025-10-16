# Raspberry Pi 5 Deployment Guide

**Complete guide to deploy Cell Signal Mapper on Raspberry Pi 5**

---

## Prerequisites

### Hardware Checklist
- ✅ Raspberry Pi 5 (4GB+ RAM recommended)
- ✅ RTL-SDR V4 dongle with antenna
- ✅ GPS module (USB or UART-based)
- ✅ MicroSD card (32GB+ recommended)
- ✅ Power supply for Pi (5V/3A minimum)
- ✅ Internet connection (for setup only)

### What You'll Transfer from Windows
- The entire `CellSignalMapper/` folder
- Your tested configuration in `config/config.yaml`

---

## Part 1: Initial Raspberry Pi Setup

### 1.1 Install Raspberry Pi OS

**On your Windows PC:**
1. Download Raspberry Pi Imager: https://www.raspberrypi.com/software/
2. Flash **Raspberry Pi OS (64-bit)** to SD card
3. Enable SSH during imaging (Settings → Enable SSH)
4. Boot the Pi and connect via SSH or direct connection

### 1.2 Update System

```bash
sudo apt update
sudo apt upgrade -y
```

---

## Part 2: Install RTL-SDR Drivers & Tools

### 2.1 Install System Dependencies

```bash
sudo apt install -y \
    libusb-1.0-0-dev \
    git \
    cmake \
    build-essential \
    rtl-sdr \
    python3-pip \
    python3-venv
```

### 2.2 Blacklist Conflicting Drivers

The DVB-T TV driver conflicts with RTL-SDR. Disable it:

```bash
# Create blacklist file
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl-sdr.conf

# Unload module if currently loaded
sudo rmmod dvb_usb_rtl28xxu 2>/dev/null || true

# Reboot to ensure clean state
sudo reboot
```

### 2.3 Test RTL-SDR Device

After reboot, plug in RTL-SDR and test:

```bash
# Check if device is detected
lsusb | grep Realtek
# Should show: "Realtek Semiconductor Corp. RTL2838 DVB-T"

# Test device functionality
rtl_test -t
# Should show: "Found 1 device(s)" and start testing
# Press Ctrl+C after a few seconds
```

**If device not detected:**
```bash
# Add user to plugdev group for USB access
sudo usermod -a -G plugdev $USER

# Log out and back in, then retry
```

---

## Part 3: Transfer Project Files

### Option A: Using SCP (from Windows)

On Windows (PowerShell or CMD):
```bash
# Transfer entire project folder
scp -r C:\Users\jainv\CellSignalMapper pi@<PI_IP_ADDRESS>:~/
```

### Option B: Using Git (if you have a repo)

On Raspberry Pi:
```bash
cd ~
git clone <your-repo-url>
cd CellSignalMapper
```

### Option C: Using USB Drive

1. Copy `CellSignalMapper/` to USB drive on Windows
2. Plug USB into Pi
3. Mount and copy:
```bash
# Find USB drive
lsblk

# Mount (assuming it's /dev/sda1)
sudo mount /dev/sda1 /mnt

# Copy to home directory
cp -r /mnt/CellSignalMapper ~/

# Unmount
sudo umount /mnt
```

---

## Part 4: Setup Python Environment

### 4.1 Navigate to Project

```bash
cd ~/CellSignalMapper
```

### 4.2 Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# You should see (venv) in your prompt
```

### 4.3 Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Installation takes ~5-10 minutes on Pi 5**

---

## Part 5: Configure GPS Module

### 5.1 GPS Module Hardware Connection

**IMPORTANT:** You are using the **ReadytoSky NEO-M8N GPS** module (round-shaped).

📖 **See `GPS_WIRING_GUIDE.md` for complete wiring instructions with diagrams!**

**Quick Summary:**

**ReadytoSky NEO-M8N (6-pin connector) → Raspberry Pi 5:**
```
GPS Pin 3: VCC (Red)     → Pi Pin 2 or 4: 5V
GPS Pin 6: GND (Black)   → Pi Pin 6: GND
GPS Pin 5: TX (Blue)     → Pi Pin 10: GPIO15 (RX)  ← GPS transmits to Pi
GPS Pin 4: RX (Orange)   → Pi Pin 8: GPIO14 (TX)   ← Pi transmits to GPS

Optional (for compass):
GPS Pin 1: SDA (Green)   → Pi Pin 3: GPIO2 (SDA)
GPS Pin 2: SCL (Yellow)  → Pi Pin 5: GPIO3 (SCL)
```

**Enable UART:**
```bash
sudo raspi-config
# Interface Options → Serial Port
# "Would you like a login shell accessible over serial?" → No
# "Would you like the serial port hardware enabled?" → Yes
# Exit and reboot

sudo reboot
```

**After reboot, verify:**
```bash
ls -l /dev/serial0
# Should show: /dev/serial0 -> ttyAMA0
```

### 5.2 Test GPS Connection

**IMPORTANT:** NEO-M8N uses **38400 baud** (NOT 9600!)

```bash
# Set correct baud rate for NEO-M8N
stty -F /dev/serial0 38400

# Read raw GPS data (Ctrl+C to stop)
# Go OUTSIDE for this test - GPS needs clear sky view!
cat /dev/serial0

# You should see NMEA sentences like:
# $GPGGA,143005,1250.6008,N,08009.3975,E,1,08,0.9,10.0,M,46.9,M,,*47
# $GPRMC,143005,A,1250.6008,N,08009.3975,E,0.0,0.0,030325,,,A*6B
```

**LED Indicators on NEO-M8N:**
- 🔴 Red LED ON = Module has power (always on)
- 🔵 Blue LED blinking = GPS fix acquired (only after 1-2 min outside)

**If no output:**
```bash
# 1. Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in

# 2. Check UART is enabled
ls -l /dev/serial0
# Should exist and point to ttyAMA0

# 3. Verify baud rate (NEO-M8N uses 38400!)
stty -F /dev/serial0 38400

# 4. Go OUTSIDE (GPS cannot work indoors)
# 5. Wait 2-5 minutes for initial fix (cold start)
```

### 5.3 Update Configuration

Edit `config/config.yaml`:
```bash
nano config/config.yaml
```

**For NEO-M8N GPS, verify these settings:**
```yaml
gps:
  enabled: true
  port: "/dev/serial0"  # For GPIO UART connection
  baud_rate: 38400      # NEO-M8N uses 38400, NOT 9600!
  min_satellites: 4
```

**Note:** The config file is already set correctly for NEO-M8N. Just verify the values.

Save with `Ctrl+O`, exit with `Ctrl+X`.

---

## Part 6: Verify rtl_power Path

The scanner automatically finds `rtl_power` on Linux, but verify:

```bash
which rtl_power
# Should output: /usr/bin/rtl_power
```

If not found:
```bash
sudo apt install rtl-sdr
```

---

## Part 7: Test the System

### 7.1 Test RTL-SDR from Project

```bash
cd ~/CellSignalMapper
source venv/bin/activate

# Test RTL-SDR detection
rtl_test -t
```

### 7.2 Test GPS (Optional Mock Mode)

```bash
cd src
python3 main.py --mode single --mock-gps
```

This tests everything except real GPS.

### 7.3 Full System Test (Real GPS + RTL-SDR)

**IMPORTANT: Go outside or near window for GPS fix**

```bash
cd ~/CellSignalMapper/src
source ../venv/bin/activate

python3 main.py --mode single
```

Expected output:
```
INFO - Cell Signal Mapper initialized
INFO - GPS connected on /dev/ttyUSB0
INFO - Waiting for GPS fix...
INFO - GPS fix acquired: GPSCoordinate(lat=XX.XXXX, lon=YY.YYYY, alt=ZZm, sats=8)
INFO - Starting signal scan...
INFO - Scanning band_5...
INFO - band_5: Avg=-55.20 dBm, Max=-45.30 dBm
INFO - === Scan Results ===
```

---

## Part 8: Run Full Scans

### Single Scan (Stationary Test)

```bash
cd ~/CellSignalMapper/src
source ../venv/bin/activate

python3 main.py --mode single
```

**Output files:**
- `data/signal_data_YYYYMMDD_HHMMSS.csv`
- `data/signal_data_YYYYMMDD_HHMMSS.json`
- `output/signal_map.kml`

### Continuous Scan (Drone Flight)

```bash
python3 main.py --mode continuous --interval 10
```

**Workflow:**
1. Start script on ground
2. Wait for GPS fix
3. Launch drone
4. Let scanner run during flight
5. Land drone
6. Press `Ctrl+C` to stop and generate all outputs

---

## Part 9: Retrieve Results

### Option A: SCP to Windows

On Windows:
```bash
scp -r pi@<PI_IP>:~/CellSignalMapper/data ./
scp -r pi@<PI_IP>:~/CellSignalMapper/output ./
```

### Option B: USB Drive

On Pi:
```bash
# Mount USB
sudo mount /dev/sda1 /mnt

# Copy results
cp -r ~/CellSignalMapper/data /mnt/
cp -r ~/CellSignalMapper/output /mnt/

# Unmount
sudo umount /mnt
```

### Option C: View on Pi (if you have GUI)

```bash
# Install image viewer
sudo apt install feh

# View heatmaps
feh ~/CellSignalMapper/output/coverage_map.png
```

---

## Part 10: Autostart (Optional)

To run scanner automatically on boot:

### Create systemd service

```bash
sudo nano /etc/systemd/system/signal-mapper.service
```

Paste:
```ini
[Unit]
Description=Cell Signal Mapper
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/CellSignalMapper/src
ExecStart=/home/pi/CellSignalMapper/venv/bin/python3 main.py --mode continuous --interval 10
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable signal-mapper.service
sudo systemctl start signal-mapper.service

# Check status
sudo systemctl status signal-mapper.service

# View logs
sudo journalctl -u signal-mapper.service -f
```

---

## Troubleshooting

### RTL-SDR Not Detected

**Error:** "No RTL-SDR device found"

```bash
# Check USB connection
lsusb | grep Realtek

# Check if driver loaded
lsmod | grep rtl

# Reinstall drivers
sudo apt remove rtl-sdr
sudo apt install rtl-sdr

# Reboot
sudo reboot
```

### GPS No Fix

**Error:** "GPS timeout after 30s"

**Solutions:**
1. **Go outside** - GPS needs clear sky view
2. Wait 2-5 minutes for initial fix (cold start)
3. Check antenna connection
4. Test with raw output: `cat /dev/ttyUSB0`

**If still no fix:**
```bash
# Install GPS test tool
sudo apt install gpsd gpsd-clients

# Test GPS
gpsmon /dev/ttyUSB0
# Should show satellites and fix status
```

### Permission Errors

**Error:** "Permission denied: /dev/ttyUSB0"

```bash
# Add user to dialout group (for serial port access)
sudo usermod -a -G dialout $USER

# Add to plugdev group (for USB devices)
sudo usermod -a -G plugdev $USER

# Log out and back in
```

### Python Import Errors

**Error:** "ModuleNotFoundError: No module named 'rtlsdr'"

```bash
# Ensure venv is activated
source ~/CellSignalMapper/venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Poor Signal Readings

**All readings show -999 dBm:**

1. Check antenna connection
2. Verify frequency range (Band 5: 869-894 MHz is within RTL-SDR range)
3. Increase gain:
   ```yaml
   rtl_sdr:
     gain: 49  # Try maximum gain
   ```
4. Check for EMI from Pi's power supply - use ferrite beads

---

## Performance Tips

### Reduce CPU Usage

```bash
# Lower priority for other services
sudo systemctl stop bluetooth
sudo systemctl stop avahi-daemon

# Increase swap (if using 4GB Pi)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Optimize for Battery (Drone Use)

```yaml
# In config.yaml, reduce logging
logging:
  log_to_file: false  # Don't write logs during flight
  log_level: "WARNING"  # Reduce console output

scan:
  integration_time: 0.5  # Faster scans (less accurate)
```

### Overclock Pi 5 (More Processing Power)

```bash
sudo nano /boot/config.txt

# Add at end:
over_voltage=2
arm_freq=2600

# Save and reboot
sudo reboot
```

---

## What's Different from Windows

| Aspect | Windows (Testing) | Raspberry Pi (Production) |
|--------|------------------|---------------------------|
| GPS | Windows Location API (WiFi) | ReadytoSky NEO-M8N (Serial NMEA) |
| GPS Port | N/A | `/dev/serial0` (GPIO UART) |
| Baud Rate | N/A | 38400 (NEO-M8N specific) |
| Altitude | None (WiFi location) | Real altitude from GPS satellites |
| RTL-SDR Path | `C:\...\rtl_power.exe` | `/usr/bin/rtl_power` |
| Platform Detection | Auto (main.py detects) | Auto (main.py detects) |
| Code Changes | **None needed** | **None needed** |

The code **automatically switches** between Windows and Linux modes!

**📖 For detailed GPS wiring:** See `GPS_WIRING_GUIDE.md`

---

## Next Steps: Drone Integration

Once the Pi system is working on the ground:

1. **Mount hardware on drone:**
   - Use vibration damping for Pi
   - Secure antenna away from motors
   - Connect to separate BEC/regulator

2. **Test EMI:**
   - Run scanner while motors idle
   - Check for signal noise
   - Add shielding if needed

3. **Flight test:**
   - Start scanner on ground
   - Wait for GPS lock
   - Launch and hover at 10m
   - Verify measurements look good
   - Land and check data

4. **Full mapping flight:**
   - Plan grid pattern
   - Set scan interval (10-15s recommended)
   - Fly entire area
   - Process data on PC

---

## Summary Checklist

Before first flight:

- ✅ RTL-SDR detected (`rtl_test -t` works)
- ✅ GPS getting fix (8+ satellites)
- ✅ Single scan mode working
- ✅ Data files being created
- ✅ KML viewable in Google Earth
- ✅ Continuous mode tested on ground
- ✅ Hardware securely mounted
- ✅ Backup of all data
- ✅ Emergency landing procedure ready

---

**You're ready to deploy!** The system is fully portable between Windows (testing) and Raspberry Pi (production) with zero code changes.
