# Auto-Brightness Feature Removal Plan

**Created:** 2025-12-16 15:00
**Status:** Ready for Implementation
**Scope:** Complete removal of non-functional `auto_brightness` feature from MotionEye

---

## Executive Summary

Remove the vestigial Automatic Brightness toggle and all associated backend code. This feature has been non-functional since Motion 5.0 removed the `auto_brightness` parameter. The UI misleads users into thinking they're controlling camera behavior when the setting is silently discarded by the adaptation layer.

**Impact:** Low-risk cleanup with backward compatibility for existing configs.

---

## Analysis Summary

### Current State
- **UI:** Fully implemented toggle with 17+ language translations
- **Backend:** Complete data flow that ultimately discards the value
- **Motion 5.0:** Parameter removed due to poor performance (brightness oscillation)
- **Effect:** Zero - setting has no impact on camera behavior

### Files Affected (23 total)

| Category | Count | Impact |
|----------|-------|--------|
| UI Templates | 2 | Remove toggle rows |
| JavaScript | 1 | Remove form handling |
| Python Backend | 4 | Remove data flow |
| Translations | 17 | Remove strings |
| Documentation | 5 | Update references |

---

## Implementation Plan

### Phase 1: UI Layer Removal

#### 1.1 Template Files

**File:** `motioneye/templates/partials/settings/_video_device.html`

**Action:** Remove lines 30-36 (entire toggle section)

```html
<!-- REMOVE THIS SECTION -->
<tr class="settings-item">
    <td class="settings-item-label"><span class="settings-item-label" data-i18n="Automatic Brightness">Automatic Brightness</span></td>
    <td class="settings-item-value"><input type="checkbox" class="styled device camera-config" id="autoBrightnessSwitch"></td>
    <td><span class="help-mark" data-i18n-title="enables software automatic brightness (only recommended for cameras without autobrightness)" title="enables software automatic brightness (only recommended for cameras without autobrightness)">?</span></td>
</tr>
<tr class="settings-item">
    <td colspan="100"><div class="settings-item-separator"></div></td>
</tr>
```

**Location:** Lines 30-36
**Risk:** Low - self-contained UI element

---

**File:** `motioneye/templates/main.html.backup`

**Action:** Same removal (lines 312-317) - or consider deleting entire backup file if obsolete

**Location:** Lines 312-317
**Risk:** None (backup file)

---

#### 1.2 JavaScript

**File:** `motioneye/static/js/main.js`

**Changes Required:**

**Line 1146** - Remove brightness slider insertion logic:
```javascript
// REMOVE THIS LINE
var prevTr = $('#autoBrightnessSwitch').parent().parent();
```
**Context:** This line positions the brightness slider. After removal, update to use a different anchor element (e.g., `$('#deviceTypeEntry')`).

**Line 2066** - Remove from form serialization:
```javascript
// REMOVE THIS LINE
'auto_brightness': $('#autoBrightnessSwitch')[0].checked,
```

**Line 2375** - Remove from form population:
```javascript
// REMOVE THIS LINE
$('#autoBrightnessSwitch')[0].checked = dict['auto_brightness']; markHideIfNull('auto_brightness', 'autoBrightnessSwitch');
```

**Risk:** Medium - requires testing form save/load still works correctly

---

### Phase 2: Backend Data Layer Removal

#### 2.1 Configuration Converters

**File:** `motioneye/config/camera/converters.py`

**Line 291** - Remove from `motion_camera_ui_to_dict()`:
```python
# REMOVE THIS LINE
'auto_brightness': ui['auto_brightness'],
```

**Line 849** - Remove from `motion_camera_dict_to_ui()`:
```python
# REMOVE THIS LINE
'auto_brightness': data.get('auto_brightness', False),  # Removed in Motion 5.0
```

**Risk:** Low - already stripped by adaptation layer

---

#### 2.2 Default Values

**File:** `motioneye/config/defaults.py`

**Lines 94-95** - Remove Motion 4.x default:
```python
# REMOVE THESE LINES
if not motionctl.is_motion_50():
    data.setdefault('auto_brightness', False)
```

**Risk:** Low - only affects new camera creation in Motion 4.x (if still supported)

---

#### 2.3 Adaptation Layer

**File:** `motioneye/config/adaptation.py`

**Line 208** - Remove from adaptation mapping:
```python
# REMOVE THIS LINE
'auto_brightness': None,
```

**Context:** This line actively strips `auto_brightness` from Motion 5.0 configs. After full removal, this becomes unnecessary.

**Risk:** Low - no-op removal

---

#### 2.4 Constants

**File:** `motioneye/config/camera/constants.py`

**Line 20** - Remove from `USED_MOTION_OPTIONS`:
```python
# REMOVE THIS LINE
'auto_brightness',
```

**Line 103** - Keep in `MOTION_50_REMOVED_PARAMS` (historical reference):
```python
# KEEP FOR DOCUMENTATION
MOTION_50_REMOVED_PARAMS = {
    'stream_port',
    'stream_localhost',
    'stream_auth_method',
    'stream_authentication',
    'auto_brightness',  # Keep this for historical reference
    'setup_mode',
}
```

**Risk:** None

---

### Phase 3: Translation Files

**Strategy:** Remove translations to reduce clutter, but low priority (harmless if left)

#### 3.1 English Base

**File:** `motioneye/locale/en/LC_MESSAGES/motioneye.po`

**Lines 321, 325** - Remove translation entries:
```po
# REMOVE THESE ENTRIES
msgstr "Automatic Brightness"
msgstr "enables software automatic brightness (only recommended for cameras without autobrightness)"
```

**Risk:** None - unused strings don't affect functionality

---

#### 3.2 JSON Translation Files (17 files)

**Files:**
- `motioneye/static/js/i18n/ar.json`
- `motioneye/static/js/i18n/bn.json`
- `motioneye/static/js/i18n/ca.json`
- `motioneye/static/js/i18n/cs.json`
- `motioneye/static/js/i18n/de.json`
- `motioneye/static/js/i18n/el.json`
- `motioneye/static/js/i18n/es.json`
- `motioneye/static/js/i18n/fi.json`
- `motioneye/static/js/i18n/fr.json`
- `motioneye/static/js/i18n/hi.json`
- `motioneye/static/js/i18n/it.json`
- `motioneye/static/js/i18n/ja.json`
- `motioneye/static/js/i18n/ko.json`
- `motioneye/static/js/i18n/ms.json`
- `motioneye/static/js/i18n/nb_NO.json`
- `motioneye/static/js/i18n/nl.json`
- `motioneye/static/js/i18n/pa.json`
- `motioneye/static/js/i18n/pl.json`
- `motioneye/static/js/i18n/pt.json`
- `motioneye/static/js/i18n/ro.json`
- `motioneye/static/js/i18n/ru.json`
- `motioneye/static/js/i18n/sk.json`
- `motioneye/static/js/i18n/sv.json`
- `motioneye/static/js/i18n/ta.json`
- `motioneye/static/js/i18n/tr.json`
- `motioneye/static/js/i18n/uk.json`
- `motioneye/static/js/i18n/zh.json`

**Action:** Remove two keys from each file:
```json
// REMOVE THESE TWO ENTRIES
"Automatic Brightness": "...",
"enables software automatic brightness (only recommended for cameras without autobrightness)": "..."
```

**Automation:** Consider using a script to process all files:
```python
import json
import glob

for filepath in glob.glob('motioneye/static/js/i18n/*.json'):
    with open(filepath, 'r') as f:
        data = json.load(f)

    data.pop('Automatic Brightness', None)
    data.pop('enables software automatic brightness (only recommended for cameras without autobrightness)', None)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

**Risk:** None

---

### Phase 4: Documentation Updates

#### 4.1 Summary Documents

**File:** `docs/summaries/motion-5.0-compatibility-implementation.md`

**Lines 19, 57, 93** - Update to reflect removal:

**Change:**
```markdown
- Parameters removed: `stream_localhost`, `stream_auth_method`, `stream_authentication`, `auto_brightness`, `setup_mode`
```

**To:**
```markdown
- Parameters removed: `stream_localhost`, `stream_auth_method`, `stream_authentication`, `auto_brightness` (removed from UI in MotionEye), `setup_mode`
```

**Risk:** None - documentation only

---

**File:** `docs/Update-Motion-MotionEye.md`

**Line 134** - Add note about UI removal:
```markdown
- `auto_brightness` - Removed UI toggle in MotionEye (parameter removed in Motion 5.0 due to oscillation issues)
```

---

#### 4.2 Handoff Documents

**File:** `docs/handoff-prompts/motion-5.0-compatibility.md`

**Lines 23, 73, 257** - Mark as removed in UI

---

#### 4.3 Scratchpad Notes

**File:** `docs/scratchpads/motion-build-pi5-steps.md`

**Line 118** - Update table entry to note UI removal

---

#### 4.4 Index Files

**File:** `docs/directories/main-html-index.md`

**Line 135** - Remove entry:
```markdown
| Auto Brightness | `autoBrightnessSwitch` | 313 | checkbox |
```

---

**File:** `docs/plans/main-html-split-plan-20251214-1430.md`

**Line 161** - Remove entry

---

### Phase 5: Backward Compatibility Handling

#### 5.1 Existing Camera Configs

**Scenario:** User has existing camera with `auto_brightness: true` in config

**Current Behavior:**
1. Config loaded with `auto_brightness` key present
2. Adaptation layer strips it before writing to Motion
3. UI receives value and populates (now-removed) checkbox

**After Removal:**
1. Config loaded with `auto_brightness` key present
2. **Converter will fail** due to missing UI field
3. Need migration strategy

---

**Solution 1: Silent Ignore (Recommended)**

Keep minimal handling in `motion_camera_dict_to_ui()`:

```python
# In converters.py line ~849
# Don't include auto_brightness in UI dict - UI element removed
# Silently ignore if present in config (backward compatibility)
```

Remove from UI dict, but don't error if present in Motion config. Old configs will naturally drop the key on next save.

**Risk:** Low - graceful degradation

---

**Solution 2: Explicit Migration**

Add to `adaptation.py`:

```python
def migrate_remove_auto_brightness(v, data):
    """Remove deprecated auto_brightness from old configs."""
    data.pop('auto_brightness', None)
    return {}

_MOTION_44_TO_50_OPTIONS_MAPPING = {
    # ... existing mappings ...
    'auto_brightness': migrate_remove_auto_brightness,
}
```

**Risk:** Low - explicit cleanup

---

**Recommended Approach:** Solution 1 (silent ignore)
- Simpler implementation
- No risk of data loss
- Old configs cleaned up naturally over time

---

#### 5.2 Form Validation

**File:** `motioneye/static/js/main.js`

**Line ~1146 Fix:** After removing `autoBrightnessSwitch`, brightness slider needs new anchor

**Current:**
```javascript
var prevTr = $('#autoBrightnessSwitch').parent().parent();
var brightnessRow = buildRangeRow('Brightness', ...);
prevTr.after(brightnessRow);  // Insert after auto-brightness toggle
```

**After Removal:**
```javascript
// Use framerate slider or device type as anchor instead
var prevTr = $('#framerateSlider').parent().parent();
var brightnessRow = buildRangeRow('Brightness', ...);
prevTr.after(brightnessRow);  // Insert after framerate slider
```

**Risk:** Medium - requires UI testing to ensure correct placement

---

### Phase 6: Testing Plan

#### 6.1 Unit Tests

No existing unit tests found for `auto_brightness`. Consider adding tests if removing backward compatibility handling.

---

#### 6.2 Integration Tests

**Test Case 1: New Camera Creation**
1. Add new camera via UI
2. Configure settings
3. Save
4. Verify no `auto_brightness` in generated Motion config
5. Verify no errors in motioneye.log

**Expected:** Clean config without `auto_brightness`

---

**Test Case 2: Existing Camera Migration**
1. Manually add `"auto_brightness": true` to camera config file
2. Restart MotionEye
3. Load camera in UI
4. Verify settings load correctly
5. Save settings
6. Verify `auto_brightness` removed from config

**Expected:** Graceful handling of old configs

---

**Test Case 3: Motion 4.x Backward Compatibility**
1. Test on system running Motion 4.x (if still supported)
2. Verify UI doesn't break
3. Verify settings save correctly

**Expected:** No regressions for Motion 4.x users (if supported)

---

#### 6.3 UI Testing

**Test:** Settings Panel Layout
1. Open Video Device settings section
2. Verify separator removed cleanly (no double separators)
3. Verify brightness/contrast sliders appear in correct position
4. Check on different browsers (Chrome, Firefox, Safari)

**Expected:** Clean visual layout without gaps or duplicates

---

**Test:** Form Save/Load
1. Configure camera settings
2. Save
3. Reload page
4. Verify all settings restored correctly (except auto_brightness)

**Expected:** No JavaScript errors in console

---

### Phase 7: Deployment Strategy

#### 7.1 Release Notes

Add to changelog:

```markdown
### Removed
- **Auto Brightness Toggle** - Removed non-functional UI toggle for software automatic brightness
  - Motion 5.0 removed the `auto_brightness` parameter due to oscillation issues
  - Existing configs will automatically drop this setting on next save
  - Use hardware auto-brightness or manual `libcam_brightness` slider instead
```

---

#### 7.2 Migration Guide

For users who relied on this feature (even though non-functional):

```markdown
## Migrating from Auto Brightness

The software auto-brightness toggle has been removed because:
1. Motion 5.0 removed support for this parameter
2. Feature caused brightness oscillation in testing
3. Modern cameras have superior hardware auto-brightness

### Alternatives:

**Option 1: Hardware Auto-Brightness (Recommended)**
- Most cameras have built-in auto-brightness
- Check camera documentation or V4L2 controls
- More stable than software implementation

**Option 2: Manual Brightness Control**
- For libcamera devices (Pi Camera), use the "Brightness" slider in Video Device settings
- Supports hot-reload (changes apply instantly)
- Range: -1.0 (darkest) to +1.0 (brightest)

**Option 3: V4L2 Controls**
- For USB cameras, use Extra Options to set V4L2 exposure controls
- Example: `v4l2_params "exposure_auto=1"`
```

---

#### 7.3 Rollout Plan

**Step 1:** Merge to development branch
**Step 2:** Test on Pi 5 with Motion 5.0
**Step 3:** Test on Motion 4.x system (if supported)
**Step 4:** Merge to beta branch for community testing
**Step 5:** Monitor for issues
**Step 6:** Release in next stable version

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing configs | Low | Silent ignore strategy |
| UI layout issues | Low | Visual testing on multiple browsers |
| JavaScript errors | Medium | Thorough testing of form save/load |
| Motion 4.x regression | Low | Test on 4.x system if supported |
| Translation sync issues | None | Automated script for JSON updates |

**Overall Risk:** Low - well-contained cleanup of non-functional feature

---

## Implementation Checklist

### Phase 1: UI Layer
- [ ] Remove toggle from `_video_device.html` (lines 30-36)
- [ ] Remove toggle from `main.html.backup` (lines 312-317) or delete file
- [ ] Update `main.js` line 1146 (brightness slider anchor)
- [ ] Remove from `main.js` line 2066 (form serialization)
- [ ] Remove from `main.js` line 2375 (form population)

### Phase 2: Backend
- [ ] Remove from `converters.py` line 291 (UI to dict)
- [ ] Remove from `converters.py` line 849 (dict to UI)
- [ ] Remove from `defaults.py` lines 94-95 (Motion 4.x default)
- [ ] Remove from `adaptation.py` line 208 (mapping)
- [ ] Remove from `constants.py` line 20 (USED_MOTION_OPTIONS)
- [ ] Keep in `constants.py` line 103 (MOTION_50_REMOVED_PARAMS)

### Phase 3: Translations
- [ ] Remove from `motioneye.po` (lines 321, 325)
- [ ] Run automated script to remove from 17 JSON files

### Phase 4: Documentation
- [ ] Update `motion-5.0-compatibility-implementation.md`
- [ ] Update `Update-Motion-MotionEye.md`
- [ ] Update `motion-5.0-compatibility.md` handoff
- [ ] Update `motion-build-pi5-steps.md`
- [ ] Update `main-html-index.md`
- [ ] Update `main-html-split-plan-20251214-1430.md`

### Phase 5: Testing
- [ ] Test new camera creation
- [ ] Test existing camera with auto_brightness in config
- [ ] Test UI layout (no gaps or double separators)
- [ ] Test form save/load functionality
- [ ] Test on multiple browsers
- [ ] Test on Pi 5 with Motion 5.0
- [ ] Test on Motion 4.x system (if applicable)

### Phase 6: Release
- [ ] Add changelog entry
- [ ] Create migration guide
- [ ] Merge to dev branch
- [ ] Community testing on beta
- [ ] Monitor for issues
- [ ] Release in stable

---

## Success Criteria

1. ✅ Auto Brightness toggle removed from UI
2. ✅ No JavaScript errors on settings page load/save
3. ✅ Existing configs with `auto_brightness` load without errors
4. ✅ New camera configs don't include `auto_brightness`
5. ✅ UI layout clean (no visual artifacts)
6. ✅ All existing tests pass
7. ✅ Documentation updated
8. ✅ No regressions in other settings

---

## Notes

### Why Not Keep for Motion 4.x?

Even though Motion 4.x still supports `auto_brightness`, we should remove it because:

1. **Poor functionality** - Known oscillation issues across all Motion versions
2. **Misleading UX** - Toggle implies reliable functionality
3. **Better alternatives** - Hardware auto-brightness, manual controls, V4L2 params
4. **Maintenance burden** - Carrying non-functional code forward
5. **User confusion** - "Why isn't auto brightness working?" support requests

### Alternative: Conditional Display

If Motion 4.x support is critical, could conditionally show toggle:

```html
<!-- Only show for Motion 4.x (not recommended due to poor quality) -->
<tr class="settings-item motion-4x-only">
    <td class="settings-item-label">
        <span class="settings-item-label" data-i18n="Automatic Brightness (Legacy)">
            Automatic Brightness (Legacy)
        </span>
    </td>
    <td class="settings-item-value">
        <input type="checkbox" class="styled device camera-config" id="autoBrightnessSwitch">
    </td>
    <td><span class="help-mark" data-i18n-title="Motion 4.x only. Known to cause oscillation. Use hardware auto-brightness instead." title="Motion 4.x only. Known to cause oscillation. Use hardware auto-brightness instead.">?</span></td>
</tr>
```

**Recommendation:** Full removal is cleaner.

---

## Open Questions

1. **Motion 4.x support status** - Is MotionEye still officially supporting Motion 4.x?
   - If yes: Consider conditional display with warnings
   - If no: Proceed with full removal

2. **Config migration strategy** - Should we actively remove `auto_brightness` from existing configs?
   - Current plan: Silent ignore (natural cleanup on save)
   - Alternative: Active migration on startup
   - **Recommendation:** Silent ignore (less intrusive)

3. **Backup file cleanup** - Should `main.html.backup` be deleted entirely?
   - Check git history for purpose
   - If obsolete, delete in this PR
   - If needed, update in sync with main template

---

## Related Issues

- Motion Project Issue #552: [Perform auto-brightness using V4L2_CID_EXPOSURE_ABSOLUTE](https://github.com/Motion-Project/motion/issues/552)
- MotionEye Issue #617: [RPi camera auto brightness not working](https://github.com/ccrisan/motioneye/issues/617)
- MotionEye Issue #1357: [Auto Brightness never settles to a stable state](https://github.com/ccrisan/motioneye/issues/1357)
- MotionPlus Discussion #125: [Missing the auto_brightness](https://github.com/Motion-Project/motionplus/discussions/125)

---

## Appendix: Complete File List

### Files to Modify (23)

**Templates (2):**
1. `motioneye/templates/partials/settings/_video_device.html`
2. `motioneye/templates/main.html.backup`

**JavaScript (1):**
3. `motioneye/static/js/main.js`

**Python (4):**
4. `motioneye/config/camera/converters.py`
5. `motioneye/config/defaults.py`
6. `motioneye/config/adaptation.py`
7. `motioneye/config/camera/constants.py`

**Translations (18):**
8. `motioneye/locale/en/LC_MESSAGES/motioneye.po`
9-25. `motioneye/static/js/i18n/*.json` (17 files)

**Documentation (5):**
26. `docs/summaries/motion-5.0-compatibility-implementation.md`
27. `docs/Update-Motion-MotionEye.md`
28. `docs/handoff-prompts/motion-5.0-compatibility.md`
29. `docs/scratchpads/motion-build-pi5-steps.md`
30. `docs/directories/main-html-index.md`

**Optional:**
31. `docs/plans/main-html-split-plan-20251214-1430.md`
32. `docs/handoff-prompts/HANDOFF-camera-control-exploration-20251208-1430.md`

### Files to Create (1)

**New Documentation:**
1. `docs/summaries/auto-brightness-removal-summary-YYYYMMDD-HHMM.md` (after implementation)

---

**End of Plan**
