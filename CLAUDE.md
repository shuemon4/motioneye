# motionEye Project Notes

## Raspberry Pi 5 Installation

### Prerequisites

When installing from a Git clone (especially from Windows), fix these issues before running `motioneye_init`:

```sh
# Fix executable permissions (lost when transferring from Windows)
chmod +x motioneye/extra/linux_init

# Fix Windows line endings (CRLF → LF)
sudo apt install dos2unix
dos2unix motioneye/extra/*
dos2unix motioneye/scripts/*
```

### Installation Method

For production use, install without editable mode so systemd can access the files:

```sh
sudo python3 -m pip install .  # NOT -e .
```

Editable installs (`-e`) place files in your home directory, causing permission issues when the systemd service runs as root.

---

## Raspberry Pi Camera Setup

### Camera Detection Commands

The camera utility commands have changed between Raspberry Pi OS versions:

| OS Version | Package | Command |
|------------|---------|---------|
| Bullseye (older) | `libcamera-apps` | `libcamera-hello --list-cameras` |
| Bookworm (newer) | `rpicam-apps` | `rpicam-hello --list-cameras` |

### Installation

**For Raspberry Pi OS Bookworm and newer:**
```sh
sudo apt update
sudo apt install rpicam-apps
rpicam-hello --list-cameras
```

**For Raspberry Pi OS Bullseye and older:**
```sh
sudo apt update
sudo apt install libcamera-apps
libcamera-hello --list-cameras
```

### Camera Configuration

If the camera is not detected, check `/boot/config.txt`:

**For automatic detection (most cases):**
```
camera_auto_detect=1
```

**For manual configuration (older modules like OV5647):**
```
dtoverlay=ov5647
camera_auto_detect=0
```

Reboot after modifying `config.txt`:
```sh
sudo reboot
```

### Adding Camera in motionEye

1. Open motionEye web UI
2. Click menu (top-left) → **Add Camera**
3. Try in order:
   - **Local MMAL Camera** (preferred for RPi cameras)
   - **Local V4L2 Camera** with device `/dev/video0`

If V4L2 camera doesn't appear:
```sh
sudo modprobe bcm2835-v4l2

# Make permanent:
echo "bcm2835-v4l2" | sudo tee -a /etc/modules
```

---

## Troubleshooting

### Service won't start (Permission denied)

If using editable install, either:
1. Fix permissions: `chmod 755 /home/<user> && chmod -R 755 /home/<user>/motioneye`
2. Or reinstall without `-e` flag (recommended)

### Check service status

```sh
sudo systemctl status motioneye
sudo journalctl -u motioneye -n 50
```

### Verify port is listening

```sh
sudo ss -tlnp | grep 8765
```
