1. PC-side motion detection script (RTSP from Pi)

Concept:

Pi 5 + v3 NoIR: just streams H.264 (no motion detection, minimal disk writes).

PC: pulls RTSP, downscales, does:

Dual background models: lights ON vs lights OFF

“Lightswitch” detection (ignore big global brightness jumps)

Blob + temporal filtering

Optional event recording to disk

You said: 14 fps in dark, 30 fps in light works well on Pi 4 + v2.
We’ll keep that in mind and:

Let the Pi set those FPS per profile (later, via libcamera).

On the PC, we’ll:

Read whatever fps we get from the stream (best-effort),

Use time-based thresholds (seconds) as much as possible, so it still makes sense at 14 vs 30 fps.

Example script: motion_detector.py
import cv2
import numpy as np
import time
from collections import deque
from pathlib import Path

# ==== CONFIG ====
RTSP_URL = "rtsp://PI_IP_OR_HOST:8554/enclosure"  # replace with your Pi's stream URL

# Processing resolution (downscaled)
PROC_WIDTH = 320
PROC_HEIGHT = 180

# Brightness & lightswitch handling
BRIGHTNESS_ALPHA = 0.05      # smoothing factor for brightness average
BRIGHTNESS_JUMP = 25.0       # mean-intensity jump to treat as lightswitch
LIGHT_ON_THRESHOLD = 70.0    # mean intensity above this => "lights ON" mode

# Background model learning rates
BG_ALPHA_ON = 0.02           # slower learning when lights ON
BG_ALPHA_OFF = 0.05          # faster learning when lights OFF (noisier)
PIXEL_DIFF_THRESHOLD = 25    # per-pixel intensity threshold for motion mask

# Blob & temporal filtering
MIN_BLOB_AREA = 600          # pixels in the downscaled frame
MOTION_WINDOW_SEC = 1.0      # look back this many seconds
MOTION_MIN_SEC = 0.3         # require motion present for at least this long

# Recording
OUTPUT_DIR = Path("events")
OUTPUT_DIR.mkdir(exist_ok=True)
MIN_EVENT_SEC = 2.0          # minimum clip length
NO_MOTION_GRACE_SEC = 1.0    # keep recording this long after motion stops

# Pre-roll buffer (store some frames before motion starts)
PREROLL_SEC = 1.0

# =================


def open_capture(url: str):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open stream: {url}")
    # Best-effort FPS read; fallback if missing
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 15.0  # reasonable default
    return cap, fps


def resize_gray(frame):
    frame_small = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
    # light blur to reduce noise
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return gray


def main():
    cap, fps_est = open_capture(RTSP_URL)
    print(f"Opened stream with reported FPS: {fps_est:.2f}")

    bg_on = None
    bg_off = None
    brightness_avg = None
    lightswitch_frames_remaining = 0

    # For temporal filtering & recording
    motion_history = deque()  # list of (timestamp, has_motion)
    preroll_frames = deque()  # list of (frame_bgr, timestamp)

    is_recording = False
    last_motion_time = None
    event_start_time = None
    writer = None
    event_idx = 0

    # For fps estimation (runtime)
    last_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Stream read failed, exiting.")
            break

        now = time.time()
        dt = now - last_time
        last_time = now

        gray = resize_gray(frame)
        mean_intensity = float(gray.mean())

        # Initialize brightness_avg
        if brightness_avg is None:
            brightness_avg = mean_intensity

        # Update brightness_avg
        brightness_avg = (1 - BRIGHTNESS_ALPHA) * brightness_avg + BRIGHTNESS_ALPHA * mean_intensity

        # Detect "lightswitch" (sudden big global change)
        if abs(mean_intensity - brightness_avg) > BRIGHTNESS_JUMP:
            lightswitch_frames_remaining = int(0.5 * fps_est)  # ignore ~0.5s worth of frames
            # Force backgrounds to adapt quickly by resetting them
            bg_on = None
            bg_off = None
            print(f"[{time.strftime('%H:%M:%S')}] Lightswitch detected.")

        if lightswitch_frames_remaining > 0:
            lightswitch_frames_remaining -= 1
            has_motion = False
            # Track history (no motion during lightswitch)
            motion_history.append((now, has_motion))
            # drop old entries
            while motion_history and (now - motion_history[0][0]) > MOTION_WINDOW_SEC:
                motion_history.popleft()
            # Keep preroll buffer updated
            preroll_frames.append((frame.copy(), now))
            while preroll_frames and (now - preroll_frames[0][1]) > PREROLL_SEC:
                preroll_frames.popleft()
            # Show debug and skip motion logic
            cv2.imshow("frame", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        # Decide which mode we're in (lights on/off)
        mode = "on" if mean_intensity >= LIGHT_ON_THRESHOLD else "off"

        # Select/update background
        if mode == "on":
            if bg_on is None:
                bg_on = gray.astype(np.float32)
            # exponential moving average
            cv2.accumulateWeighted(gray, bg_on, BG_ALPHA_ON)
            bg = bg_on
        else:
            if bg_off is None:
                bg_off = gray.astype(np.float32)
            cv2.accumulateWeighted(gray, bg_off, BG_ALPHA_OFF)
            bg = bg_off

        # Compute motion mask
        diff = cv2.absdiff(gray, cv2.convertScaleAbs(bg))
        _, mask = cv2.threshold(diff, PIXEL_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

        # Morphology to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        # Find largest blob area
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = area

        has_motion = max_area >= MIN_BLOB_AREA

        # Update motion history
        motion_history.append((now, has_motion))
        while motion_history and (now - motion_history[0][0]) > MOTION_WINDOW_SEC:
            motion_history.popleft()

        # Determine if we have "sustained" motion in recent window
        recent_motion_time = sum(
            1 for t, m in motion_history if m
        ) / max(1, len(motion_history)) * MOTION_WINDOW_SEC  # rough approx
        sustained_motion = recent_motion_time >= MOTION_MIN_SEC

        # Update preroll buffer
        preroll_frames.append((frame.copy(), now))
        while preroll_frames and (now - preroll_frames[0][1]) > PREROLL_SEC:
            preroll_frames.popleft()

        # === Event recording logic ===
        if sustained_motion:
            last_motion_time = now
            if not is_recording:
                # Start new event
                event_idx += 1
                event_start_time = now
                ts_str = time.strftime("%Y%m%d_%H%M%S")
                out_path = OUTPUT_DIR / f"event_{ts_str}_{event_idx:03d}.mp4"

                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                # Use original frame size for recording
                h, w, _ = frame.shape
                writer = cv2.VideoWriter(str(out_path), fourcc, fps_est, (w, h))
                is_recording = True
                print(f"[{time.strftime('%H:%M:%S')}] Start recording {out_path}")

                # Write preroll
                for pf, _ in preroll_frames:
                    writer.write(pf)
        else:
            if is_recording and last_motion_time is not None:
                # If we've had no motion for NO_MOTION_GRACE_SEC and event at least MIN_EVENT_SEC, stop
                if (now - last_motion_time) > NO_MOTION_GRACE_SEC and (now - event_start_time) > MIN_EVENT_SEC:
                    print(f"[{time.strftime('%H:%M:%S')}] Stop recording")
                    is_recording = False
                    writer.release()
                    writer = None
                    event_start_time = None
                    last_motion_time = None

        # Write current frame if recording
        if is_recording and writer is not None:
            writer.write(frame)

        # === Debug display ===
        debug = frame.copy()
        # Draw a simple indicator
        color = (0, 255, 0) if has_motion else (0, 0, 255)
        cv2.circle(debug, (20, 20), 10, color, -1)
        text = f"mode={mode} mean={mean_intensity:4.1f} area={int(max_area)}"
        cv2.putText(debug, text, (40, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("frame", debug)
        cv2.imshow("mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    # Cleanup
    if writer is not None:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()


How this ties to your 14 fps / 30 fps idea:

You configure the Pi (via libcamera-vid or Picamera2) to run:

~14 fps profile for “lights off” (to reduce noise and bandwidth).

~30 fps profile for “lights on” (smooth motion where you have more light).

This script:

Treats time in seconds, not frames, for things like MOTION_WINDOW_SEC, MOTION_MIN_SEC, NO_MOTION_GRACE_SEC, so it’s robust whether the stream is 14 or 30 fps.

Uses a brightness threshold (LIGHT_ON_THRESHOLD) to decide which background model to update.

You can tune:

LIGHT_ON_THRESHOLD by looking at the debug text (mean intensity).

MIN_BLOB_AREA and PIXEL_DIFF_THRESHOLD from the “mask” view.

2. Future “calibration sweeper” for camera settings

Now for your calibration idea (which is excellent, by the way):

Goal: automatically explore camera settings (exposure, gain, AWB, etc.), capture an image at each point, and log settings + image so an AI can learn which combos work best for your environment (lights on/off, enclosure geometry, etc.).

A. High-level design

Phase 1 – Capture sessions on the Pi

Use Picamera2 (recommended for Pi 5 + Camera v3).

Define a grid of settings to sweep:

Exposure time (e.g. from 100 µs up to some max)

Analogue gain

AWB mode / gains

Noise reduction, contrast, saturation, sharpness

Maybe resolution and framerate

For each combination:

Apply settings

Wait a short settle time (e.g. 200–500 ms)

Capture a still

Store:

Image file

Metadata (JSON or CSV row) containing all settings + measured stats (mean brightness, histogram, etc.).

Phase 2 – Filter obviously bad combinations

On the Pi (or later on PC), compute:

Mean intensity

Percentage of pixels near 0 (black) or 255 (white)

Dynamic range (e.g., 1% and 99% histogram percentiles)

Drop or mark combos that:

Are “whiteout” (e.g., >95% pixels > 250)

Are “blackout” (e.g., >95% pixels < 5)

You mentioned “several settings into it within a specified tolerance”:

If you’re sweeping exposure upward and you hit three consecutive values that are “whiteout” → stop sweeping higher; you’ve clearly saturated.

Similarly if going downward and you hit three “blackout” values → stop going lower.

Phase 3 – AI optimization

Feed the dataset (images + metadata + your labels like “good”, “too dark”, “too bright”, “too noisy”) into an AI model to:

Learn a mapping from environment features → settings.

Potentially create a small “policy” that runs on the Pi: given a frame, choose settings.

That’s for later; for now we can build Phase 1–2 so you can start collecting data.

B. Example Pi-side calibration skeleton (Picamera2, Python)

This is not fully plug-and-play, but it shows the structure you’d want:

from picamera2 import Picamera2, Preview
import time
import json
from pathlib import Path
import numpy as np
import cv2

OUTPUT_DIR = Path("calibration_runs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Simple helper to classify exposure result
def analyze_image_stats(img_gray):
    mean = float(img_gray.mean())
    # fraction of pixels near extremes
    near_black = (img_gray < 5).mean()
    near_white = (img_gray > 250).mean()
    # percentiles
    p1, p99 = np.percentile(img_gray, [1, 99])
    return {
        "mean": mean,
        "near_black": float(near_black),
        "near_white": float(near_white),
        "p1": float(p1),
        "p99": float(p99),
    }


def is_blackout(stats, black_threshold=0.95):
    return stats["near_black"] >= black_threshold


def is_whiteout(stats, white_threshold=0.95):
    return stats["near_white"] >= white_threshold


def main():
    picam2 = Picamera2()
    config = picam2.create_still_configuration(
        main={"size": (1280, 720)},  # you can use calibration-specific size
        raw=None
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2.0)  # warm-up

    # Define sweeps (you will tune these based on your enclosure)
    # Values below are illustrative, not authoritative.
    exposure_times = [500, 1000, 2000, 4000, 8000, 16000, 32000, 64000]  # microseconds
    analogue_gains = [1.0, 2.0, 4.0, 8.0]
    awb_modes = ["auto", "tungsten", "fluorescent", "daylight", "cloudy"]

    # Track metadata in a single JSON file
    meta_path = OUTPUT_DIR / "calibration_meta.jsonl"
    meta_file = meta_path.open("w")

    # Example: loop (awb_mode -> gain -> exposure)
    for awb in awb_modes:
        print(f"=== AWB mode {awb} ===")
        # Set AWB mode
        controls = {"AwbMode": awb}
        picam2.set_controls(controls)
        time.sleep(0.5)

        for gain in analogue_gains:
            print(f"  -- Gain {gain} --")
            controls = {"AnalogueGain": gain}
            picam2.set_controls(controls)
            time.sleep(0.5)

            consecutive_whiteout = 0
            consecutive_blackout = 0

            for exp in exposure_times:
                print(f"    * Exposure {exp} us")
                controls = {"ExposureTime": exp}
                picam2.set_controls(controls)
                time.sleep(0.3)  # let exposure settle

                # Capture frame as numpy array
                frame = picam2.capture_array()
                # Convert to BGR if needed (Picamera2 often gives RGB)
                if frame.shape[2] == 3:
                    img_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                else:
                    img_bgr = frame

                img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                stats = analyze_image_stats(img_gray)

                # Decide if too bright / too dark
                whiteout = is_whiteout(stats)
                blackout = is_blackout(stats)

                if whiteout:
                    consecutive_whiteout += 1
                else:
                    consecutive_whiteout = 0

                if blackout:
                    consecutive_blackout += 1
                else:
                    consecutive_blackout = 0

                # Build a unique filename
                ts = time.strftime("%Y%m%d_%H%M%S")
                fname = f"awb_{awb}_gain_{gain:.1f}_exp_{exp}_{ts}.jpg"
                img_path = OUTPUT_DIR / fname
                cv2.imwrite(str(img_path), img_bgr)

                record = {
                    "file": fname,
                    "awb_mode": awb,
                    "analogue_gain": gain,
                    "exposure_us": exp,
                    "stats": stats,
                    "whiteout": whiteout,
                    "blackout": blackout,
                    "timestamp": ts,
                }
                meta_file.write(json.dumps(record) + "\n")
                meta_file.flush()

                print(f"      saved {fname} | mean={stats['mean']:.1f} "
                      f"wb={whiteout} bb={blackout}")

                # Early stopping in this sweep direction:
                # If we hit multiple consecutive whiteouts, no need to go higher.
                if consecutive_whiteout >= 3:
                    print("      too bright consecutively, stopping higher exposures for this gain/AWB.")
                    break
                if consecutive_blackout >= 3:
                    print("      too dark consecutively, stopping lower exposures for this gain/AWB.")
                    break

    meta_file.close()
    picam2.stop()
    print("Calibration sweep complete.")


if __name__ == "__main__":
    main()

C. Extra settings/options you might add

Later you can extend the sweep to include:

Resolution: higher vs lower, to trade detail vs noise and processing cost.

Frame rate: your 14 fps vs 30 fps profiles for motion detection; see how they affect noise & blur.

Noise reduction / sharpening:

E.g. Sharpness, Contrast, Saturation, Denoise controls.

IR vs visible lighting profiles:

Run separate sweeps with lights ON and OFF (and IR LEDs ON if you use them).

Region-of-interest (ROI):

You can test cropping to the “interesting” part of the enclosure for better auto-exposure there.

Each captured row in calibration_meta.jsonl becomes a sample for your future AI to learn “good vs bad” settings per lighting condition.