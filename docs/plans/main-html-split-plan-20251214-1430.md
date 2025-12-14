# Plan: Split main.html into Partials

**Created**: 2024-12-14
**Status**: Planning
**Target File**: `motioneye/templates/main.html` (~1400 lines)

---

## Objective

Split the monolithic `main.html` template into logical partial files to improve:
- Developer experience (easier to find and edit sections)
- AI agent navigation (smaller, focused files)
- Git history clarity (isolated changes per feature area)
- Code maintainability (single responsibility per file)

---

## Proposed Directory Structure

```
motioneye/templates/
├── main.html                          # Slim orchestrator (~80 lines)
├── base.html                          # Unchanged
├── partials/
│   ├── _macros.html                   # Reusable macros
│   ├── _inline_scripts.html           # JavaScript initialization
│   ├── _header.html                   # Top navigation bar
│   ├── settings/
│   │   ├── _preferences.html          # User preferences
│   │   ├── _general.html              # General settings
│   │   ├── _video_device.html         # Camera device config
│   │   ├── _file_storage.html         # Storage & upload settings
│   │   ├── _text_overlay.html         # Text overlay settings
│   │   ├── _video_streaming.html      # Streaming settings
│   │   ├── _still_images.html         # Still image capture
│   │   ├── _movies.html               # Movie recording
│   │   ├── _motion_detection.html     # Motion detection config
│   │   ├── _notifications.html        # Email/Telegram/webhook notifications
│   │   ├── _working_schedule.html     # Weekly schedule
│   │   └── _additional_sections.html  # Dynamic camera_sections loop
│   ├── _page_container.html           # Main page wrapper & footer
│   ├── _frame_mode.html               # Embedded frame view
│   └── _modals.html                   # Modal & popup containers
```

---

## Detailed File Breakdown

### Phase 1: Core Infrastructure

#### 1.1 `partials/_macros.html`
**Source Lines**: 3-50
**Content**: `config_item` macro definition
**Dependencies**: None (imported by other partials)

```jinja2
{# Macro for rendering configuration items #}
{% macro config_item(config, depends="") -%}
    <tr class="settings-item additional-config"
    ...
{%- endmacro %}
```

**Notes**:
- Must be imported with `{% from %}` syntax, not `{% include %}`
- All settings partials depend on this macro

---

#### 1.2 `partials/_inline_scripts.html`
**Source Lines**: 72-116
**Content**: JavaScript variable initialization and i18n setup

**Variables defined**:
- `basePath`
- `userLang`
- `adminUsername`
- `frame`
- `hasLocalCamSupport`
- `hasNetCamSupport`
- `maskWidth`

**Dependencies**: Requires template context variables from Python

---

#### 1.3 `partials/_header.html`
**Source Lines**: 119-138
**Content**: Top navigation bar with settings button, camera selector, apply button

**Element IDs**:
- `cameraSelect`
- `remCameraButton`
- `applyButton`

**Conditional**: Wrapped in `{% if not frame %}`

---

### Phase 2: Settings Sections

#### 2.1 `partials/settings/_preferences.html`
**Source Lines**: 144-176
**Section ID**: `preferencesDiv`

**Element IDs**:
| ID | Type |
|----|------|
| `layoutColumnsSlider` | range |
| `fitFramesVerticallySwitch` | checkbox |
| `layoutRowsSlider` | range |
| `framerateDimmerSlider` | range |
| `resolutionDimmerSlider` | range |

**Dependencies**: None

---

#### 2.2 `partials/settings/_general.html`
**Source Lines**: 178-262
**Section ID**: `generalSectionDiv`

**Element IDs**:
| ID | Type |
|----|------|
| `langSelect` | select |
| `adminUsernameEntry` | text |
| `adminPasswordEntry` | password |
| `normalUsernameEntry` | text |
| `normalPasswordEntry` | password |
| `updateButton` | button |
| `shutDownButton` | button |
| `rebootButton` | button |
| `backupButton` | button |
| `restoreButton` | button |

**Dynamic Content**:
- `{% for config in main_sections.get('general', {}).get('configs', []) %}` (line 214)

**Dependencies**:
- `_macros.html` (for dynamic configs)
- Template variables: `version`, `motion_version`, `os_version`, `enable_update`, `enable_reboot`

---

#### 2.3 `partials/settings/_video_device.html`
**Source Lines**: 281-414
**Section ID**: `deviceSectionDiv`
**Toggle**: `videoDeviceEnabledSwitch`

**Element IDs** (25 total):
| ID | Type | Notes |
|----|------|-------|
| `videoDeviceEnabledSwitch` | checkbox | Section toggle |
| `deviceNameEntry` | text | |
| `deviceIdEntry` | text | readonly |
| `deviceUrlEntry` | text | readonly |
| `deviceTypeEntry` | text | readonly |
| `autoBrightnessSwitch` | checkbox | |
| `resolutionSelect` | select | |
| `customWidthEntry` | number | depends: resolution=custom |
| `customHeightEntry` | number | depends: resolution=custom |
| `rotationSelect` | select | |
| `framerateSlider` | range | |
| `autofocusModeSelect` | select | Pi Camera v3 |
| `autofocusRangeSelect` | select | depends: autofocusMode!=0 |
| `lensPositionSlider` | range | depends: autofocusMode=0 |
| `privacyMaskSwitch` | checkbox | |
| `privacyMaskEditButton` | button | |
| `privacyMaskSaveButton` | button | |
| `privacyMaskLinesEntry` | hidden | |
| `privacyMaskClearButton` | button | |
| `extraOptionsEntry` | textarea | |

**Dynamic Content**:
- `{% for config in camera_sections.get('device', {}).get('configs', []) %}` (line 411)

**Dependencies**: `_macros.html`

---

#### 2.4 `partials/settings/_file_storage.html`
**Source Lines**: 416-646
**Section ID**: `storageSectionDiv`

**Subsections**:
1. Storage Device (416-483)
2. Upload Settings (487-604)
3. Web Hook on Storage (608-631)
4. Command on Storage (633-642)

**Element IDs** (30+ total) - see main-html-index.md for complete list

**Dynamic Content**:
- `{% for config in camera_sections.get('storage', {}).get('configs', []) %}` (line 643)

**Dependencies**: `_macros.html`

---

#### 2.5 `partials/settings/_text_overlay.html`
**Source Lines**: 648-702
**Section ID**: `textOverlaySectionDiv`
**Toggle**: `textOverlayEnabledSwitch`

**Element IDs**:
| ID | Type |
|----|------|
| `textOverlayEnabledSwitch` | checkbox |
| `leftTextTypeSelect` | select |
| `leftTextEntry` | text |
| `rightTextTypeSelect` | select |
| `rightTextEntry` | text |
| `textScaleSlider` | range |

**Dynamic Content**:
- `{% for config in camera_sections.get('text-overlay', {}).get('configs', []) %}` (line 699)

**Dependencies**: `_macros.html`

---

#### 2.6 `partials/settings/_video_streaming.html`
**Source Lines**: 704-791
**Section ID**: `streamingSectionDiv`
**Toggle**: `videoStreamingEnabledSwitch`

**Element IDs**:
| ID | Type |
|----|------|
| `videoStreamingEnabledSwitch` | checkbox |
| `streamingFramerateSlider` | range |
| `streamingQualitySlider` | range |
| `streamingServerResizeSwitch` | checkbox |
| `streamingResolutionSlider` | range |
| `streamingPortEntry` | number |
| `streamingDirectModeSwitch` | checkbox |
| `streamingAuthModeSelect` | select |
| `streamingMotion` | checkbox |
| `streamingSnapshotUrlHtml` | html |
| `streamingMjpgUrlHtml` | html |
| `streamingEmbedUrlHtml` | html |

**Dynamic Content**:
- `{% for config in camera_sections.get('streaming', {}).get('configs', []) %}` (line 788)

**Dependencies**: `_macros.html`

---

#### 2.7 `partials/settings/_still_images.html`
**Source Lines**: 793-860
**Section ID**: `stillImagesSectionDiv`
**Toggle**: `stillImagesEnabledSwitch`

**Element IDs**:
| ID | Type |
|----|------|
| `stillImagesEnabledSwitch` | checkbox |
| `imageFileNameEntry` | text |
| `imageQualitySlider` | range |
| `captureModeSelect` | select |
| `snapshotIntervalEntry` | number |
| `preservePicturesSelect` | select |
| `picturesLifetimeEntry` | number |
| `manualSnapshotsSwitch` | checkbox |

**Dynamic Content**:
- `{% for config in camera_sections.get('still-images', {}).get('configs', []) %}` (line 857)

**Dependencies**: `_macros.html`

---

#### 2.8 `partials/settings/_movies.html`
**Source Lines**: 862-967
**Section ID**: `moviesSectionDiv`
**Toggle**: `moviesEnabledSwitch`

**Element IDs**:
| ID | Type |
|----|------|
| `moviesEnabledSwitch` | checkbox |
| `movieFileNameEntry` | text |
| `moviePassthroughSwitch` | checkbox |
| `movieFormatSelect` | select |
| `movieQualitySlider` | range |
| `recordingModeSelect` | select |
| `maxMovieLengthEntry` | number |
| `preserveMoviesSelect` | select |
| `moviesLifetimeEntry` | number |

**Conditional Options** (hardware encoder support):
- `has_h264_nvenc_support`
- `has_h264_nvmpi_support`
- `has_h264_qsv_support`
- `has_h264_omx_support`
- `has_h264_v4l2m2m_support`
- `has_hevc_nvenc_support`
- `has_hevc_nvmpi_support`
- `has_hevc_qsv_support`

**Dynamic Content**:
- `{% for config in camera_sections.get('movies', {}).get('configs', []) %}` (line 964)

**Dependencies**: `_macros.html`

---

#### 2.9 `partials/settings/_motion_detection.html`
**Source Lines**: 969-1088
**Section ID**: `motionDetectionSectionDiv`
**Toggle**: `motionDetectionEnabledSwitch`

**Subsections**:
1. Sensitivity Settings (976-1011)
2. Event Settings (1015-1034)
3. Mask Settings (1038-1071)
4. Debug Settings (1075-1084)

**Element IDs** (20 total) - see main-html-index.md for complete list

**Dynamic Content**:
- `{% for config in camera_sections.get('motion-detection', {}).get('configs', []) %}` (line 1085)

**Dependencies**: `_macros.html`

---

#### 2.10 `partials/settings/_notifications.html`
**Source Lines**: 1090-1267
**Section ID**: `notificationsSectionDiv`

**Subsections**:
1. Motion Start Actions header (1097-1103)
2. Email Notifications (1105-1153)
3. Telegram Notifications (1157-1180)
4. Motion Start Web Hook (1184-1205)
5. Motion Start Command (1209-1218)
6. Motion End Actions header (1222-1228)
7. Motion End Web Hook (1229-1250)
8. Motion End Command (1254-1263)

**Element IDs** (25+ total) - see main-html-index.md for complete list

**Dynamic Content**:
- `{% for config in camera_sections.get('notifications', {}).get('configs', []) %}` (line 1264)
- Note: Uses `config_item(config, "motionDetectionEnabled")` with extra depends

**Dependencies**:
- `_macros.html`
- All items depend on `motionDetectionEnabled`

---

#### 2.11 `partials/settings/_working_schedule.html`
**Source Lines**: 1269-1353
**Section ID**: `workingScheduleSectionDiv`
**Toggle**: `workingScheduleEnabledSwitch`
**Section Depends**: `motionDetectionEnabled`

**Element IDs**:
- 7 day switches: `mondayEnabledSwitch` through `sundayEnabledSwitch`
- 14 time entries: `mondayFromEntry`, `mondayToEntry`, etc.
- `workingScheduleTypeSelect`

**Dynamic Content**:
- `{% for config in camera_sections.get('working-schedule', {}).get('configs', []) %}` (line 1350)

**Dependencies**:
- `_macros.html`
- Section depends on `motionDetectionEnabled`

---

#### 2.12 `partials/settings/_additional_sections.html`
**Source Lines**: 1355-1371
**Content**: Loop for dynamic camera sections

```jinja2
{% for section in camera_sections.values() %}
{% if section.get('label') and section.get('configs') %}
<div class="settings-section-title">
    ...
</div>
<table class="settings">
    {% for config in section['configs'] %}
        {{config_item(config)}}
    {% endfor %}
</table>
{% endif %}
{% endfor %}
```

**Dependencies**: `_macros.html`

---

### Phase 3: Page Structure

#### 3.1 `partials/_page_container.html`
**Source Lines**: 1374-1380
**Content**: Page container div and footer

```jinja2
<div class="settings-progress"></div>
</form>
</div>
</div>
<img class="background-logo" src="{{static_path}}img/motioneye-logo.svg" onmousedown="return false;">
<div class="page-container"></div>
<div class="footer">
    <div class="copyright-note">copyright &copy; <a href="...">The motionEye Team</a></div>
</div>
</div>
```

---

#### 3.2 `partials/_frame_mode.html`
**Source Lines**: 1381-1391
**Conditional**: `{% else %}` branch (when `frame` is true)

**Content**: Minimal camera frame for embedding

```jinja2
<div class="camera-frame" id="camera{{camera_id}}"
    streaming_framerate="{{camera_config['stream_maxrate']}}"
    streaming_server_resize="{{camera_config['@webcam_server_resize']|string|lower}}"
    proto="{{camera_config['@proto']}}"
    url="{{camera_config['@url']}}">
    <div class="camera-container">
        <div class="camera-placeholder"><img class="no-camera" src="{{static_path}}img/no-camera.svg"></div>
        <img class="camera">
        <div class="camera-progress"><img class="camera-progress"></div>
    </div>
</div>
```

**Dependencies**: `camera_id`, `camera_config` template variables

---

#### 3.3 `partials/_modals.html`
**Source Lines**: 1392-1394
**Content**: Modal and popup containers

```jinja2
<div class="modal-glass"></div>
<div class="modal-container"></div>
<div class="popup-message-container"></div>
```

---

## New main.html Structure

After splitting, `main.html` becomes an orchestrator (~80 lines):

```jinja2
{% extends "base.html" %}
{% from "partials/_macros.html" import config_item with context %}

{% block title %}{% if title %}{{title}}{% else %}{{hostname}}{% endif %}{% endblock %}

{% block style %}
    {{super()}}
    <link rel="stylesheet" type="text/css" href="{{static_path}}css/ui.css?v={{version}}">
    <link rel="stylesheet" type="text/css" href="{{static_path}}css/main.css?v={{version}}">
    {% if frame %}
        <link rel="stylesheet" type="text/css" href="{{static_path}}css/frame.css?v={{version}}">
    {% endif %}
{% endblock %}

{% block script %}
    {{super()}}
    <script defer src="{{static_path}}js/ui.js?v={{version}}"></script>
    <script defer src="{{static_path}}js/main.js?v={{version}}"></script>
    {% if frame %}
        <script defer src="{{static_path}}js/frame.js?v={{version}}"></script>
    {% endif %}
{% endblock %}

{% block inline %}
    {{super()}}
    {% include "partials/_inline_scripts.html" %}
{% endblock %}

{% block body %}
    {% if not frame %}
        {% include "partials/_header.html" %}
        <div class="page">
            <div class="settings closed">
                <div class="settings-container">
                    <form autocomplete="new-password">
                        {% include "partials/settings/_preferences.html" %}
                        {% include "partials/settings/_general.html" %}

                        {# Additional Main Sections (dynamic) #}
                        {% for section in main_sections.values() %}
                        {% if section.get('label') and section.get('configs') %}
                        <div class="settings-section-title additional-section">
                            {% if section.get('onoff') %}<input type="checkbox" class="styled section additional-section {{section['name']}} main-config" id="{{section['name']}}Switch">{% endif %}
                            {% if section.get('description') %}<span class="help-mark" title="{{section['description']}}">?</span>{% endif %}
                            <a class="settings-section-title">{{section['label']}}</a>
                            <span class="minimize {% if section.get('open') %}open{% endif %}"></span>
                        </div>
                        <table class="settings">
                            {% for config in section['configs'] %}
                                {{config_item(config)}}
                            {% endfor %}
                        </table>
                        {% endif %}
                        {% endfor %}

                        {% include "partials/settings/_video_device.html" %}
                        {% include "partials/settings/_file_storage.html" %}
                        {% include "partials/settings/_text_overlay.html" %}
                        {% include "partials/settings/_video_streaming.html" %}
                        {% include "partials/settings/_still_images.html" %}
                        {% include "partials/settings/_movies.html" %}
                        {% include "partials/settings/_motion_detection.html" %}
                        {% include "partials/settings/_notifications.html" %}
                        {% include "partials/settings/_working_schedule.html" %}
                        {% include "partials/settings/_additional_sections.html" %}

                        <div class="settings-progress"></div>
                    </form>
                </div>
            </div>
            <img class="background-logo" src="{{static_path}}img/motioneye-logo.svg" onmousedown="return false;">
            <div class="page-container"></div>
            <div class="footer">
                <div class="copyright-note">copyright &copy; <a href="https://github.com/orgs/motioneye-project/people" target="_blank" rel="noopener">The motionEye Team</a></div>
            </div>
        </div>
    {% else %}
        {% include "partials/_frame_mode.html" %}
    {% endif %}
    {% include "partials/_modals.html" %}
{% endblock %}
```

---

## Implementation Order

### Step 1: Create Directory Structure
```bash
mkdir -p motioneye/templates/partials/settings
```

### Step 2: Extract Macros (No Dependencies)
1. Create `partials/_macros.html` with `config_item` macro
2. Test: Verify macro import works

### Step 3: Extract Leaf Partials (No Internal Includes)
Order by complexity (simplest first):
1. `partials/_modals.html` (3 lines)
2. `partials/_frame_mode.html` (11 lines)
3. `partials/settings/_preferences.html` (~32 lines)
4. `partials/settings/_text_overlay.html` (~55 lines)
5. `partials/settings/_working_schedule.html` (~85 lines)
6. `partials/settings/_still_images.html` (~68 lines)
7. `partials/settings/_movies.html` (~106 lines)
8. `partials/settings/_additional_sections.html` (~17 lines)

### Step 4: Extract Medium Complexity Partials
1. `partials/_inline_scripts.html` (~45 lines)
2. `partials/_header.html` (~20 lines)
3. `partials/settings/_general.html` (~85 lines)
4. `partials/settings/_video_streaming.html` (~88 lines)
5. `partials/settings/_motion_detection.html` (~120 lines)

### Step 5: Extract Complex Partials
1. `partials/settings/_video_device.html` (~134 lines)
2. `partials/settings/_file_storage.html` (~230 lines)
3. `partials/settings/_notifications.html` (~178 lines)

### Step 6: Assemble New main.html
1. Create new `main.html` with all includes
2. Remove extracted content from original

### Step 7: Testing
1. Visual comparison of rendered output
2. Verify all form elements work
3. Test on Pi 5

---

## Testing Strategy

### Pre-Implementation: Capture Baseline
```bash
# On Pi 5, capture rendered HTML
curl -u admin:password http://192.168.1.176:8765/ > baseline.html
```

### Post-Implementation: Compare
```bash
# After changes, capture new output
curl -u admin:password http://192.168.1.176:8765/ > new.html

# Diff (ignoring whitespace)
diff -w baseline.html new.html
```

### Functional Tests
1. Load main page - verify all sections render
2. Open each settings section - verify expand/collapse
3. Change a setting in each section - verify Apply works
4. Test frame mode embed URL
5. Test modal dialogs (add camera, etc.)

---

## Rollback Plan

Keep original `main.html` as `main.html.backup` until testing is complete.

If issues arise:
```bash
mv motioneye/templates/main.html.backup motioneye/templates/main.html
rm -rf motioneye/templates/partials/
```

---

## Documentation Updates

After successful implementation:
1. Update `docs/directories/main-html-index.md` to reference partials
2. Add partial file descriptions to index
3. Update line number references (now per-partial)

---

## Estimated File Sizes

| File | Estimated Lines |
|------|-----------------|
| `main.html` (new) | ~80 |
| `_macros.html` | ~48 |
| `_inline_scripts.html` | ~45 |
| `_header.html` | ~20 |
| `_preferences.html` | ~32 |
| `_general.html` | ~85 |
| `_video_device.html` | ~134 |
| `_file_storage.html` | ~230 |
| `_text_overlay.html` | ~55 |
| `_video_streaming.html` | ~88 |
| `_still_images.html` | ~68 |
| `_movies.html` | ~106 |
| `_motion_detection.html` | ~120 |
| `_notifications.html` | ~178 |
| `_working_schedule.html` | ~85 |
| `_additional_sections.html` | ~17 |
| `_frame_mode.html` | ~11 |
| `_modals.html` | ~3 |
| **Total** | **~1405** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Macro context not passed | Medium | High | Use `with context` in import |
| Missing template variable | Low | High | Test each partial individually |
| Whitespace differences | Medium | Low | Use `{%- -%}` for whitespace control |
| Performance regression | Very Low | Low | Jinja2 caches compiled templates |
| Git merge conflicts | Medium | Medium | Complete in single PR |

---

## Success Criteria

1. Rendered HTML output is byte-identical (excluding whitespace)
2. All UI functionality works identically
3. No increase in page load time
4. All 18 partial files created and working
5. main.html reduced to ~80 lines
6. Documentation updated
