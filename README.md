# What is motionEye?

**motionEye** is an online interface for the software [_motion_](https://motion-project.github.io/), a video surveillance program with motion detection.

Check out the [__wiki__](https://github.com/motioneye-project/motioneye/wiki) for more details. Changelog is available on the [__releases page__](https://github.com/motioneye-project/motioneye/releases).

From version 0.43, **motionEye** is multilingual:

| [![](https://hosted.weblate.org/widgets/motioneye-project/-/287x66-black.png)<br>![](https://hosted.weblate.org/widgets/motioneye-project/-/multi-auto.svg)](https://hosted.weblate.org/engage/motioneye-project/) |
| -: |

You can contribute to translations on [__Weblate__](https://hosted.weblate.org/projects/motioneye-project).

# Installation

See INSTALLATION.md for detailed instructions on how to install MotionEye. 

# Upgrade

```sh
sudo systemctl stop motioneye
sudo python3 -m pip install --upgrade --pre motioneye
sudo systemctl start motioneye
```

# Accessing the user interface

After having successfully followed the installation instructions, the motionEye server should be running on your system and listening on port **8765**. Fire up your favorite web browser and visit the following URL (replacing `[your_ip]` with... well, your system's IP address):

```
http://[your_ip]:8765/
```

Use usernamme _admin_ with empty password when prompted for credentials. For security, __please do set up a proper password for the admin user__, at least if you plan to make your motionEye installation accessible from the Internet.

# Configuration

## System Power Controls

Shutdown and Reboot buttons are **enabled by default** in the General Settings section for administrator users. This is designed for dedicated hardware installations (like Raspberry Pi) where system power control is essential for setup and troubleshooting.

If you want to disable these controls (e.g., on a shared server), edit `/etc/motioneye/motioneye.conf`:

```conf
enable_reboot false
```

Then restart the service:
```sh
sudo systemctl restart motioneye
```
