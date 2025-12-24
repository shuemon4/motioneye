# MotionEye Installation Guide

MotionEye is a web interface for the Motion surveillance daemon. This document covers installation on Linux systems, with a focus on Raspberry Pi platforms.

**Supported Platforms**: Debian/Ubuntu (APT-based) and Fedora/RHEL (RPM-based) distributions with systemd.

---

## Prerequisites

Before installing MotionEye, ensure your system meets these requirements:

### System Requirements
- **OS**: 64-bit Linux with systemd (Debian Bookworm/Trixie, Ubuntu 22.04+, or Fedora/RHEL)
- **Python**: 3.10 or later (3.13 on Trixie)
- **Architecture**: amd64 or aarch64 (64-bit ARM) only
- **Disk Space**: ~200 MB for MotionEye + dependencies + space for video storage
- **RAM**: 512 MB minimum (1+ GB recommended for streaming)

### Motion Daemon
- **Required**: Motion 5.0 or later (libcamera support, CSRF protection)
- **Note**: Motion must be installed before MotionEye

### Network
- **Connectivity**: System must have Internet access during installation
- **Port 8765**: Must be available (configurable)

---

## Installation Steps

### Step 1: Install Python and Build Dependencies

#### Debian Trixie (Raspberry Pi OS)

For Raspberry Pi 4/5 running Trixie (Debian 13):

```bash
sudo apt update
sudo apt install -y python3-pip python3-dev
```

**Note**: Trixie includes Python 3.13. Some packages (jinja2, babel) are pre-installed as system dependencies.

#### Debian Bookworm

```bash
sudo apt update
sudo apt install --no-install-recommends ca-certificates curl python3 python3-pip
```

#### Fedora/RHEL-based Systems

```bash
sudo dnf groupinstall "Development Tools"
sudo dnf install python3 python3-devel python3-pip \
  openssl-devel libjpeg-turbo-devel libcurl-devel
```

### Step 2: Handle PEP 668 (Modern Debian/Ubuntu)

Modern Debian/Ubuntu versions (Bookworm, Trixie, 23.04+) use PEP 668 to prevent pip from installing packages outside virtual environments.

**Option A: Use --break-system-packages flag** (recommended for dedicated systems like Raspberry Pi)

This is the simplest approach for single-purpose systems:

```bash
# All pip install commands require this flag
sudo pip3 install --break-system-packages <package>
```

**Option B: Configure pip globally** (avoid typing the flag each time)

```bash
# Ensure [global] section exists
grep -q '\[global\]' /etc/pip.conf 2> /dev/null || \
  printf '%b' '[global]\n' | sudo tee -a /etc/pip.conf > /dev/null

# Add break-system-packages=true
sudo sed -i '/^\[global\]/a\break-system-packages=true' /etc/pip.conf
```

**Option C: Install in a virtual environment**

```bash
python3 -m venv ~/motioneye-env
source ~/motioneye-env/bin/activate
pip install motioneye
```

Note: If using a virtual environment, activate it before running `motioneye_init` and when managing MotionEye manually.

### Step 3: Install MotionEye

#### Option A: Automatic Setup (Recommended)

The `motioneye_init` script performs all necessary setup:

```bash
sudo pip3 install --break-system-packages motioneye
sudo motioneye_init
```

**What motioneye_init does**:
1. Creates the `motion` system user and group
2. Sets up configuration directories (`/etc/motioneye`, `/var/log/motioneye`, `/var/lib/motioneye`)
3. Sets correct ownership (`motion:motion`) on all directories
4. Installs and enables the systemd service
5. Starts the MotionEye service

**Requirements for automatic setup**:
- APT- or RPM-based distribution
- systemd as init system
- sudo access

#### Option B: Manual Setup (Quick Start)

For development or testing, you can skip `motioneye_init` and configure manually:

**1. Install MotionEye system-wide:**

```bash
# From PyPI
sudo pip3 install --break-system-packages motioneye

# Or from source (clone/rsync first)
cd ~/motioneye
sudo pip3 install --break-system-packages .
```

**Important**: Use `sudo pip3 install` for system-wide access. User-level installation (`pip3 install` without sudo) installs to `~/.local/` which is not accessible to root or the systemd service.

**2. Create minimal configuration:**

```bash
sudo mkdir -p /etc/motioneye
sudo tee /etc/motioneye/motioneye.conf > /dev/null << 'CONFIG'
port 8765
listen 0.0.0.0
CONFIG
```

**Note**: Do NOT specify `motion_binary` in the config - MotionEye autodetects it via `which motion`.

**3. Fix permissions (CRITICAL):**

```bash
# Create motion user/group if missing
sudo groupadd -r motion 2>/dev/null || true
sudo useradd -r -g motion -G video -s /usr/sbin/nologin motion 2>/dev/null || true

# Set correct ownership
sudo chown -R motion:motion /etc/motioneye
```

**4. Start MotionEye:**

```bash
# Manual start (for testing)
sudo meyectl startserver -c /etc/motioneye/motioneye.conf -l &

# Or via systemd (if service file exists)
sudo systemctl start motioneye
```

**5. Verify installation:**

```bash
curl http://localhost:8765/
sudo ss -tlnp | grep 8765
```

#### Option C: Full Manual Setup (For Unsupported Distributions)

For systems not supported by `motioneye_init`:

**1. Create system user:**

```bash
sudo groupadd -r motion
sudo useradd -r -g motion -G video -s /usr/sbin/nologin -d /var/lib/motioneye motion
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
```

**3. Configure MotionEye:**

```bash
# Create minimal config
sudo tee /etc/motioneye/motioneye.conf > /dev/null << 'CONFIG'
port 8765
listen 0.0.0.0
CONFIG
sudo chown motion:motion /etc/motioneye/motioneye.conf
sudo chmod 640 /etc/motioneye/motioneye.conf
```

**4. Install systemd service:**

```bash
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

### Scenario 1: Raspberry Pi 5 with Trixie (Recommended)

Tested on: Raspberry Pi 5 with Camera Module 3 (IMX708), Debian Trixie 64-bit.

```bash
# 1. Update system and install pip
sudo apt update
sudo apt install -y python3-pip python3-dev

# 2. Install Python dependencies
sudo pip3 install --break-system-packages tornado pillow pycurl boto3

# 3. Install MotionEye (from PyPI or source)
sudo pip3 install --break-system-packages motioneye

# 4. Initialize (creates user, directories, service)
sudo motioneye_init

# 5. Verify
sudo systemctl status motioneye
curl http://localhost:8765/
```

**Installation Time**: ~60 seconds
**Memory Usage**: ~91 MB (MotionEye only)
**Access URL**: `http://[pi_ip]:8765`

### Scenario 2: Raspberry Pi 4 with Trixie

Tested on: Raspberry Pi 4 with Camera Module 2 (IMX219), Debian Trixie 64-bit.

```bash
# 1. Update system and install pip
sudo apt update
sudo apt install -y python3-pip python3-dev

# 2. Install Python dependencies (some already present)
# jinja2 and babel are typically pre-installed
sudo pip3 install --break-system-packages tornado pillow pycurl boto3

# 3. Install MotionEye system-wide
sudo pip3 install --break-system-packages motioneye

# 4. Initialize
sudo motioneye_init

# 5. Verify
sudo systemctl status motioneye
curl http://localhost:8765/
```

**Installation Time**: ~90 seconds
**Memory Usage**: ~90 MB (MotionEye), ~75 MB (Motion), ~50 MB (mediamtx)
**Access URL**: `http://[pi_ip]:8765`

### Scenario 3: Development/Testing (Manual Quick Start)

For development without `motioneye_init`:

```bash
# 1. Transfer source code
rsync -avz --exclude='.git' --exclude='__pycache__' \
  /path/to/motioneye/ user@pi:~/motioneye/

# 2. Install dependencies and package
ssh user@pi
sudo apt install -y python3-pip python3-dev
sudo pip3 install --break-system-packages tornado pillow pycurl boto3
cd ~/motioneye && sudo pip3 install --break-system-packages .

# 3. Create minimal config
sudo mkdir -p /etc/motioneye
sudo tee /etc/motioneye/motioneye.conf > /dev/null << 'CONFIG'
port 8765
listen 0.0.0.0
CONFIG

# 4. Fix permissions
sudo groupadd -r motion 2>/dev/null || true
sudo useradd -r -g motion -G video -s /usr/sbin/nologin motion 2>/dev/null || true
sudo chown -R motion:motion /etc/motioneye

# 5. Start manually
sudo meyectl startserver -c /etc/motioneye/motioneye.conf -l &
```

**Note**: Use `meyectl startserver` syntax (command first, then options).

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

#### Service Fails After Reboot (Most Common)

**Error**: `CRITICAL: config directory "/etc/motioneye" does not exist or is not writable`

**Cause**: The `/etc/motioneye` directory was created with `root:root` ownership, but the systemd service runs as the `motion` user.

**Fix**:
```bash
sudo chown -R motion:motion /etc/motioneye
sudo systemctl restart motioneye
```

**Prevention**: Always run `sudo motioneye_init` or manually set permissions after creating config directories.

#### meyectl: Command Not Found

**Cause**: MotionEye was installed to user site-packages (`~/.local/`) instead of system-wide.

**Fix**:
```bash
# Reinstall system-wide
sudo pip3 install --break-system-packages motioneye
```

**Verification**:
```bash
which meyectl  # Should show /usr/local/bin/meyectl
```

#### PEP 668: Externally Managed Environment

**Error**: `error: externally-managed-environment`

**Cause**: Modern Debian/Ubuntu enforces PEP 668, preventing pip installs to system Python.

**Fix**: Add `--break-system-packages` flag:
```bash
sudo pip3 install --break-system-packages motioneye
```

#### Invalid Configuration Option Warnings

**Warning**: `WARNING:root:unknown configuration option: motion_binary`

**Cause**: Specifying options that MotionEye doesn't recognize or auto-detects.

**Fix**: Use minimal config - MotionEye auto-detects Motion via `which motion`:
```bash
sudo tee /etc/motioneye/motioneye.conf > /dev/null << 'CONFIG'
port 8765
listen 0.0.0.0
CONFIG
```

#### MotionEye Won't Start

```bash
# Check service status and errors
sudo systemctl status motioneye
sudo journalctl -u motioneye -n 100

# Verify config file exists
ls -l /etc/motioneye/motioneye.conf

# Check permissions (must be motion:motion)
stat /etc/motioneye
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
motion --version

# Check Motion is running
sudo systemctl status motion

# Verify Motion HTTP port
ps aux | grep motion
```

For more troubleshooting, see [Motion API Troubleshooting](docs/troubleshooting/motion-api-errors.md).

### Quick Reference: Common Fixes

| Issue | Error | Fix | Time |
|-------|-------|-----|------|
| Service fails after reboot | Config directory not writable | `sudo chown -R motion:motion /etc/motioneye` | 5s |
| meyectl not found | Command not found | `sudo pip3 install --break-system-packages .` | 30s |
| Port already in use | Address already in use | Change port in config or kill existing process | 5s |
| Config not recognized | Unknown configuration option | Use minimal config (port, listen only) | 2s |
| PEP 668 error | Externally managed environment | Add `--break-system-packages` flag | 1s |

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

**This fork requires 64-bit OS and Pi 4 or newer.** 32-bit support has been removed.

**Pi 5** (Recommended):
- Kernel: 6.12.47+rpt-rpi-2712
- CPU: Cortex-A76 @ 2.4 GHz (excellent performance)
- Camera: Camera Module 3 (v3) with libcamera - IMX708 sensor
- Motion: Requires Motion 5.0+ with libcamera support
- OS: Debian Trixie 64-bit (tested)
- Memory: ~91 MB for MotionEye

**Pi 4** (Supported):
- Kernel: 6.12.47+rpt-rpi-v8
- CPU: Cortex-A72 @ 1.5 GHz
- Camera: Camera Module 2 (v2) or v3 via libcamera - IMX219 or IMX708 sensor
- Motion: Motion 5.0+ with libcamera support (MMAL removed)
- OS: Debian Trixie 64-bit (tested)
- Memory: ~90 MB (MotionEye), ~75 MB (Motion), ~50 MB (mediamtx)

**Pi 3 and Earlier**: Not supported (32-bit only, no libcamera)

### Python Package Versions (Trixie)

Verified working package versions on Debian Trixie (December 2025):

| Package | Version | Source |
|---------|---------|--------|
| tornado | 6.5.4 | pip3 wheel |
| jinja2 | (system) | apt (pre-installed) |
| pillow | 11.1.0-12.0.0 | pip3 wheel |
| pycurl | 7.45.7 | pip3 wheel |
| babel | (system) | apt (pre-installed) |
| boto3 | 1.42.15 | pip3 wheel |

**Note**: pycurl is not available via apt on Trixie - must use pip3.

### Docker

A Docker image is available in the `docker/` directory:

```bash
docker-compose -f docker/docker-compose.yml up -d
```

---

## Key Lessons Learned

Based on real-world installation testing on Pi 4 and Pi 5 (December 2025):

### Installation Strategy

1. **System-wide pip install**: Always use `sudo pip3 install` for MotionEye. User-level installation to `~/.local/` is not accessible to root or systemd services.

2. **PEP 668 compliance**: Trixie/Bookworm require `--break-system-packages` flag for system-wide pip installs. This is safe for single-purpose systems like Raspberry Pi.

3. **Minimal config works best**: MotionEye auto-detects Motion via `which motion`. Don't specify `motion_binary` in config.

4. **Permissions are critical**: The most common post-reboot failure is permissions. Always run `sudo chown -R motion:motion /etc/motioneye` after manual setup.

5. **meyectl syntax**: Command comes before options: `meyectl startserver -c config.conf` (not `meyectl -c config.conf startserver`).

### Dependency Strategy

1. **apt first**: Install what's available from apt (faster, pre-compiled)
2. **pip3 for missing**: Use pip3 for packages not in apt (pycurl on Trixie)
3. **Pre-built wheels**: Most packages have aarch64 wheels - no compilation needed
4. **Verify imports**: Test each package after installation to catch issues early

### Service Management

- `motioneye_init` handles user/group creation, directories, permissions, and systemd
- Manual setup requires careful attention to permissions
- Always verify with `curl http://localhost:8765/` after starting

---

## License

MotionEye is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE) for details.

---

## Related Documentation

- [Motion Integration Guide](docs/MotionEye-Integration-Guide.md)
- [Motion API Troubleshooting](docs/troubleshooting/motion-api-errors.md)
- [Motion Project](https://motion-project.github.io/)
- [Pi 4 Installation Notes](docs/installation/pi4-motioneye-installation-notes-20251223-1220.md) - Detailed step-by-step with issues encountered
- [Pi 5 Installation Notes](docs/installation/pi5-notes.md) - Streamlined installation on Pi 5
