# Motion 5.0 Video Format Cleanup Plan

**Created**: 2025-12-14 15:30
**Status**: Planning
**Priority**: Medium
**Complexity**: Low

---

## Overview

Motion 5.0 removed support for deprecated video containers and codecs. This plan addresses necessary cleanup in MotionEye to remove ALL references to unsupported formats and ensure UI consistency with Motion's current capabilities.

**Project Scope**: This project targets **fresh installations** on **Raspberry Pi 5** with **Pi Camera v3**. No backward compatibility or migration support for deprecated formats is required.

### Motion 5.0 Supported Formats

| Container | Codec      | Extension | Status |
|-----------|------------|-----------|--------|
| mov       | H.264      | .mov      | ✓ Supported |
| webm      | VP8        | .webm     | ✓ Supported |
| mp4       | H.264      | .mp4      | ✓ Supported |
| mkv       | H.264      | .mkv      | ✓ Supported |
| hevc      | H.265/HEVC | .mp4      | ✓ Supported |

### Deprecated Formats to Remove Completely

- **FLV** (Flash Video) - REMOVE all references
- **OGG/Theora** - REMOVE all references
- **AVI** - Already removed from Motion
- **SWF** - Minimal migration support only (map to MP4)

---

## Impact Analysis

### Files Requiring Changes

1. **UI Template** - `motioneye/templates/partials/settings/_movies.html`
   - Remove FLV option from dropdown
   - Impact: Users upgrading will no longer see deprecated format option

2. **Media Files Module** - `motioneye/mediafiles.py`
   - Remove `.flv` and `.ogg` from `_MOVIE_EXTS`
   - Remove FLV/OGG mappings from FFmpeg dictionaries
   - Impact: System will no longer recognize/process deprecated formats

3. **Legacy Migration** - `motioneye/config/adaptation.py`
   - Update `swf -> flv` mapping to `swf -> mp4`
   - Impact: Old SWF configs will migrate to MP4 instead of FLV

### Backward Compatibility - NOT REQUIRED

**Decision**: Remove all deprecated format support completely.

**Rationale**:
- Project targets fresh Pi 5 + Camera v3 installations
- No need to support legacy recordings or configurations
- Cleaner codebase without deprecated format cruft

**Migration Support**:
- Keep minimal legacy mapping in `adaptation.py` to prevent crashes if old configs are loaded
- Map deprecated formats to MP4 (safest, most compatible option)

---

## Implementation Plan

### Phase 1: UI Cleanup (Required)

**File**: `motioneye/templates/partials/settings/_movies.html`

**Current Code** (lines 21-26):
```html
<select class="styled movies camera-config" id="movieFormatSelect">
    <option value="mp4">H.264 (.mp4)</option>
    <option value="mkv">Matroska Video (.mkv)</option>
    <option value="mov">QuickTime (.mov)</option>
    <option value="flv">Flash Video (.flv)</option>  <!-- REMOVE -->
    <option value="webm">WebM VP8 (.webm)</option>
```

**Updated Code**:
```html
<select class="styled movies camera-config" id="movieFormatSelect">
    <option value="mp4">H.264 (.mp4)</option>
    <option value="mkv">Matroska Video (.mkv)</option>
    <option value="mov">QuickTime (.mov)</option>
    <option value="webm">WebM VP8 (.webm)</option>
    <option value="hevc">H.265/HEVC (.mp4)</option>
```

**Changes**:
- Remove `<option value="flv">Flash Video (.flv)</option>`
- Ensure `hevc` option is present (already exists in template)
- Verify hardware acceleration options (h264_omx, h264_v4l2m2m) remain intact

**Testing**:
- Verify dropdown renders correctly
- Confirm format selection persists across page reloads
- Test with existing camera configs using deprecated formats

---

### Phase 2: Media File Extensions - CLEAN REMOVAL

**File**: `motioneye/mediafiles.py`

**Current Code** (line 47):
```python
_MOVIE_EXTS = ['.mp4', '.mkv', '.mov', '.flv', '.webm', '.ogg']
```

**Updated Code**:
```python
_MOVIE_EXTS = ['.mp4', '.mkv', '.mov', '.webm']
```

**Changes**:
- Remove `.flv` completely
- Remove `.ogg` completely
- Keep only Motion 5.0 supported extensions

**Impact**:
- System will not list or recognize deprecated format files
- Cleaner, more maintainable codebase

---

### Phase 3: FFmpeg Mapping Cleanup

**File**: `motioneye/mediafiles.py`

**Current Code** (lines 51-91):

#### 3a. Codec Mapping
```python
FFMPEG_CODEC_MAPPING = {
    'mp4': 'h264',
    'mkv': 'h264',
    'mov': 'h264',
    'flv': 'flv1',      # REMOVE - deprecated
    'webm': 'vp8',
    'ogg': 'theora',    # REMOVE - deprecated
    'hevc': 'h265',
    'mp4:h264_omx': 'h264_omx',
    'mkv:h264_omx': 'h264_omx',
    'mp4:h264_v4l2m2m': 'h264_v4l2m2m',
    'mkv:h264_v4l2m2m': 'h264_v4l2m2m',
}
```

**Updated Code**:
```python
FFMPEG_CODEC_MAPPING = {
    'mp4': 'h264',
    'mkv': 'h264',
    'mov': 'h264',
    'webm': 'vp8',
    'hevc': 'h265',
    'mp4:h264_omx': 'h264_omx',
    'mkv:h264_omx': 'h264_omx',
    'mp4:h264_v4l2m2m': 'h264_v4l2m2m',
    'mkv:h264_v4l2m2m': 'h264_v4l2m2m',
}
```

#### 3b. Format Mapping
```python
FFMPEG_FORMAT_MAPPING = {
    'mp4': 'mp4',
    'mkv': 'matroska',
    'mov': 'mov',
    'flv': 'flv',        # REMOVE - deprecated
    'webm': 'webm',
    'ogg': 'ogg',        # REMOVE - deprecated
    'hevc': 'mp4',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'matroska',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'matroska',
}
```

**Updated Code**:
```python
FFMPEG_FORMAT_MAPPING = {
    'mp4': 'mp4',
    'mkv': 'matroska',
    'mov': 'mov',
    'webm': 'webm',
    'hevc': 'mp4',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'matroska',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'matroska',
}
```

#### 3c. Extension Mapping
```python
FFMPEG_EXT_MAPPING = {
    'mp4': 'mp4',
    'mkv': 'mkv',
    'mov': 'mov',
    'flv': 'flv',        # REMOVE - deprecated
    'webm': 'webm',
    'ogg': 'ogg',        # REMOVE - deprecated
    'hevc': 'mp4',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'mkv',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'mkv',
}
```

**Updated Code**:
```python
FFMPEG_EXT_MAPPING = {
    'mp4': 'mp4',
    'mkv': 'mkv',
    'mov': 'mov',
    'webm': 'webm',
    'hevc': 'mp4',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'mkv',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'mkv',
}
```

#### 3d. MIME Type Mapping
```python
MOVIE_EXT_TYPE_MAPPING = {
    'mp4': 'video/mp4',
    'mkv': 'video/x-matroska',
    'mov': 'video/quicktime',
    'flv': 'video/x-flv',        # REMOVE - deprecated
    'webm': 'video/webm',
    'ogg': 'video/ogg',          # REMOVE - deprecated
}
```

**Updated Code**:
```python
MOVIE_EXT_TYPE_MAPPING = {
    'mp4': 'video/mp4',
    'mkv': 'video/x-matroska',
    'mov': 'video/quicktime',
    'webm': 'video/webm',
}
```

**Note**: All deprecated format MIME types removed - no backward compatibility needed.

---

### Phase 4: Legacy Migration Update

**File**: `motioneye/config/adaptation.py`

**Current Code** (lines 166-192):
```python
_LEGACY_FORMAT_MAPPING = {
    'mpeg4': 'mp4',
    'msmpeg4': 'mp4',
    'swf': 'flv',       # ❌ FLV is now deprecated
    'ffv1': 'mkv',
}

def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0.

    Also migrates legacy formats that were removed in Motion 5.0:
    - mpeg4, msmpeg4 -> mp4
    - swf -> flv
    - ffv1 -> mkv
    """
    container = _LEGACY_FORMAT_MAPPING.get(v, v)
    return {'movie_container': container}
```

**Updated Code**:
```python
_LEGACY_FORMAT_MAPPING = {
    'mpeg4': 'mp4',
    'msmpeg4': 'mp4',
    'swf': 'mp4',        # ✓ Updated: swf -> mp4 (flv deprecated)
    'flv': 'mp4',        # ✓ Added: prevent crash if flv config loaded
    'ffv1': 'mkv',
    'ogg': 'mp4',        # ✓ Added: map ogg to mp4 (maximum compatibility)
}

def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0.

    Also migrates legacy formats that were removed in Motion 5.0:
    - mpeg4, msmpeg4 -> mp4
    - swf, flv, ogg -> mp4
    - ffv1 -> mkv

    Note: Minimal migration support only. Project targets fresh Pi 5 installs.
    """
    container = _LEGACY_FORMAT_MAPPING.get(v, v)
    return {'movie_container': container}
```

**Changes**:
- Update `'swf': 'flv'` to `'swf': 'mp4'`
- Add `'flv': 'mp4'` to prevent crashes
- Add `'ogg': 'mp4'` (MP4 chosen for maximum compatibility)
- Update docstring to clarify minimal migration support

**Migration Behavior**:
- All deprecated formats → `mp4` (safest, most compatible)
- Prevents crashes if old configs accidentally loaded
- No expectation of full backward compatibility

---

## Testing Strategy

### 1. Unit Tests
- [ ] Test legacy format migration in `motioneye/config/adaptation.py`
- [ ] Verify FFmpeg mapping dictionaries contain only supported formats
- [ ] Verify `_MOVIE_EXTS` contains only: `.mp4`, `.mkv`, `.mov`, `.webm`

### 2. Integration Tests
- [ ] Create camera config with each supported format
- [ ] Verify Motion process starts successfully
- [ ] Confirm recordings are created with correct extensions

### 3. UI Tests
- [ ] Verify dropdown contains only supported formats
- [ ] Test format selection persistence
- [ ] Verify existing configs display correctly

### 4. Migration Tests (Crash Prevention Only)
- [ ] Create test config with `movie_codec: flv` → verify migrates to `mp4`
- [ ] Test `movie_codec: ogg` → verify migrates to `mp4`
- [ ] Test `movie_codec: swf` → verify migrates to `mp4`
- [ ] Verify no crashes when deprecated formats encountered

### 5. Raspberry Pi 5 Testing
- [ ] Deploy to test Pi at `192.168.1.176`
- [ ] Test each video format with Pi Camera v3
- [ ] Verify recordings play correctly
- [ ] Check Motion process logs for errors

---

## Deployment Steps

### Pre-Deployment
1. Backup existing configs: `/etc/motioneye/`
2. Document current `movie_format` settings for all cameras
3. Create rollback plan

### Deployment
1. Update UI template (Phase 1)
2. Update mediafiles.py (Phases 2-3)
3. Update adaptation.py (Phase 4)
4. Restart MotionEye service
5. Verify existing cameras load correctly
6. Test new camera creation with each format

### Post-Deployment Validation
1. Check `/var/log/motioneye/` for errors
2. Verify all cameras streaming
3. Trigger motion events to test recording
4. Confirm recordings have correct format/extension

---

## Rollback Plan

If issues occur:
1. Restore backup config files
2. Restart MotionEye: `sudo systemctl restart motioneye`
3. Document failure mode for investigation

Files to restore:
- `/etc/motioneye/*.conf`
- `motioneye/templates/partials/settings/_movies.html`
- `motioneye/mediafiles.py`
- `motioneye/config/adaptation.py`

---

## Decisions Made

1. **Media File Extensions**: ✅ Remove completely - no backward compatibility
2. **MIME Type Mapping**: ✅ Remove deprecated formats completely
3. **Migration Target**: ✅ All deprecated formats → MP4 (maximum compatibility)
4. **Project Scope**: ✅ Fresh Pi 5 + Camera v3 installations only

---

## Documentation Updates

### Release Notes
Add to next release:
```markdown
## Video Format Support (Motion 5.0)

### Supported Formats
- MP4 (H.264)
- MKV (Matroska H.264)
- MOV (QuickTime H.264)
- WebM (VP8)
- HEVC (H.265)

### Removed Formats
- FLV (Flash Video) - completely removed
- OGG (Theora) - completely removed
- Legacy formats (mpeg4, msmpeg4, swf) - minimal migration support

**Note**: This version targets fresh Raspberry Pi 5 + Pi Camera v3 installations.
Legacy format support has been removed.
```

### User Documentation
- Update format selection guide
- Add troubleshooting section for deprecated formats
- Document hardware acceleration options (h264_omx, h264_v4l2m2m)

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Crash on legacy config load | Low | Low | Minimal migration support in adapter |
| User confusion about removed formats | Low | Low | Clear release notes, fresh install focus |
| Hardware-specific format issues | Medium | Low | Test all formats on Pi 5 before release |
| Incomplete removal of deprecated code | Low | Low | Systematic grep/review of all files |

---

## Success Criteria

- [ ] UI dropdown shows only Motion 5.0 supported formats (mp4, mkv, mov, webm, hevc)
- [ ] No FLV or OGG references in `_MOVIE_EXTS`
- [ ] All FFmpeg mappings cleaned of deprecated formats
- [ ] Legacy format migration maps to MP4 (crash prevention)
- [ ] No errors in Motion logs after format change
- [ ] Recordings created successfully in all supported formats
- [ ] All tests pass on Raspberry Pi 5 with Pi Camera v3
- [ ] No deprecated format code remains in production paths

---

## Timeline Estimate

- **Phase 1 (UI)**: 10 minutes
- **Phase 2 (Extensions)**: 5 minutes
- **Phase 3 (FFmpeg)**: 15 minutes
- **Phase 4 (Migration)**: 10 minutes
- **Testing**: 1 hour (focused on Pi 5)
- **Documentation**: 15 minutes

**Total**: ~2 hours (simplified by removing backward compatibility)

---

## Next Steps

1. ✅ User decisions confirmed - remove all deprecated formats
2. Implement Phase 1: UI template cleanup
3. Implement Phase 2: Media file extensions cleanup
4. Implement Phase 3: FFmpeg mapping cleanup
5. Implement Phase 4: Migration adapter updates
6. Run test suite
7. Deploy to Pi 5 at `192.168.1.176` for integration testing
8. Verify all video formats work with Pi Camera v3
9. Update documentation
10. Commit changes with detailed message

**Ready to proceed with implementation.**
