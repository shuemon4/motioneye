Nice, I like the “do it right from the start” approach 👌
Here’s a structured tasks list for a **Pi-5 + Camera v3 motion daemon** with an **in-process hardware H.264 encoder**.

I’ll break it into phases you can tackle one by one.

---

## Phase 0 – Foundations & Decisions

**0.1. Tech choices**

* Language: C++17 or C++20.
* Build system: CMake.
* Core libs:

  * `libcamera` (capture).
  * `libjpeg-turbo` (JPEG snapshots / MJPEG).
  * FFmpeg / libav* (`libavcodec`, `libavformat`, `libavutil`, `libswscale`) for H.264 (using `h264_v4l2m2m` hardware encoder).
  * Small HTTP server (e.g. civetweb or a single-file embedded HTTP lib).

**0.2. Dev environment**

* Configure a Pi 5 with Raspberry Pi OS Bookworm.
* Install dev packages:

  * `libcamera-dev`, `libjpeg-dev` (or `libjpeg-turbo-dev`), `libavcodec-dev`, `libavformat-dev`, `libavutil-dev`, `libswscale-dev`.
* Set up:

  * `cmake` + `ninja` or `make`.
  * Basic logging library (or just `spdlog` / your own logger).

**0.3. Repository skeleton**

* Create project structure:

  ```text
  /cmake/
  /src/
    main.cpp
    core/
    camera/
    motion/
    encoder/
    http/
    storage/
    util/
  /include/
  /config/
  /tests/
  CMakeLists.txt
  ```

* Initial CMake targets:

  * `pi_motion` (executable).
  * `pi_motion_core` (static lib with most code).

---

## Phase 1 – Configuration & Core Types

**1.1. Config model**

* Define a `Config` struct mirroring what you want (camera, motion, recording, http).
* Implement simple config loader:

  * Start with `.ini` or `.toml` via a minimal library.
  * Map to internal `Config` object.

**1.2. Core common types**

* `FrameMeta`, `Frame`, `GrayFrame`, `BoundingBox`, `MotionResult`, etc.
* Simple `EventBus` interface:

  * `publish(Event)` / `subscribe(EventType, callback)` (for now can be just a callback registry in memory).

**1.3. Logging & error handling**

* Central logger (severity levels, timestamps).
* Error codes / exceptions policy for fatal vs recoverable errors.

---

## Phase 2 – Camera Capture (PiCamV3 + libcamera)

**2.1. Camera abstraction**

* Define interface:

  ```cpp
  class IFrameSink {
  public:
      virtual void on_frame(const Frame&) = 0;
  };

  class ICamera {
  public:
      virtual bool init(const CameraConfig&) = 0;
      virtual bool start(IFrameSink* sink) = 0;
      virtual void stop() = 0;
  };
  ```

**2.2. PiCamV3 implementation**

* Implement `PiCamV3Capture`:

  * Discover libcamera cameras.
  * Select Pi camera (for now, assume first camera).
  * Configure video stream:

    * Resolution: 1920x1080.
    * Framerate: e.g. 25 fps.
    * Pixel format: YUV420.
  * Apply config from `CameraConfig` (rotation, HDR flag, AF mode later).

**2.3. Capture thread**

* Start libcamera pipeline:

  * Create request buffers.
  * Register a frame-completed callback.
* In your capture thread:

  * Wait on a queue of completed requests.
  * Wrap each buffer in `Frame`:

    * Attach `FrameMeta` (timestamp, exposure, gain, etc. if needed).
* Immediately produce:

  * Full-res YUV pointer for encoder.
  * Downscaled grayscale (e.g. using a simple nearest-neighbor downscale) into a separate buffer for motion engine.

**2.4. Frame buffer / ring buffer**

* Implement a bounded lock-free (or mutex-protected) ring buffer for:

  * Latest full-res frames.
  * Latest low-res gray frames.
* Define policies for dropping frames when consumer is slow.

**2.5. Minimal test**

* Write a `main_capture_test`:

  * Initialize `PiCamV3Capture`.
  * Print FPS and basic stats.
  * Optionally write raw frames to disk to confirm correctness.

---

## Phase 3 – Motion Detection Engine

**3.1. Interfaces**

* Define:

  ```cpp
  struct MotionParams { /* thresholds, decay, etc. */ };

  struct MotionResult {
      bool event_active;
      float score;
      std::vector<BoundingBox> boxes;
  };

  class IMotionDetector {
  public:
      virtual void configure(const MotionParams&) = 0;
      virtual MotionResult process_frame(const GrayFrame&, const FrameMeta&) = 0;
  };
  ```

**3.2. Simple algorithm implementation**

* Implement `RunningAverageMotionDetector`:

  * Keep a background frame (same size as gray frame).
  * Update background with EMA.
  * Compute abs difference, threshold to binary mask.
  * Optional morphology (fast 3x3 erode/dilate).
  * Compute score = number of motion pixels or area.
  * Derive bounding boxes (connected components, filtered by min area).

**3.3. Event logic**

* Implement hysteresis/event tracking:

  * Maintain state: `in_event`, `frames_above_threshold`, `frames_below_threshold`.
  * Start event when score > `start_threshold` for N frames.
  * End event when score < `end_threshold` for M frames.
* Emit events via EventBus:

  * `MotionEventStart`, `MotionEventUpdate`, `MotionEventEnd`.

**3.4. Motion thread**

* Create MotionEngine thread:

  * Pull low-res frames from ring buffer.
  * Run `IMotionDetector`.
  * Publish events and internal stats (score, etc.).
* Add simple logging: “MOTION START/END @ timestamp”.

**3.5. Test harness**

* `main_motion_test`:

  * Use live camera input.
  * Print motion scores, log events to stdout.
  * Tune default thresholds so it behaves sanely in your actual enclosure.

---

## Phase 4 – In-Process H.264 Encoder (Hardware, via FFmpeg)

**4.1. Encoder abstraction**

* Define:

  ```cpp
  class IRecorder {
  public:
      virtual void start_segment(const std::string& path,
                                 const VideoParams& params) = 0;
      virtual void push_frame(const Frame& frame) = 0;
      virtual void stop_segment() = 0;
  };
  ```

* `VideoParams`: width, height, fps, pixel format.

**4.2. Choose encoder backend**

* Use FFmpeg with `h264_v4l2m2m`:

  * Encodes using V4L2 hardware encoder but stays in-process.
* Work out your **pixel format pipeline**:

  * Camera gives YUV420.
  * Encoder expects YUV420P (usually compatible).
  * If needed, use `libswscale` to convert.

**4.3. Implement `H264Recorder` (FFmpeg layer)**

Inside `start_segment`:

* Initialize FFmpeg:

  * Create `AVFormatContext` for MP4/mov (e.g. "mp4").
  * Create `AVStream` for video.
  * Create and configure `AVCodecContext`:

    * Codec: `h264_v4l2m2m` (hardware).
    * Set width, height, time_base, framerate, bit rate.
  * Open codec.
  * Open file with `avformat_write_header`.

Inside `push_frame`:

* Map your `Frame` YUV planes to `AVFrame`:

  * Set `data[]`, `linesize[]`, `pts`.
  * If scaling needed, use `sws_scale`.
* Call `avcodec_send_frame` / `avcodec_receive_packet` in a loop.
* For each `AVPacket`, write with `av_interleaved_write_frame`.

Inside `stop_segment`:

* Flush encoder (`send_frame(NULL)`, drain packets).
* Write trailer with `av_write_trailer`.
* Close codec and format context, free resources.

**4.4. Timestamps & sync**

* Decide on your time base:

  * Use camera timestamps and convert to a frame counter or `AVRational`.
* Ensure `pts` increments according to FPS:

  * E.g. `pts = frame_index` with `time_base = {1, fps}`.

**4.5. Recorder thread**

* Recorders should not block motion or capture.
* Implement a `RecordingManager`:

  * Runs in its own thread.
  * Consumes a queue of `(Frame, Command)`:

    * Commands: `START(path, params)`, `STOP`, `FRAME(frame)`.
  * Internally manages `H264Recorder` instance.

**4.6. Test harness**

* `main_record_test`:

  * Capture frames from camera.
  * Feed EVERY frame to `RecordingManager` for N seconds.
  * Verify you get a playable MP4 with correct timing.

---

## Phase 5 – Event-Driven Recording & Pre/Post Buffers

**5.1. Pre/post buffer design**

* Implement an in-memory circular buffer for full-res frames:

  * Capacity = `pre_buffer_s * fps` frames.
* When not recording:

  * Keep pushing frames into this buffer (old frames overwritten).

**5.2. Event linkage**

* On `MotionEventStart`:

  * Instruct `RecordingManager` to `START` segment with new file path.
  * Immediately push previous N seconds from pre-buffer to recorder.
* While `event_active`:

  * Continue pushing new frames to recorder.
* On `MotionEventEnd`:

  * Keep pushing for `post_buffer_s` seconds.
  * After that, send `STOP` to recorder.

**5.3. Storage layout & retention**

* Implement `StorageManager`:

  * Generates file paths: `/var/lib/pi-motion/YYYY/MM/DD/HHMMSS_eventNN.mp4`.
  * Runs periodic cleanup:

    * Enforce `max_days` and `min_free_pct`.
    * Delete oldest segments first.

---

## Phase 6 – HTTP Server & Live View

**6.1. HTTP framework integration**

* Add an embedded HTTP server library.
* Start HTTP server in its own thread:

  * Bind to `Config.http.bind_address:port`.

**6.2. Status & control endpoints**

* `GET /api/v1/status`:

  * Motion state, FPS, disk usage, current segment.
* `GET /api/v1/config`:

  * Current config (read-only first).
* Later: `PUT /api/v1/config` for live reconfig.

**6.3. Snapshot endpoint**

* `GET /snapshot.jpg`:

  * Grabs the most recent full-res frame from the frame buffer.
  * Converts to JPEG using libjpeg.
  * Writes as HTTP response.

**6.4. MJPEG live view**

* `GET /live.mjpeg`:

  * HTTP multipart stream.
  * Loop:

    * Grab latest frame at fixed interval (e.g. 5–10 fps).
    * Encode to JPEG.
    * Write boundary + headers + JPEG data.
* Ensure this uses the **most recent** frame, not a queue, so you don’t lag.

---

## Phase 7 – Integration, Tuning & Hardening

**7.1. Configuration integration**

* Wire `Config` into all subsystems:

  * Camera (resolution, fps, HDR).
  * Motion (thresholds, decays, masks).
  * Recording (pre/post, bitrate).
  * HTTP (port, etc.).

**7.2. Metrics & logging**

* Counters:

  * Captured FPS.
  * Motion CPU load.
  * Encoder FPS, queue depth.
  * Disk usage.
* Log structure:

  * Motion events with timestamps.
  * Encoder start/stop and errors.
  * HTTP requests.

**7.3. Robust error handling**

* Handle camera disconnect or libcamera errors:

  * Try to restart camera.
  * Fail gracefully if restart fails.
* Handle encoder failures:

  * Abort current segment.
  * Optionally back off and log.

**7.4. Real-world tuning (your enclosure)**

* Tune motion parameters:

  * `downscale`, thresholds, half-life, event gaps.
* Test:

  * Lights on/off transitions.
  * Different subjects (people, animals, small vs large motion).
* Adjust HDR / exposure modes if needed.

---

## Phase 8 – Packaging & Future-Ready Work

**8.1. System integration**

* Create a systemd service unit:

  * Autostart on boot.
  * Restart policy on failure.
* Add CLI options:

  * `--config /path/to/config.ini`.
  * `--foreground` vs daemon mode.

**8.2. Packaging**

* CMake install rules.
* (Optional) Build a `.deb` package for easy re-install.

**8.3. Future extensions hooks**

* Keep interfaces generic so you can later:

  * Add multiple cameras (one `ICamera` per pipeline).
  * Add alternate motion algorithms (OpenCV-based, etc.).
  * Add additional codecs / storage backends.

---

If you’d like, next step I can:

* Turn **Phases 2–4** into a more detailed *class-by-class* layout (header prototypes, how data flows between them), or
* Start with a concrete **CMakeLists + minimal `PiCamV3Capture` skeleton** you can drop onto your Pi and iterate on.
