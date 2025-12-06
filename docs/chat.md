Short version: on a Pi 5 you **can’t turn on the old “legacy” camera stack**, and Motion still only talks V4L2, not libcamera. So people are working around it by **adding a compatibility/bridge layer** or by **ditching Motion**.

Here are the main patterns I see in the wild:

---

## 1. Use `libcamerify` so Motion sees a fake V4L2 camera

`libcamerify` is a little shim that uses libcamera internally, but exposes the camera as a V4L2 `/dev/videoX` device – which Motion *can* use.

Typical approach:

1. Install Motion + the libcamera V4L2 compatibility bits:

```bash
sudo apt update
sudo apt install motion libcamera-apps libcamera-v4l2
```

2. Install the prebuilt Motion package for Bookworm/Pi from Motion-Project if needed (4.6.0+): ([digithink.com][1])

```bash
wget https://github.com/Motion-Project/motion/releases/download/release-4.6.0/pi_bookworm_motion_4.6.0-1_arm64.deb
sudo dpkg -i pi_bookworm_motion_4.6.0-1_arm64.deb
sudo apt --fix-broken install
```

3. Run Motion via `libcamerify`:

```bash
sudo libcamerify motion
```

4. In `motion.conf`, point the camera at the compatibility V4L2 device, usually:

```text
videodevice /dev/video0
```

On Raspberry Pi forums and Reddit, people confirm Motion working this way (sometimes after installing `libcamera-v4l2` to get rid of LD_PRELOAD errors). ([Raspberry Pi Forums][2])

**Caveats:**

* Still a bit fragile on Pi 5 – wrong builds/libs can segfault, and only certain pixel formats work.
* Only one process can own the camera – you can’t use `libcamera-hello` at the same time.

---

## 2. Use `v4l2loopback` + `libcamera-vid` / `rpicam-vid`

Another common pattern is to create a **virtual V4L2 device** and *pipe* libcamera video into it:

1. Install `v4l2loopback` and ffmpeg (or GStreamer):

```bash
sudo apt install v4l2loopback-dkms ffmpeg
```

2. Create a virtual device:

```bash
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="libcamera-bridge" exclusive_caps=1
```

3. Stream libcamera video into the virtual device, e.g. with ffmpeg:

```bash
libcamera-vid -t 0 --inline --codec yuv420 --width 1280 --height 720 -o - |
  ffmpeg -re -i - -f v4l2 /dev/video10
```

4. In Motion:

```text
videodevice /dev/video10
```

The MotionEye issue tracker has a walkthrough of exactly this idea: “bridge libcamera output to a V4L2 virtual device using v4l2loopback and ffmpeg or GStreamer.” ([GitHub][3])

This keeps Motion mostly oblivious to libcamera and works on Pi 5 because everything libcamera-side is “upstream” of the bridge.

---

## 3. Don’t use V4L2 at all – feed Motion a network stream

Because Pi 5 must use libcamera and can happily output to RTSP/MJPEG/etc., another route is:

1. Use `rpicam-vid` or a small RTSP/MJPEG server (e.g. `raspi-cam-srv`) to publish a stream. ([Raspberry Pi Forums][4])
2. Configure Motion’s camera as a **Network Camera** (HTTP, RTSP, etc.) pointing at that stream.

This avoids V4L2 entirely – the Pi 5 side just runs libcamera and streams out over the network; Motion only sees an IP camera. Folks doing surveillance on Pi 5s also do exactly this with other NVR software like ZoneMinder: run a local MJPEG/RTSP stream and treat the Pi as an IP cam. ([Raspberry Pi Forums][5])

---

## 4. Switch tools (custom libcamera motion detection)

Some people simply **abandon Motion/MotionEye** on Pi 5 and:

* Write their own motion detection using libcamera + OpenCV or custom code. ([Raspberry Pi Forums][2])
* Or use libcamera-native projects (e.g. `raspi-cam-srv`, Picamera2-based scripts) and roll simple “save on motion” logic.

Given that Pi 5 **no longer supports the legacy camera stack** and libcamera is the only real path forward, this is where many newer projects are going. ([forum.arducam.com][6])

---

## 5. What *doesn’t* work on a Pi 5

Just to be explicit:

* **Enabling “legacy camera” in raspi-config** – that option doesn’t exist on modern Bookworm Pi OS for Pi 5, and the Pi 5 doesn’t support the old stack anyway. ([forum.arducam.com][6])
* Old MotionEyeOS images that depended on legacy/MMAL – those are effectively dead for Pi 5 without heavy surgery.

---

## What I’d personally try first (for your use case)

Given you’re already deep into Motion/MotionEye and Pi 5:

1. **Try `libcamerify motion` + `/dev/video0`**, making sure:

   * `libcamera-v4l2` is installed.
   * Nothing else is using the camera.
2. If that’s flaky, move to **v4l2loopback + libcamera-vid** – it’s more plumbing, but also more controllable and usually more reliable.

If you tell me:

* Which Pi camera model you’re using (Cam v2, HQ, v3, etc.), and
* Whether you’re running Raspberry Pi OS Bookworm 32-bit or 64-bit,

I can sketch a concrete set of commands and a `motion.conf` snippet tailored specifically to your setup.

[1]: https://www.digithink.com/buildnotes/buster-motion-and-bookworm/?utm_source=chatgpt.com "Install motion on raspberry pi running debian bookworm"
[2]: https://forums.raspberrypi.com/viewtopic.php?t=365152 "Pi 5 and Motion problem - Raspberry Pi Forums"
[3]: https://github.com/motioneye-project/motioneye/issues/3168?utm_source=chatgpt.com "Need help or support for motioneye into Raspberry PI 5 ..."
[4]: https://forums.raspberrypi.com/viewtopic.php?t=371704 "video surveilance software using libcamera - Raspberry Pi Forums"
[5]: https://forums.raspberrypi.com/viewtopic.php?t=390060&utm_source=chatgpt.com "Pi 5 and surveillance camera: Motioneye or something else?"
[6]: https://forum.arducam.com/t/imx708-and-imx477-not-found-on-raspberry-pi-5/7922?utm_source=chatgpt.com "IMX708 and IMX477 not found on raspberry pi 5"
