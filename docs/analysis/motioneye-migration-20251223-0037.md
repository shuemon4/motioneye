# MotionEye Platform Migration Analysis (Pi 4+ / Trixie 64-bit)

## Section A: Search plan
- `rg -n "(debian|raspbian|bookworm|bullseye|buster|stretch|trixie|os-release|lsb_release)"`
- `rg -n "(armhf|arm64|aarch64|armv7|armv6|armv8|32-bit|64-bit|pointer|sizeof|uname -m|uname\(|platform\\.machine|sys\\.maxsize|bitness|arch)" motioneye scripts docs`
- `rg -n "(systemd|systemctl|service\\s|/etc/|/usr/bin|/lib/systemd|/etc/systemd|rc\\.d|init\\.d)" motioneye scripts`
- `rg -n "(systemd|systemctl|/etc/|/usr/bin|/usr/local/bin|/lib/systemd|init\\.d|service )" -g"*.py" -g"*.sh" -g"*.service" -g"*.sysv" motioneye scripts`
- `rg -n "(libcamera|raspivid|raspistill|rpicam|mmal|omx|v4l2|/dev/video|camera-|picam|bcm2835|imx|csi)" -g"*.py" -g"*.sh" -g"*.conf" -g"*.sample" motioneye scripts`
- `rg -n "(ffmpeg|avconv|libav|encoder|codec|h264|h265|hevc|omx|v4l2m2m|vaapi)" motioneye -g"*.py" -g"*.sh" -g"*.conf"`
- `rg -n "(uname -m|platform\\.machine|platform\\.processor|sys\\.maxsize|bits|armv6|armv7|armv8|aarch64|arm64|armhf)" motioneye scripts docs -g"*.py" -g"*.sh"`
- `rg -n "h264_omx|h264_v4l2m2m|omx|v4l2m2m" motioneye/static motioneye/templates motioneye/config motioneye/handlers`
- `rg -n "mmal" motioneye/templates motioneye/static motioneye/config motioneye/handlers motioneye/controls`
- `rg -n "libcamera|libcam" motioneye/static/js/main.js`

## Section B: Findings

### OS / Architecture
- `motioneye/update.py:31` (`get_os_version`, `_get_os_version_lsb_release`, `_get_os_version_uname`)
  - Risk: Raspberry Pi OS Lite / Debian 13 minimal installs may not have `lsb_release`, so OS detection falls back to `uname -rs` and reports only kernel version. UI “OS version” becomes inaccurate; update gating may behave incorrectly.
  - Suggestion: Prefer `/etc/os-release` parsing first, then `lsb_release`, then `uname`. See Patch C1.
- `motioneye/extra/linux_init:21` (dependency install + Motion package lookup)
  - Risk: Contains ARMv6 branch for Pi 1/Zero. Baseline is Pi 4+, so this is dead code and can select incorrect releases if left stale.
  - Suggestion: Remove ARMv6 branch and keep ARMv7/arm64 logic; also install `rpicam-apps` only on RPi for libcamera. See Patch C2.
- `motioneye/rpicam_rtsp.py:62` (`_detect_architecture`)
  - Risk: Relies solely on `platform.machine()`; edge strings or 32-bit userlands can trigger wrong mediamtx downloads. Trixie 64-bit should be OK but fragile.
  - Suggestion: Add pointer-size check to pick arm64v8 only when 64-bit. See Patch C3.
- Not found: No explicit pointer-size logic (`sys.maxsize`, `struct.calcsize`) or Debian version branching beyond the above.

### Systemd / Paths / Service Management
- `motioneye/extra/motioneye.systemd:10` (`ExecStart`)
  - Risk: Hard-coded `/usr/local/bin/meyectl` is incorrect for Debian packages (`/usr/bin/meyectl`), making the unit fail without the `linux_init` patch.
  - Suggestion: Use `/usr/bin/env meyectl` in the unit to be path-agnostic. See Patch C4.
- `motioneye/extra/linux_init:79` (systemd unit install)
  - Risk: Copies unit into `/etc/systemd/system` and patches `ExecStart`. This is OK but assumes write access and an exact unit line. For Trixie, it’s acceptable; keep but ensure the unit is path-agnostic.
  - Suggestion: Same as above; unit should not require sed substitution. Patch C4.
- `motioneye/extra/motioneye.sysv:1` (sysv init)
  - Risk: Legacy init script; not used on Debian 13/systemd. Retaining it keeps legacy paths and `/usr/local/bin` assumptions.
  - Suggestion: Deprecate/remove for Pi 4+ baseline (documentation or packaging). No runtime patch required unless you want to delete it.
- `motioneye/settings.py:28` (`CONF_PATH`, `RUN_PATH`, `LOG_PATH`, `MEDIA_PATH`)
  - Risk: Ties to FHS paths; OK for Trixie but requires writable `/etc`, `/var`, `/run` when running as service.
  - Suggestion: No change needed unless you want relocatable installs.

### Camera Backend (libcamera vs legacy) / V4L2 / /dev/video*
- `motioneye/controls/pictl.py:116` (`get_camera_interface`)
  - Risk: Includes MMAL fallback for Bullseye; on Trixie 64-bit MMAL is gone, and this branch is dead. It also keeps older BCM detection logic for Pi models below the new baseline.
  - Suggestion: Remove MMAL fallback and treat libcamera as the only CSI backend; fall back to V4L2 for USB. See Patch C5.
- `motioneye/controls/mmalctl.py:20` (`list_devices`)
  - Risk: Uses `vcgencmd`, not present on 64-bit Bookworm/Trixie by default. MMAL is obsolete on Pi 4+ with Trixie.
  - Suggestion: Deprecate MMAL path; keep only for migration if needed.
- `motioneye/handlers/config.py:529` (`list`, `proto == 'mmal'`)
  - Risk: “MMAL camera” selection still present; on Trixie it yields empty or misleading results.
  - Suggestion: Map `mmal` to `libcamera` and list rpicam devices only. See Patch C6.
- `motioneye/config/camera/crud.py:106` (`add_camera`, `proto == 'mmal'`)
  - Risk: New camera addition still uses “MMAL” to mean CSI camera. On Trixie this should be libcamera only.
  - Suggestion: Accept `libcamera` (and `mmal` only as alias) and error if libcamera is unavailable. See Patch C7.
- `motioneye/config/camera/converters.py:383` (`motion_camera_ui_to_dict`)
  - Risk: MMAL config persists for legacy; on Trixie it should be migrated to libcamera. Without conversion, config could remain invalid.
  - Suggestion: If `mmalcam_name` is present, convert to `libcam_device` when libcamera is available; drop `mmalcam_name`. See Patch C8.
- `motioneye/utils/__init__.py:195` (`is_mmal_camera` / `is_local_motion_camera`)
  - Risk: Treats MMAL as first-class local camera. For Pi 4+ baseline, this can be reclassified as “legacy” while still supporting migration.
  - Suggestion: Keep for migration but avoid creating new MMAL configs.
- `motioneye/static/js/main.js:4268` (Add Camera dialog)
  - Risk: UI still offers “Local MMAL Camera”; on Trixie this is misleading. Users should see “Local CSI (libcamera)” instead.
  - Suggestion: Replace UI option and CSS classes with `libcamera` and treat `mmal` as legacy label only. See Patch C9.
- `motioneye/controls/rpicamctl.py:204` (`list_devices`) and `motioneye/controls/v4l2ctl.py:41` (`list_devices`/`list_resolutions`)
  - Risk: Output parsing is brittle if upstream formats change in Debian 13 builds.
  - Suggestion: Consider adding tolerant parsing or fallback checks; no specific change required unless testing exposes issues.

### Encoding / ffmpeg / Hardware Acceleration
- `motioneye/mediafiles.py:222` (`find_ffmpeg`)
  - Risk: Parses `ffmpeg -codecs` lines for `encoders:` tokens; output format changes may result in empty encoder sets, hiding hardware acceleration.
  - Suggestion: Add fallback to parse `ffmpeg -encoders` if codec parsing fails. See Patch C10.
- `motioneye/config/defaults.py:199` (`_set_default_motion_camera`)
  - Risk: OMX fallback (`h264_omx`) is obsolete on 64-bit. For Pi 4+ baseline this is dead code and adds confusion.
  - Suggestion: Remove OMX fallback and prefer `h264_v4l2m2m` when available, otherwise software. See Patch C11.
- `motioneye/templates/partials/settings/_movies.html:35` (OMX options)
  - Risk: OMX choices appear when `ffmpeg` reports `h264_omx`. On 64-bit builds this is typically absent, but the option is obsolete for the baseline.
  - Suggestion: Remove OMX options from UI to simplify. See Patch C12.

## Section C: Patch proposals

### C1: OS version detection via /etc/os-release
```diff
diff --git a/motioneye/update.py b/motioneye/update.py
@@
 def get_os_version():
     try:
         import platformupdate
@@
     except ImportError:
-        return _get_os_version_lsb_release()
+        os_release = _get_os_version_os_release()
+        if os_release:
+            return os_release
+        return _get_os_version_lsb_release()
+
+
+def _get_os_version_os_release():
+    try:
+        data = {}
+        with open('/etc/os-release', 'r') as f:
+            for line in f:
+                line = line.strip()
+                if not line or line.startswith('#') or '=' not in line:
+                    continue
+                key, value = line.split('=', 1)
+                data[key] = value.strip().strip('"')
+        name = data.get('PRETTY_NAME') or data.get('NAME') or data.get('ID')
+        version = data.get('VERSION_ID') or data.get('VERSION_CODENAME') or ''
+        if name:
+            return name, version
+    except Exception:
+        pass
+    return None
```

### C2: Remove ARMv6 logic and add rpicam-apps only on RPi
```diff
diff --git a/motioneye/extra/linux_init b/motioneye/extra/linux_init
@@
-    # On ARMv6 Raspberry Pi models, download armv6hf package
-    PI=''
-    [[ ${ARCH} == 'armhf' && $(uname -m) == 'armv6l' ]] && PI='pi_'
     echo "INFO: ${DISTRO^} on ${ARCH} detected, checking for latest motion package from GitHub releases"
     command -v curl > /dev/null || DEBIAN_FRONTEND="noninteractive" apt-get -y --no-install-recommends install curl
-    URL=$(curl -sSfL 'https://api.github.com/repos/Motion-Project/motion/releases' | awk -F\" "/browser_download_url.*${PI}${DISTRO}_motion_.*_${ARCH}.deb/{print \$4}" | head -1)
+    URL=$(curl -sSfL 'https://api.github.com/repos/Motion-Project/motion/releases' | awk -F\" "/browser_download_url.*${DISTRO}_motion_.*_${ARCH}.deb/{print \$4}" | head -1)
@@
-  DEBIAN_FRONTEND="noninteractive" apt-get -y --no-install-recommends install "${MOTION}" v4l-utils ffmpeg curl
+  RPI_APPS=''
+  if grep -qi 'Raspberry Pi' /proc/device-tree/model 2>/dev/null || grep -qi 'Raspberry Pi' /proc/cpuinfo; then
+    RPI_APPS='rpicam-apps'
+  fi
+  DEBIAN_FRONTEND="noninteractive" apt-get -y --no-install-recommends install "${MOTION}" v4l-utils ffmpeg curl ${RPI_APPS}
```

### C3: Mediamtx arch detection with pointer-size guard
```diff
diff --git a/motioneye/rpicam_rtsp.py b/motioneye/rpicam_rtsp.py
@@
-import platform
+import platform
+import struct
@@
-    machine = platform.machine().lower()
-
-    if machine in ('aarch64', 'arm64'):
-        return 'arm64v8'
-    elif machine.startswith('armv7') or machine == 'armhf':
+    machine = platform.machine().lower()
+    bits = struct.calcsize('P') * 8
+
+    if machine in ('aarch64', 'arm64', 'armv8l'):
+        return 'arm64v8' if bits == 64 else 'armv7'
+    elif machine.startswith('armv7') or machine.startswith('armv6') or machine == 'armhf':
         return 'armv7'
@@
-    else:
-        logging.warning(f'Unknown architecture {machine}, defaulting to arm64v8')
-        return 'arm64v8'
+    else:
+        fallback = 'arm64v8' if bits == 64 else 'armv7'
+        logging.warning(f'Unknown architecture {machine}, defaulting to {fallback}')
+        return fallback
```

### C4: systemd unit path robustness
```diff
diff --git a/motioneye/extra/motioneye.systemd b/motioneye/extra/motioneye.systemd
@@
-ExecStart=/usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf
+ExecStart=/usr/bin/env meyectl startserver -c /etc/motioneye/motioneye.conf
```

### C5: Remove MMAL fallback in camera interface detection
```diff
diff --git a/motioneye/controls/pictl.py b/motioneye/controls/pictl.py
@@
-Camera Interface Priority:
-1. libcamera - if rpicam-hello/libcamera-hello is available (Bookworm, Pi 5)
-2. mmal - if legacy camera stack available (Bullseye, Pi 4 and earlier)
-3. v4l2 - generic fallback for USB cameras
+Camera Interface Priority:
+1. libcamera - if rpicam-hello/libcamera-hello is available
+2. v4l2 - generic fallback for USB cameras
@@
-    from motioneye.controls import rpicamctl, mmalctl
+    from motioneye.controls import rpicamctl
@@
-    # Fall back to MMAL on Raspberry Pi with legacy camera stack
-    pi_info = get_pi_model()
-    if pi_info:
-        # Validate that MMAL actually works
-        try:
-            devices = mmalctl.list_devices()
-            _camera_interface_cache = 'mmal'
-            logging.info('Camera interface: mmal (legacy camera stack)')
-            return 'mmal'
-        except Exception as e:
-            logging.warning(f'MMAL detection failed: {e} - falling back to v4l2')
-
-    # Not a Pi or no camera interface available
+    # Not a Pi or no camera interface available
     _camera_interface_cache = 'v4l2'
     logging.info('Camera interface: v4l2 (generic)')
     return 'v4l2'
```

### C6: Map MMAL listing to libcamera only
```diff
diff --git a/motioneye/handlers/config.py b/motioneye/handlers/config.py
@@
-from motioneye.controls import mmalctl, pictl, rpicamctl, smbctl, tzctl, v4l2ctl
+from motioneye.controls import pictl, rpicamctl, smbctl, tzctl, v4l2ctl
@@
-        elif proto == 'mmal':
+        elif proto in ('libcamera', 'mmal'):
@@
-            # Use libcamera if available (Bookworm on any Pi, or Pi 5)
-            # Fall back to MMAL on legacy systems (Bullseye on Pi 4 and earlier)
-            if pictl.uses_libcamera():
-                cameras = [
-                    {
-                        'id': d[0],
-                        'name': d[1],
-                        'supports_autofocus': d[2].get('supports_autofocus', False),
-                    }
-                    for d in rpicamctl.list_devices()
-                    if d[0] not in configured_devices
-                ]
-            else:
-                cameras = [
-                    {'id': d[0], 'name': d[1]}
-                    for d in mmalctl.list_devices()
-                    if (d[0] not in configured_devices)
-                ]
+            cameras = [
+                {
+                    'id': d[0],
+                    'name': d[1],
+                    'supports_autofocus': d[2].get('supports_autofocus', False),
+                }
+                for d in rpicamctl.list_devices()
+                if d[0] not in configured_devices
+            ]
```

### C7: Add camera flow: accept libcamera and alias mmal
```diff
diff --git a/motioneye/config/camera/crud.py b/motioneye/config/camera/crud.py
@@
-    Supports v4l2, motioneye, mmal/libcamera, netcam, and mjpeg camera types.
+    Supports v4l2, motioneye, libcamera, netcam, and mjpeg camera types.
@@
-    elif proto == 'mmal':
-        # Use libcamera if available (Bookworm on any Pi, or Pi 5)
-        # Fall back to MMAL on legacy systems (Bullseye on Pi 4 and earlier)
-        if pictl.uses_libcamera():
-            camera_config['libcam_device'] = device_details['path']
-            camera_config['libcam_buffer_count'] = 4
-            # Check if camera supports autofocus (Camera v3)
-            if device_details.get('supports_autofocus'):
-                camera_config['@supports_autofocus'] = True
-                # Camera v3 (IMX708) - high resolution
-                camera_config['width'] = 1920
-                camera_config['height'] = 1080
-            else:
-                # Camera v2 (IMX219) and others - conservative resolution
-                camera_config['width'] = 1280
-                camera_config['height'] = 720
-        else:
-            camera_config['mmalcam_name'] = device_details['path']
-            camera_config['width'] = 640
-            camera_config['height'] = 480
+    elif proto in ('libcamera', 'mmal'):
+        if not pictl.uses_libcamera():
+            raise ValueError('libcamera not available; install rpicam-apps')
+        camera_config['libcam_device'] = device_details['path']
+        camera_config['libcam_buffer_count'] = 4
+        if device_details.get('supports_autofocus'):
+            camera_config['@supports_autofocus'] = True
+            camera_config['width'] = 1920
+            camera_config['height'] = 1080
+        else:
+            camera_config['width'] = 1280
+            camera_config['height'] = 720
```

### C8: Convert MMAL configs to libcamera when saving
```diff
diff --git a/motioneye/config/camera/converters.py b/motioneye/config/camera/converters.py
@@
-from motioneye.controls import diskctl, smbctl, v4l2ctl
+from motioneye.controls import diskctl, smbctl, v4l2ctl, pictl
@@
-    elif utils.is_mmal_camera(prev_config):
-        proto = 'mmal'
+    elif utils.is_mmal_camera(prev_config):
+        proto = 'libcamera' if pictl.uses_libcamera() else 'mmal'
@@
-        elif proto == 'libcamera':
+        elif proto == 'libcamera':
+            if not prev_config.get('libcam_device'):
+                data['libcam_device'] = ui.get('device_url') or 'auto'
+            prev_config.pop('mmalcam_name', None)
```

### C9: UI: Replace MMAL with libcamera in Add Camera dialog
```diff
diff --git a/motioneye/static/js/main.js b/motioneye/static/js/main.js
@@
-        case 'mmal':
-            prettyType = 'MMAL Camera';
+        case 'mmal':
+            prettyType = 'Legacy MMAL Camera';
             break;
@@
-                        (hasLocalCamSupport ? '<option value="mmal">'+motionEyeI18n.t("Local MMAL Camera")+'</option>' : '') +
+                        (hasLocalCamSupport ? '<option value="libcamera">'+motionEyeI18n.t("Local CSI (libcamera)")+'</option>' : '') +
@@
-                '<tr class="v4l2 motioneye netcam mjpeg mmal">' +
+                '<tr class="v4l2 motioneye netcam mjpeg libcamera">' +
@@
-                '<tr class="v4l2 motioneye netcam mjpeg mmal">' +
+                '<tr class="v4l2 motioneye netcam mjpeg libcamera">' +
@@
-                '<tr class="v4l2 motioneye netcam mjpeg mmal">' +
+                '<tr class="v4l2 motioneye netcam mjpeg libcamera">' +
@@
-        content.find('tr.v4l2, tr.motioneye, tr.netcam, tr.mjpeg, tr.mmal').css('display', 'none');
+        content.find('tr.v4l2, tr.motioneye, tr.netcam, tr.mjpeg, tr.libcamera').css('display', 'none');
@@
-        else if (typeSelect.val() == 'mmal') {
-            content.find('tr.mmal').css('display', 'table-row');
-            addCameraInfo.html(
-		motionEyeI18n.t("Local MMAL cameras are devices that are connected directly to your motionEye system. These are usually board-specific cameras."));
+        else if (typeSelect.val() == 'libcamera') {
+            content.find('tr.libcamera').css('display', 'table-row');
+            addCameraInfo.html(
+		motionEyeI18n.t("Local CSI (libcamera) cameras are connected directly to your motionEye system."));
         }
@@
-            else if (typeSelect.val() == 'mmal') {
+            else if (typeSelect.val() == 'libcamera') {
                 data.path = addCameraSelect.val();
-                data.proto = 'mmal';
+                data.proto = 'libcamera';
             }
```

### C10: ffmpeg encoder detection fallback
```diff
diff --git a/motioneye/mediafiles.py b/motioneye/mediafiles.py
@@
     codecs = {}
     for line in lines:
@@
         codecs[codec] = {'encoders': encoders, 'decoders': decoders}
+
+    if not codecs or not any(v.get('encoders') for v in codecs.values()):
+        try:
+            enc_output = utils.call_subprocess(binary + ' -encoders -hide_banner', shell=True)
+            enc_output = utils.make_str(enc_output)
+        except subprocess.CalledProcessError:
+            enc_output = ''
+        for line in enc_output.split('\n'):
+            m = re.match(r'^ [A-Z.]{6} ([\\w_]+)\\s', line)
+            if not m:
+                continue
+            enc = m.group(1)
+            if enc.startswith('h264'):
+                codecs.setdefault('h264', {'encoders': set(), 'decoders': set()})['encoders'].add(enc)
+            elif enc.startswith(('hevc', 'h265')):
+                codecs.setdefault('hevc', {'encoders': set(), 'decoders': set()})['encoders'].add(enc)
```

### C11: Remove OMX default codec
```diff
diff --git a/motioneye/config/defaults.py b/motioneye/config/defaults.py
@@
-    elif motionctl.has_h264_omx_support():
-        # OMX is deprecated but still works on older setups
-        data.setdefault('movie_codec', 'mp4:h264_omx')
-
     else:
         data.setdefault('movie_codec', 'mp4')  # software fallback
```

### C12: Remove OMX options from UI
```diff
diff --git a/motioneye/templates/partials/settings/_movies.html b/motioneye/templates/partials/settings/_movies.html
@@
-                {% if has_h264_omx_support %}
-                <option value="mp4:h264_omx">H.264/OMX (.mp4)</option>
-                {% endif %}
@@
-                {% if has_h264_omx_support %}
-                <option value="mkv:h264_omx">Matroska Video/OMX (.mkv)</option>
-                {% endif %}
```

## Section D: Verification checklist
- `python3 -c "from motioneye import update; print(update.get_os_version())"` -> reports `Debian GNU/Linux 13` (or `trixie`) from `/etc/os-release`.
- `systemctl cat motioneye` -> `ExecStart=/usr/bin/env meyectl ...` and service starts without `linux_init` sed patching.
- `rpicam-hello --list-cameras` (or `libcamera-hello --list-cameras`) -> lists CSI cameras.
- `v4l2-ctl --list-devices` -> USB cameras still enumerated.
- `ffmpeg -hide_banner -encoders | rg "h264_v4l2m2m"` -> confirms HW encoder on Pi 4; OMX should be absent on 64-bit.
- UI: “Add Camera” dialog shows “Local CSI (libcamera)” and no MMAL option; movie formats show V4L2M2M when available and no OMX entries.

