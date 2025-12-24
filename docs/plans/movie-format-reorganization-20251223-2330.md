# Movie Format UI Reorganization & Platform-Aware Filtering

**Date:** 2025-12-23 23:30
**Status:** Planning → Implementation
**Priority:** Medium
**Complexity:** Moderate

## Problem Statement

The current movie format dropdown in the Movies settings section has several issues:

1. **Disorganized listing** - Codec types are mixed without clear grouping
2. **No platform awareness** - Shows all software codecs even when hardware alternatives exist
3. **Suboptimal defaults on Pi** - Users may not realize V4L2M2M is the best choice
4. **Code duplication** - Functions defined twice in `motionctl.py` (lines 469-596)
5. **Poor user experience** - No clear indication of which option is best for their hardware

### Current Format Options (Unsorted)
```
H.264 (.mp4)
Matroska Video (.mkv)
QuickTime (.mov)
WebM VP8 (.webm)
H.264/NVENC (.mp4)          [conditional]
H.264/V4L2M2M (.mp4)        [conditional]
HEVC (.mp4)
HEVC/NVENC (.mp4)           [conditional]
Matroska Video/V4L2M2M (.mkv) [conditional]
```

## Goals

1. **Reorganize UI** - Group by codec type (H.264, HEVC, VP8), then by container
2. **Platform detection** - Detect Raspberry Pi hardware reliably
3. **Smart filtering** - Hide inappropriate options on Pi (e.g., NVENC)
4. **User guidance** - Clear labels indicating hardware acceleration and recommendations
5. **Code cleanup** - Remove duplicate functions

## Technical Approach

### Phase 1: Hardware Detection

**File:** `motioneye/motionctl.py`

Add platform detection using multi-layer approach (most reliable → fallback):

```python
def detect_platform():
    """
    Detect if running on Raspberry Pi and which model.

    Returns:
        str: Platform identifier
            - 'pi5': Raspberry Pi 5
            - 'pi4': Raspberry Pi 4
            - 'pi': Generic Raspberry Pi (older models)
            - 'arm_unknown': ARM architecture but not confirmed Pi
            - 'generic': x86_64 or other architecture
    """
    # Layer 1: Device tree (most reliable for Pi)
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip('\x00')
            if 'Raspberry Pi' in model:
                if 'Pi 5' in model:
                    return 'pi5'
                elif 'Pi 4' in model:
                    return 'pi4'
                return 'pi'
    except (FileNotFoundError, IOError):
        pass

    # Layer 2: /proc/cpuinfo (fallback)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'Model' in line and 'Raspberry Pi' in line:
                    if 'Pi 5' in line:
                        return 'pi5'
                    elif 'Pi 4' in line:
                        return 'pi4'
                    return 'pi'
    except (FileNotFoundError, IOError):
        pass

    # Layer 3: Architecture hints
    import platform
    machine = platform.machine()
    if machine in ('aarch64', 'armv7l', 'armv8'):
        return 'arm_unknown'

    return 'generic'


def is_raspberry_pi():
    """
    Check if running on Raspberry Pi hardware.

    Returns:
        bool: True if confirmed Raspberry Pi, False otherwise
    """
    platform = detect_platform()
    return platform in ('pi5', 'pi4', 'pi')
```

**Testing on Pi:**
```bash
# Should return True on Pi 4/5
ssh admin@192.168.1.246 "python3 -c 'from motioneye import motionctl; print(motionctl.is_raspberry_pi())'"
ssh admin@192.168.1.176 "python3 -c 'from motioneye import motionctl; print(motionctl.is_raspberry_pi())'"
```

### Phase 2: Code Cleanup

**File:** `motioneye/motionctl.py`

**Action:** Remove duplicate function definitions (lines 539-596)

Functions are duplicated:
- `has_h264_nvenc_support()` - lines 479 and 539
- `has_h264_nvmpi_support()` - lines 489 and 549
- `has_hevc_nvmpi_support()` - lines 499 and 559
- `has_hevc_nvenc_support()` - lines 509 and 569
- `has_h264_qsv_support()` - lines 519 and 579
- `has_hevc_qsv_support()` - lines 529 and 589

Keep lines 469-536, remove lines 539-596.

### Phase 3: Template Context

**File:** `motioneye/handlers/main.py`

**Location:** Lines 55-61 (template context)

**Action:** Add platform detection to template context

```python
has_h264_v4l2m2m_support=motionctl.has_h264_v4l2m2m_support(),
has_h264_nvenc_support=motionctl.has_h264_nvenc_support(),
has_h264_nvmpi_support=motionctl.has_h264_nvmpi_support(),
has_hevc_nvenc_support=motionctl.has_hevc_nvenc_support(),
has_hevc_nvmpi_support=motionctl.has_hevc_nvmpi_support(),
has_h264_qsv_support=motionctl.has_h264_qsv_support(),
has_hevc_qsv_support=motionctl.has_hevc_qsv_support(),
is_raspberry_pi=motionctl.is_raspberry_pi(),  # NEW
platform_type=motionctl.detect_platform(),    # NEW
```

### Phase 4: UI Reorganization

**File:** `motioneye/templates/partials/settings/_movies.html`

**Location:** Lines 21-51 (movie format dropdown)

**New Structure:**

```html
<select class="styled movies camera-config" id="movieFormatSelect">
    <!-- H.264 Hardware Accelerated (Pi-specific) -->
    {% if is_raspberry_pi and has_h264_v4l2m2m_support %}
    <optgroup label="H.264 (Hardware - Recommended for Pi)">
        <option value="mp4:h264_v4l2m2m">H.264/V4L2M2M (.mp4)</option>
        <option value="mkv:h264_v4l2m2m">H.264/V4L2M2M (.mkv)</option>
    </optgroup>
    {% endif %}

    <!-- H.264 Hardware (NVIDIA) -->
    {% if has_h264_nvenc_support and not is_raspberry_pi %}
    <optgroup label="H.264 (NVIDIA Hardware)">
        <option value="mp4:h264_nvenc">H.264/NVENC (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- H.264 Hardware (Intel) -->
    {% if has_h264_qsv_support and not is_raspberry_pi %}
    <optgroup label="H.264 (Intel QuickSync)">
        <option value="mp4:h264_qsv">H.264/QSV (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- H.264 Hardware (Jetson) -->
    {% if has_h264_nvmpi_support and not is_raspberry_pi %}
    <optgroup label="H.264 (Jetson Hardware)">
        <option value="mp4:h264_nvmpi">H.264/NVMPI (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- H.264 Software (show on non-Pi, or Pi without V4L2M2M) -->
    {% if not is_raspberry_pi or not has_h264_v4l2m2m_support %}
    <optgroup label="H.264 (Software)">
        <option value="mp4">H.264 (.mp4)</option>
        <option value="mkv">H.264 (.mkv)</option>
        <option value="mov">H.264 (.mov)</option>
    </optgroup>
    {% endif %}

    <!-- HEVC Hardware (NVIDIA) -->
    {% if has_hevc_nvenc_support and not is_raspberry_pi %}
    <optgroup label="HEVC/H.265 (NVIDIA Hardware)">
        <option value="mp4:hevc_nvenc">HEVC/NVENC (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- HEVC Hardware (Jetson) -->
    {% if has_hevc_nvmpi_support and not is_raspberry_pi %}
    <optgroup label="HEVC/H.265 (Jetson Hardware)">
        <option value="mp4:hevc_nvmpi">HEVC/NVMPI (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- HEVC Hardware (Intel) -->
    {% if has_hevc_qsv_support and not is_raspberry_pi %}
    <optgroup label="HEVC/H.265 (Intel QuickSync)">
        <option value="mp4:hevc_qsv">HEVC/QSV (.mp4)</option>
    </optgroup>
    {% endif %}

    <!-- HEVC Software (always available via libx265) -->
    <optgroup label="HEVC/H.265 (Software)">
        <option value="hevc">HEVC (.mp4)</option>
    </optgroup>

    <!-- VP8/WebM -->
    <optgroup label="VP8">
        <option value="webm">VP8 (.webm)</option>
    </optgroup>
</select>
```

### Phase 5: Help Text Update

**File:** `motioneye/templates/partials/settings/_movies.html`

**Location:** Line 53

**Current:**
```html
sets the movie file format; not all formats are guaranteed to work on all systems; if in doubt, test each format and select the one that works best with your video player.
```

**New:**
```html
Sets the movie file format and encoder. Hardware-accelerated options (V4L2M2M, NVENC, QSV) provide better performance with lower CPU usage. Software encoders offer maximum compatibility but higher CPU usage. Recommended: Use hardware encoding when available.
```

## Implementation Order

1. ✅ **Add platform detection** (`motionctl.py`)
2. ✅ **Remove duplicate functions** (`motionctl.py` lines 539-596)
3. ✅ **Update template context** (`handlers/main.py`)
4. ✅ **Reorganize UI dropdown** (`templates/partials/settings/_movies.html`)
5. ✅ **Update help text** (`templates/partials/settings/_movies.html`)
6. ✅ **Test on Pi 4** (192.168.1.246)
7. ✅ **Test on Pi 5** (192.168.1.176)
8. ✅ **Verify non-Pi behavior** (development Mac - should show all options)

## Testing Strategy

### Test 1: Platform Detection
```bash
# On Pi 4
ssh admin@192.168.1.246 "python3 -c 'from motioneye import motionctl; print(\"Platform:\", motionctl.detect_platform()); print(\"Is Pi:\", motionctl.is_raspberry_pi())'"

# Expected output:
Platform: pi4
Is Pi: True

# On Pi 5
ssh admin@192.168.1.176 "python3 -c 'from motioneye import motionctl; print(\"Platform:\", motionctl.detect_platform()); print(\"Is Pi:\", motionctl.is_raspberry_pi())'"

# Expected output:
Platform: pi5
Is Pi: True
```

### Test 2: UI Rendering (Pi 4)
1. Deploy code to Pi 4
2. Access web UI: http://192.168.1.246:8765/
3. Navigate to camera settings → Movies section
4. Verify dropdown shows:
   - H.264 (Hardware - Recommended for Pi) group with V4L2M2M options
   - NO NVENC/QSV/NVMPI options (filtered out)
   - NO software H.264 options (V4L2M2M available)
   - HEVC (Software) group
   - VP8 group

### Test 3: UI Rendering (Pi 5)
1. Deploy code to Pi 5
2. Access web UI: http://192.168.1.176:8765/
3. Verify same behavior as Test 2

### Test 4: Codec Detection
```bash
# On Pi 4
ssh admin@192.168.1.246 "python3 -c 'from motioneye import motionctl; print(\"V4L2M2M:\", motionctl.has_h264_v4l2m2m_support()); print(\"NVENC:\", motionctl.has_h264_nvenc_support())'"

# Expected:
V4L2M2M: True
NVENC: False
```

### Test 5: Existing Configurations
- Cameras with existing `movie_codec` settings should continue working
- `mp4:h264_v4l2m2m` should remain selected if previously configured
- Legacy codecs should still function (handled by `config/adaptation.py`)

## Risk Assessment

**Low Risk Changes:**
- Adding detection functions (new code, doesn't affect existing)
- Removing duplicate functions (verified unused duplicates)
- Template reorganization (Jinja2 conditionals, no logic change)

**Medium Risk Changes:**
- Filtering options on Pi (could hide desired options)
  - **Mitigation:** Keep software fallbacks when hardware unavailable
  - **Mitigation:** Only filter on confirmed Pi detection

**Testing Requirements:**
- Must test on both Pi 4 and Pi 5
- Must verify non-Pi systems still work (use development Mac)
- Must verify existing configs don't break

## Success Criteria

1. ✅ Platform detection works on Pi 4, Pi 5, and generic systems
2. ✅ Duplicate functions removed without breaking functionality
3. ✅ UI shows organized codec groups
4. ✅ Pi users see only relevant options (V4L2M2M, not NVENC)
5. ✅ Non-Pi users see all applicable options
6. ✅ Hardware options labeled clearly
7. ✅ Existing camera configs continue working
8. ✅ Help text provides better guidance

## Rollback Plan

If issues occur:
1. Revert template changes (restore original dropdown)
2. Keep platform detection functions (harmless)
3. Keep duplicate function removal (cleanup)

Git commit structure:
- Commit 1: Add platform detection + remove duplicates
- Commit 2: UI reorganization
- Easy to revert Commit 2 if needed

## Future Enhancements

1. **Auto-select best codec** on first camera setup
2. **Performance indicators** (CPU usage estimates per codec)
3. **Codec testing utility** (test all available codecs)
4. **HEVC V4L2M2M support** (when ffmpeg adds Pi 5 HEVC hardware encoding)

## References

- ffmpeg codec detection: `motioneye/mediafiles.py:216-274`
- Current UI template: `motioneye/templates/partials/settings/_movies.html:21-51`
- Handler context: `motioneye/handlers/main.py:55-61`
- Codec mappings: `motioneye/mediafiles.py:52-80`
