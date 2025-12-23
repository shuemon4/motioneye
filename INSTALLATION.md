# MotionEye Installation Guide

MotionEye is a web interface for the Motion surveillance daemon. This document covers installation on Linux systems, with a focus on Raspberry Pi platforms.

**Supported Platforms**: Debian/Ubuntu (APT-based) and Fedora/RHEL (RPM-based) distributions with systemd.

---

## Prerequisites

Before installing MotionEye, ensure your system meets these requirements:

### System Requirements
- **OS**: Linux with systemd (Debian/Ubuntu or Fedora/RHEL)
- **Python**: 3.7 or later
- **Architecture**: amd64, ARMv7 (32-bit), ARMv8/aarch64 (64-bit), or other architectures
- **Disk Space**: ~100 MB for MotionEye + space for video storage
- **RAM**: 256 MB minimum (1+ GB recommended for 4K streams)

### Motion Daemon
- **Required**: Motion 5.0 or later (for CSRF protection and security)
- **Status**: Should be installed before or alongside MotionEye

### Network
- **Connectivity**: System must have Internet access during installation
- **Port 8765**: Must be available (configurable)

---

## Installation Steps

### Step 1: Install Python and Build Dependencies

#### Debian/Ubuntu (APT-based)

**Minimum installation** (when wheels are pre-compiled):

```bash
sudo apt update
sudo apt install --no-install-recommends ca-certificates curl python3
```

**For ARMv6/ARMv7 (32-bit), RISC-V, or other rare architectures**, additional build dependencies are required:

```bash
sudo apt install --no-install-recommends \
  python3-dev gcc libjpeg62-turbo-dev \
  libcurl4-openssl-dev libssl-dev
```

This is necessary to compile Pillow (image processing) and PycURL (HTTP client) from source.

#### Fedora/RHEL-based Systems

```bash
sudo dnf groupinstall "Development Tools"
sudo dnf install python3 python3-devel \
  openssl-devel libjpeg-turbo-devel libcurl-devel
```

### Step 2: Install Python Package Manager (pip)

#### Debian/Ubuntu 22.04 and Earlier

```bash
curl -sSfO 'https://bootstrap.pypa.io/get-pip.py'
sudo python3 get-pip.py
rm get-pip.py
```

#### Debian/Ubuntu 23.04+ / Bookworm+ (with PEP-668 Protection)

Modern Debian/Ubuntu versions use PEP 668 to prevent pip from installing outside virtual environments. MotionEye has minimal dependencies with flexible version requirements and is compatible with system packages.

**Option A: Enable pip for system-wide installation** (recommended for single-purpose systems)

```bash
# Ensure [global] section exists
grep -q '\[global\]' /etc/pip.conf 2> /dev/null || \
  printf '%b' '[global]\n' | sudo tee -a /etc/pip.conf > /dev/null

# Add break-system-packages=true
sudo sed -i '/^\[global\]/a\break-system-packages=true' /etc/pip.conf
```

**Option B: Install in a virtual environment**

```bash
python3 -m venv ~/motioneye-env
source ~/motioneye-env/bin/activate
pip install motioneye
```

Note: If using a virtual environment, activate it before running `motioneye_init` and when managing MotionEye manually.

### Step 3: Install MotionEye

#### Automatic Setup (Recommended)

The `motioneye_init` script performs all necessary setup:

```bash
sudo python3 -m pip install --pre motioneye
sudo motioneye_init
```

**What motioneye_init does**:
1. Creates the `motion` system user
2. Sets up configuration directories (`/etc/motioneye`)
3. Creates log and data directories with proper permissions
4. Installs systemd service file
5. Enables and starts the MotionEye service

**Requirements for automatic setup**:
- APT- or RPM-based distribution
- systemd as init system
- sudo access

#### Manual Setup (For Unsupported Distributions)

If your system is not supported by `motioneye_init`, follow these steps:

**1. Create system user:**

```bash
sudo useradd -r -s /bin/false -d /var/lib/motioneye motion
```

**2. Create directory structure:**

```bash
# Configuration
sudo mkdir -p /etc/motioneye
sudo chown motion:motion /etc/motioneye
sudo chmod 750 /etc/motioneye

# Logs
sudo mkdir -p /var/log/motioneye
sudo chown motion:motion /var/log/motioneye
sudo chmod 755 /var/log/motioneye

# Media storage
sudo mkdir -p /var/lib/motioneye
sudo chown motion:motion /var/lib/motioneye
sudo chmod 755 /var/lib/motioneye

# Runtime files
sudo mkdir -p /run/motioneye
sudo chown motion:motion /run/motioneye
sudo chmod 755 /run/motioneye
```

**3. Configure MotionEye:**

```bash
# Copy sample configuration
sudo cp /path/to/motioneye/extra/motioneye.conf.sample /etc/motioneye/motioneye.conf
sudo chown motion:motion /etc/motioneye/motioneye.conf
sudo chmod 640 /etc/motioneye/motioneye.conf
```

Edit `/etc/motioneye/motioneye.conf` as needed (see [Configuration](#configuration) section).

**4. Install systemd service:**

```bash
# For systemd systems
sudo cp /path/to/motioneye/extra/motioneye.systemd /etc/systemd/system/motioneye.service
sudo systemctl daemon-reload
sudo systemctl enable motioneye
sudo systemctl start motioneye
```

**5. Verify installation:**

```bash
sudo systemctl status motioneye
curl http://localhost:8765/
```

---

## Configuration

### Basic Configuration

MotionEye's main configuration file is `/etc/motioneye/motioneye.conf`. Key settings include:

| Option | Default | Purpose |
|--------|---------|---------|
| `listen` | `0.0.0.0` | IP address to bind to (`127.0.0.1` for localhost only) |
| `port` | `8765` | HTTP port for web interface |
| `log_level` | `info` | Logging level (quiet, error, warning, info, debug) |
| `motion_control_port` | `7999` | Motion daemon HTTP control port |
| `motion_control_localhost` | `true` | Restrict Motion control to localhost |
| `media_path` | `/var/lib/motioneye` | Where media files are stored |
| `log_path` | `/var/log/motioneye` | Where logs are written |
| `conf_path` | `/etc/motioneye` | Configuration directory |

### Network Configuration

To make MotionEye accessible from other systems:

```bash
# Edit /etc/motioneye/motioneye.conf
sudo nano /etc/motioneye/motioneye.conf

# Change listen to allow external connections
listen 0.0.0.0
port 8765

# If using Motion daemon on another system
motion_control_localhost false
```

### Security Configuration

For Internet-facing installations, enable authentication:

1. Access the web interface at `http://[your_ip]:8765`
2. Use default credentials: **username** `admin`, **password** empty
3. Go to Settings → Preferences and set a strong password
4. Configure HTTPS (requires reverse proxy like nginx)

---

## Installation Scenarios

### Scenario 1: Fresh Raspberry Pi Installation

For a new Raspberry Pi with Bookworm:

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Motion daemon
# (Follow Motion installation instructions for Pi 5 or Pi 4)

# 3. Install MotionEye dependencies
sudo apt install --no-install-recommends \
  ca-certificates curl python3

# 4. Install MotionEye
curl -sSfO 'https://bootstrap.pypa.io/get-pip.py'
sudo python3 get-pip.py
rm get-pip.py

sudo python3 -m pip install --pre motioneye
sudo motioneye_init

# 5. Start MotionEye
sudo systemctl start motioneye
sudo systemctl enable motioneye
```

Access at: `http://[pi_ip]:8765`

### Scenario 2: Pi 5 with Camera Module 3

For Raspberry Pi 5 with the new libcamera stack:

```bash
# Install libcamera support
sudo apt install libcamera-dev libcamera-tools \
  libjpeg-dev libavformat-dev libavcodec-dev

# Install and configure Motion 5.0+ (libcamera version)
# See Motion installation guide

# Then install MotionEye as above
sudo python3 -m pip install --pre motioneye
sudo motioneye_init
```

**Important**: Pi 5 requires Motion 5.0+ with libcamera support. Older MMAL-based Motion versions won't work.

### Scenario 3: Armv7 32-bit System (Pi 3/4 with 32-bit OS)

```bash
# Install build dependencies for wheel compilation
sudo apt install python3-dev gcc libjpeg62-turbo-dev \
  libcurl4-openssl-dev libssl-dev

# Install pip
curl -sSfO 'https://bootstrap.pypa.io/get-pip.py'
sudo python3 get-pip.py
rm get-pip.py

# Install MotionEye (will compile Pillow and PycURL)
sudo python3 -m pip install --pre motioneye
sudo motioneye_init
```

---

## Accessing MotionEye

### Initial Access

After successful installation, MotionEye listens on port **8765**:

```
http://[your_ip]:8765/
```

Replace `[your_ip]` with:
- `localhost` - Local access only
- `127.0.0.1` - Local access only
- Your system's IP address - Network access
- Your hostname - If DNS resolves it

### Default Credentials

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | (empty) |

**⚠️ Security Warning**: Change the admin password immediately before exposing MotionEye to the Internet. See [Security Configuration](#security-configuration).

### First-Time Setup

1. **Login**: Use default credentials above
2. **Set Password**: Preferences → Change Password
3. **Add Cameras**: Main page → Add Camera (configure Motion daemon)
4. **Configure Streaming**: Camera settings → adjust resolution and frame rate
5. **Enable Detection**: Camera settings → Motion Detection settings

---

## Post-Installation

### Verify Installation

Check that all components are running:

```bash
# MotionEye service status
sudo systemctl status motioneye

# Motion daemon status (if installed)
sudo systemctl status motion

# Test web interface
curl -I http://localhost:8765/

# Check logs
sudo journalctl -u motioneye -n 50
```

### Common Issues

#### MotionEye Won't Start

```bash
# Check service status and errors
sudo systemctl status motioneye
sudo journalctl -u motioneye -n 100

# Verify config file exists
ls -l /etc/motioneye/motioneye.conf

# Check permissions
ls -l /var/log/motioneye /var/lib/motioneye
```

#### Can't Connect to Web Interface

```bash
# Verify service is running
sudo systemctl status motioneye

# Check if port is listening
sudo ss -tlnp | grep 8765

# Test localhost access
curl http://localhost:8765/

# Check for firewall
sudo ufw status  # UFW
sudo firewall-cmd --list-all  # firewalld
```

#### Motion Daemon Not Detected

```bash
# Verify Motion is installed
which motion
motion -h | grep Version

# Check Motion is running
sudo systemctl status motion

# Verify Motion HTTP port
ps aux | grep motion
```

For more troubleshooting, see [Motion API Troubleshooting](docs/troubleshooting/motion-api-errors.md).

---

## Upgrading MotionEye

### Standard Upgrade

```bash
# Stop service
sudo systemctl stop motioneye

# Upgrade package
sudo python3 -m pip install --upgrade --pre motioneye

# Start service
sudo systemctl start motioneye

# Verify
sudo systemctl status motioneye
```

### Rollback

If issues occur after upgrade:

```bash
# Downgrade to previous version
sudo systemctl stop motioneye
sudo python3 -m pip install 'motioneye==0.43.1b4'
sudo systemctl start motioneye
```

---

## Uninstallation

To completely remove MotionEye:

```bash
# Stop service
sudo systemctl stop motioneye

# Disable service
sudo systemctl disable motioneye

# Remove service file
sudo rm /etc/systemd/system/motioneye.service
sudo systemctl daemon-reload

# Uninstall package
sudo python3 -m pip uninstall motioneye

# Remove user (optional, keep if using Motion daemon)
sudo userdel motion

# Remove directories (optional)
sudo rm -rf /etc/motioneye /var/log/motioneye /var/lib/motioneye
```

---

## Advanced Configuration

### Behind a Reverse Proxy

To access MotionEye through a web server (nginx/Apache):

```bash
# Edit /etc/motioneye/motioneye.conf
listen 127.0.0.1  # Localhost only
port 8765

# Configure nginx upstream
upstream motioneye {
    server 127.0.0.1:8765;
}

server {
    listen 80;
    server_name motioneye.example.com;

    location / {
        proxy_pass http://motioneye;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Multi-User Setup

MotionEye can be run in a Python virtual environment for isolation:

```bash
# Create virtual environment
python3 -m venv ~/.local/motioneye

# Activate environment
source ~/.local/motioneye/bin/activate

# Install MotionEye
pip install --pre motioneye

# Run manually (without systemd)
meyectl startserver -c /path/to/motioneye.conf
```

---

## Support and Troubleshooting

### Getting Help

1. **MotionEye Wiki**: https://github.com/motioneye-project/motioneye/wiki
2. **Issue Tracker**: https://github.com/motioneye-project/motioneye/issues
3. **Motion Project**: https://motion-project.github.io/

### Logging

Enable debug logging for troubleshooting:

```bash
# Edit configuration
sudo nano /etc/motioneye/motioneye.conf
log_level debug

# Restart and monitor
sudo systemctl restart motioneye
sudo journalctl -u motioneye -f
```

### Performance Optimization

For systems with limited resources:

- Reduce camera resolution
- Lower frame rate (fps)
- Disable motion detection features not in use
- Use MJPEG instead of H.264 streaming (lower CPU)
- Monitor CPU usage: `top`, `htop`, or `ps aux | grep motion`

---

## Platform-Specific Notes

### Raspberry Pi

**Pi 5** (Recommended for new setups):
- CPU: Cortex-A76 @ 2.4 GHz (excellent performance)
- Camera: Use Camera Module 3 (v3) with libcamera
- Motion: Requires Motion 5.0+ with libcamera support

**Pi 4** (Still viable):
- CPU: Cortex-A72 @ 1.5 GHz
- Camera: Camera Module 3 (v3) works via libcamera, or v2 with older Motion
- Motion: Motion 4.x (MMAL) or 5.0+ (libcamera)

**Pi 3 and Earlier** (Limited support):
- CPU: ARMv7 32-bit, slower performance
- Camera: Camera Module v2 or compatible USB cameras
- Motion: Motion 4.x only (MMAL not available in 5.0)

### Docker

A Docker image is available in the `docker/` directory:

```bash
docker-compose -f docker/docker-compose.yml up -d
```

---

## License

MotionEye is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE) for details.

---

## Related Documentation

- [Motion Integration Guide](docs/MotionEye-Integration-Guide.md)
- [Motion API Troubleshooting](docs/troubleshooting/motion-api-errors.md)
- [Motion Project](https://motion-project.github.io/)
