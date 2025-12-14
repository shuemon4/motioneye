# main.html Navigation Index

**File**: `motioneye/templates/main.html`
**Purpose**: Primary UI template for MotionEye web interface
**Size**: ~1400 lines
**Type**: Jinja2 template extending `base.html`

---

## Quick Reference: Line Ranges

| Section | Lines | Element IDs |
|---------|-------|-------------|
| [Macro Definition](#macro-config_item) | 3-50 | `config_item` |
| [Style & Script Blocks](#style--script-blocks) | 54-116 | - |
| [Header Bar](#header-bar) | 119-138 | `cameraSelect`, `applyButton`, `remCameraButton` |
| [Preferences](#preferences-section) | 144-176 | `layoutColumnsSlider`, `fitFramesVerticallySwitch`, `framerateDimmerSlider`, `resolutionDimmerSlider` |
| [General Settings](#general-settings-section) | 178-262 | `langSelect`, `adminUsernameEntry`, `adminPasswordEntry`, `normalUsernameEntry`, `normalPasswordEntry` |
| [Video Device](#video-device-section) | 281-414 | `videoDeviceEnabledSwitch`, `deviceNameEntry`, `resolutionSelect`, `framerateSlider`, `autofocusModeSelect` |
| [File Storage](#file-storage-section) | 416-646 | `storageDeviceSelect`, `rootDirectoryEntry`, `uploadEnabledSwitch`, `webHookStorageEnabledSwitch` |
| [Text Overlay](#text-overlay-section) | 648-702 | `textOverlayEnabledSwitch`, `leftTextTypeSelect`, `rightTextTypeSelect`, `textScaleSlider` |
| [Video Streaming](#video-streaming-section) | 704-791 | `videoStreamingEnabledSwitch`, `streamingFramerateSlider`, `streamingPortEntry`, `streamingAuthModeSelect` |
| [Still Images](#still-images-section) | 793-860 | `stillImagesEnabledSwitch`, `imageFileNameEntry`, `captureModeSelect`, `preservePicturesSelect` |
| [Movies](#movies-section) | 862-967 | `moviesEnabledSwitch`, `movieFileNameEntry`, `movieFormatSelect`, `recordingModeSelect` |
| [Motion Detection](#motion-detection-section) | 969-1088 | `motionDetectionEnabledSwitch`, `frameChangeThresholdSlider`, `motionMaskSwitch` |
| [Motion Notifications](#motion-notifications-section) | 1090-1267 | `emailNotificationsEnabledSwitch`, `telegramNotificationsEnabledSwitch`, `webHookNotificationsEnabledSwitch` |
| [Working Schedule](#working-schedule-section) | 1269-1353 | `workingScheduleEnabledSwitch`, `mondayEnabledSwitch` - `sundayEnabledSwitch` |
| [Additional Sections](#additional-sections) | 1355-1371 | Dynamic from `camera_sections` |
| [Frame Mode](#frame-mode) | 1381-1391 | `camera-frame` |
| [Modal/Popup](#modalpopup-containers) | 1392-1394 | `modal-glass`, `modal-container`, `popup-message-container` |

---

## Detailed Section Breakdown

### Macro: config_item
**Lines**: 3-50
**Purpose**: Reusable macro for rendering configuration items in settings tables

Renders different input types based on `config['type']`:
- `str` - Text input
- `pwd` - Password input
- `number` - Numeric text input
- `range` - Slider input
- `bool` - Checkbox input
- `choices` - Dropdown select
- `html` - Custom HTML container
- `separator` - Visual divider

**Attributes handled**: `reboot`, `required`, `strip`, `depends`, `min`, `max`, `floating`, `sign`, `snap`, `ticks`, `ticksnum`, `decimals`, `unit`, `validate`

---

### Style & Script Blocks
**Lines**: 54-116

| Block | Lines | Content |
|-------|-------|---------|
| `{% block title %}` | 52 | Page title |
| `{% block style %}` | 54-61 | CSS imports: `ui.css`, `main.css`, `frame.css` |
| `{% block script %}` | 63-70 | JS imports: `ui.js`, `main.js`, `frame.js` |
| `{% block inline %}` | 72-116 | i18n setup, JavaScript variables |

**Key JavaScript Variables** (defined line 109-114):
- `adminUsername`
- `frame`
- `hasLocalCamSupport`
- `hasNetCamSupport`
- `maskWidth`

---

### Header Bar
**Lines**: 119-138
**CSS Class**: `.header`, `.settings-top-bar`

| Element | ID | Line | Purpose |
|---------|-----|------|---------|
| Settings button | `.settings-button` | 123 | Opens settings panel |
| Logout button | `.logout-button` | 124 | Switch user |
| Camera dropdown | `cameraSelect` | 125 | Camera selection |
| Remove camera | `remCameraButton` | 126 | Delete camera |
| Apply button | `applyButton` | 127 | Save changes |

---

### Preferences Section
**Lines**: 144-176
**Section ID**: `preferencesDiv`
**CSS Class**: `.settings-section-title`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Layout Columns | `layoutColumnsSlider` | 153 | range (1-4) |
| Fit Frames Vertically | `fitFramesVerticallySwitch` | 158 | checkbox |
| Layout Rows | `layoutRowsSlider` | 163 | range (1-4) |
| Frame Rate Dimmer | `framerateDimmerSlider` | 168 | range (0-100) |
| Resolution Dimmer | `resolutionDimmerSlider` | 173 | range (1-100) |

---

### General Settings Section
**Lines**: 178-262
**Section ID**: `generalSectionDiv`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Language | `langSelect` | 187 | select |
| Admin Username | `adminUsernameEntry` | 196 | text (readonly) |
| Admin Password | `adminPasswordEntry` | 201 | password |
| Surveillance Username | `normalUsernameEntry` | 206 | text |
| Surveillance Password | `normalPasswordEntry` | 211 | password |
| Version Info | - | 221-231 | display only |
| Software Update | `updateButton` | 235 | button |
| Shut Down | `shutDownButton` | 241 | button |
| Reboot | `rebootButton` | 246 | button |
| Backup | `backupButton` | 254 | button |
| Restore | `restoreButton` | 259 | button |

**Dynamic configs**: Line 214-216 (`main_sections.get('general')`)

---

### Video Device Section
**Lines**: 281-414
**Section ID**: `deviceSectionDiv`
**Toggle Switch**: `videoDeviceEnabledSwitch`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Camera Name | `deviceNameEntry` | 291 | text |
| Camera ID | `deviceIdEntry` | 296 | text (readonly) |
| Camera Device | `deviceUrlEntry` | 301 | text (readonly) |
| Camera Type | `deviceTypeEntry` | 306 | text (readonly) |
| Auto Brightness | `autoBrightnessSwitch` | 313 | checkbox |
| Resolution | `resolutionSelect` | 322 | select |
| Custom Width | `customWidthEntry` | 329 | number |
| Custom Height | `customHeightEntry` | 334 | number |
| Rotation | `rotationSelect` | 340 | select (0/90/180/270) |
| Frame Rate | `framerateSlider` | 351 | range (2-30) |
| **Autofocus Mode** | `autofocusModeSelect` | 357 | select |
| **Autofocus Range** | `autofocusRangeSelect` | 368 | select |
| **Focus Position** | `lensPositionSlider` | 378 | range (0-10) |
| Privacy Mask | `privacyMaskSwitch` | 386 | checkbox |
| Edit Mask | `privacyMaskEditButton` | 392 | button |
| Save Mask | `privacyMaskSaveButton` | 393 | button |
| Mask Lines | `privacyMaskLinesEntry` | 394 | hidden text |
| Clear Mask | `privacyMaskClearButton` | 400 | button |
| Extra Options | `extraOptionsEntry` | 408 | textarea |

**Note**: Autofocus controls (lines 354-380) are Pi Camera v3 specific additions.

---

### File Storage Section
**Lines**: 416-646
**Section ID**: `storageSectionDiv`

#### Storage Device (416-483)
| Setting | ID | Line |
|---------|-----|------|
| Storage Device | `storageDeviceSelect` | 426 |
| Network Server | `networkServerEntry` | 433 |
| SMB Version | `networkSMBVerSelect` | 439 |
| Share Name | `networkShareNameEntry` | 451 |
| Username | `networkUsernameEntry` | 456 |
| Share Password | `networkPasswordEntry` | 461 |
| Root Directory | `rootDirectoryEntry` | 466 |
| Test Share | `networkShareTestButton` | 471 |
| Disk Usage | `diskUsageProgressBar` | 480 |

#### Upload Settings (487-604)
| Setting | ID | Line |
|---------|-----|------|
| Upload Enabled | `uploadEnabledSwitch` | 489 |
| Upload Pictures | `uploadPictureSwitch` | 494 |
| Upload Movies | `uploadMovieSwitch` | 499 |
| Upload Service | `uploadServiceSelect` | 505 |
| Server Address | `uploadServerEntry` | 521 |
| Server Port | `uploadPortEntry` | 526 |
| Method | `uploadMethodSelect` | 532 |
| Endpoint URL | `uploadEndpointUrlEntry` | 541 |
| Location | `uploadLocationEntry` | 548 |
| Include Subfolders | `uploadSubfoldersSwitch` | 553 |
| Clean Cloud | `cleanCloudEnabledSwitch` | 558 |
| Username | `uploadUsernameEntry` | 563 |
| Password | `uploadPasswordEntry` | 568 |
| Auth Key | `uploadAuthorizationKeyEntry` | 573 |
| Authorize Link | `authorizeLinkHtml` | 579 |
| Access Key | `uploadAccessKeyEntry` | 587 |
| Secret Key | `uploadSecretKeyEntry` | 592 |
| Bucket | `uploadBucketEntry` | 597 |
| Test Service | `uploadTestButton` | 602 |

#### Web Hook (608-631)
| Setting | ID | Line |
|---------|-----|------|
| Web Hook Enabled | `webHookStorageEnabledSwitch` | 610 |
| Web Hook URL | `webHookStorageUrlEntry` | 615 |
| HTTP Method | `webHookStorageHttpMethodSelect` | 621 |

#### Command (633-642)
| Setting | ID | Line |
|---------|-----|------|
| Command Enabled | `commandStorageEnabledSwitch` | 635 |
| Command | `commandStorageEntry` | 640 |

---

### Text Overlay Section
**Lines**: 648-702
**Section ID**: `textOverlaySectionDiv`
**Toggle Switch**: `textOverlayEnabledSwitch`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Left Text Type | `leftTextTypeSelect` | 659 | select |
| Left Text Custom | `leftTextEntry` | 670 | text |
| Right Text Type | `rightTextTypeSelect` | 678 | select |
| Right Text Custom | `rightTextEntry` | 689 | text |
| Text Scale | `textScaleSlider` | 696 | range (1-10) |

---

### Video Streaming Section
**Lines**: 704-791
**Section ID**: `streamingSectionDiv`
**Toggle Switch**: `videoStreamingEnabledSwitch`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Streaming Frame Rate | `streamingFramerateSlider` | 714 | range (1-30) |
| Streaming Quality | `streamingQualitySlider` | 719 | range (0-100) |
| Server Resize | `streamingServerResizeSwitch` | 724 | checkbox |
| Streaming Resolution | `streamingResolutionSlider` | 729 | range (0-100) |
| Streaming Port | `streamingPortEntry` | 734 | number |
| Direct Streaming | `streamingDirectModeSwitch` | 739 | checkbox |
| Auth Mode | `streamingAuthModeSelect` | 745 | select |
| Motion Optimization | `streamingMotion` | 755 | checkbox |
| Snapshot URL | `streamingSnapshotUrlHtml` | 764 | link |
| Streaming URL | `streamingMjpgUrlHtml` | 773 | link |
| Embed URL | `streamingEmbedUrlHtml` | 782 | link |

---

### Still Images Section
**Lines**: 793-860
**Section ID**: `stillImagesSectionDiv`
**Toggle Switch**: `stillImagesEnabledSwitch`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Image File Name | `imageFileNameEntry` | 803 | text |
| Image Quality | `imageQualitySlider` | 808 | range (0-100) |
| Capture Mode | `captureModeSelect` | 814 | select |
| Snapshot Interval | `snapshotIntervalEntry` | 830 | number |
| Preserve Pictures | `preservePicturesSelect` | 836 | select |
| Picture Lifetime | `picturesLifetimeEntry` | 849 | number |
| Manual Snapshots | `manualSnapshotsSwitch` | 854 | checkbox |

---

### Movies Section
**Lines**: 862-967
**Section ID**: `moviesSectionDiv`
**Toggle Switch**: `moviesEnabledSwitch`

| Setting | ID | Line | Type |
|---------|-----|------|------|
| Movie File Name | `movieFileNameEntry` | 872 | text |
| Movie Passthrough | `moviePassthroughSwitch` | 877 | checkbox |
| Movie Format | `movieFormatSelect` | 883 | select |
| Movie Quality | `movieQualitySlider` | 927 | range (0-100) |
| Recording Mode | `recordingModeSelect` | 933 | select |
| Max Movie Length | `maxMovieLengthEntry` | 942 | number |
| Preserve Movies | `preserveMoviesSelect` | 948 | select |
| Movies Lifetime | `moviesLifetimeEntry` | 961 | number |

**Movie Format Options** (lines 884-921):
- Standard: mp4, mkv, mov, flv, webm, ogg, hevc
- Hardware accelerated (conditional): h264_nvenc, h264_nvmpi, h264_qsv, h264_omx, h264_v4l2m2m, hevc_nvenc, hevc_nvmpi, hevc_qsv

---

### Motion Detection Section
**Lines**: 969-1088
**Section ID**: `motionDetectionSectionDiv`
**Toggle Switch**: `motionDetectionEnabledSwitch`

#### Sensitivity Settings (976-1011)
| Setting | ID | Line |
|---------|-----|------|
| Frame Change Threshold | `frameChangeThresholdSlider` | 979 |
| Max Frame Change Threshold | `maxFrameChangeThresholdEntry` | 984 |
| Auto Threshold Tuning | `autoThresholdTuningSwitch` | 989 |
| Auto Noise Detection | `autoNoiseDetectSwitch` | 994 |
| Noise Level | `noiseLevelSlider` | 999 |
| Light Switch Detection | `lightSwitchDetectSlider` | 1004 |
| Despeckle Filter | `despeckleFilterSwitch` | 1009 |

#### Event Settings (1015-1034)
| Setting | ID | Line |
|---------|-----|------|
| Motion Gap | `eventGapEntry` | 1017 |
| Captured Before | `preCaptureEntry` | 1022 |
| Captured After | `postCaptureEntry` | 1027 |
| Minimum Motion Frames | `minimumMotionFramesEntry` | 1032 |

#### Mask Settings (1038-1071)
| Setting | ID | Line |
|---------|-----|------|
| Mask Enable | `motionMaskSwitch` | 1040 |
| Mask Type | `motionMaskTypeSelect` | 1046 |
| Smart Mask Sluggishness | `smartMaskSluggishnessSlider` | 1055 |
| Edit Mask | `motionMaskEditButton` | 1061 |
| Save Mask | `motionMaskSaveButton` | 1062 |
| Mask Lines | `motionMaskLinesEntry` | 1063 |
| Clear Mask | `motionMaskClearButton` | 1069 |

#### Debug Settings (1075-1084)
| Setting | ID | Line |
|---------|-----|------|
| Show Frame Changes | `showFrameChangesSwitch` | 1077 |
| Create Debug Media | `createDebugMediaSwitch` | 1082 |

---

### Motion Notifications Section
**Lines**: 1090-1267
**Section ID**: `notificationsSectionDiv`

#### Email Notifications (1105-1153)
| Setting | ID | Line |
|---------|-----|------|
| Email Enabled | `emailNotificationsEnabledSwitch` | 1106 |
| Email Addresses | `emailAddressesEntry` | 1111 |
| SMTP Server | `smtpServerEntry` | 1116 |
| SMTP Port | `smtpPortEntry` | 1121 |
| SMTP Account | `smtpAccountEntry` | 1126 |
| SMTP Password | `smtpPasswordEntry` | 1131 |
| From Address | `emailFromEntry` | 1136 |
| Use TLS | `smtpTlsSwitch` | 1141 |
| Picture Time Span | `emailPictureTimeSpanEntry` | 1146 |
| Test Email | `emailTestButton` | 1151 |

#### Telegram Notifications (1157-1180)
| Setting | ID | Line |
|---------|-----|------|
| Telegram Enabled | `telegramNotificationsEnabledSwitch` | 1159 |
| API Token | `telegramAPIEntry` | 1164 |
| Chat ID | `telegramCIDEntry` | 1169 |
| Picture Time Span | `telegramPictureTimeSpanEntry` | 1174 |
| API Info Button | `apiInstructionButton` | 1178 |
| Test Button | `telegramTestButton` | 1179 |

#### Motion Start Web Hook (1184-1205)
| Setting | ID | Line |
|---------|-----|------|
| Web Hook Enabled | `webHookNotificationsEnabledSwitch` | 1186 |
| Web Hook URL | `webHookNotificationsUrlEntry` | 1191 |
| HTTP Method | `webHookNotificationsHttpMethodSelect` | 1197 |

#### Motion Start Command (1209-1218)
| Setting | ID | Line |
|---------|-----|------|
| Command Enabled | `commandNotificationsEnabledSwitch` | 1211 |
| Command | `commandNotificationsEntry` | 1216 |

#### Motion End Web Hook (1229-1250)
| Setting | ID | Line |
|---------|-----|------|
| Web Hook Enabled | `webHookEndNotificationsEnabledSwitch` | 1231 |
| Web Hook URL | `webHookEndNotificationsUrlEntry` | 1236 |
| HTTP Method | `webHookEndNotificationsHttpMethodSelect` | 1242 |

#### Motion End Command (1254-1263)
| Setting | ID | Line |
|---------|-----|------|
| Command Enabled | `commandEndNotificationsEnabledSwitch` | 1256 |
| Command | `commandEndNotificationsEntry` | 1261 |

---

### Working Schedule Section
**Lines**: 1269-1353
**Section ID**: `workingScheduleSectionDiv`
**Toggle Switch**: `workingScheduleEnabledSwitch`
**Depends on**: `motionDetectionEnabled`

| Day | Enable ID | From ID | To ID | Line |
|-----|-----------|---------|-------|------|
| Monday | `mondayEnabledSwitch` | `mondayFromEntry` | `mondayToEntry` | 1278-1285 |
| Tuesday | `tuesdayEnabledSwitch` | `tuesdayFromEntry` | `tuesdayToEntry` | 1286-1294 |
| Wednesday | `wednesdayEnabledSwitch` | `wednesdayFromEntry` | `wednesdayToEntry` | 1295-1303 |
| Thursday | `thursdayEnabledSwitch` | `thursdayFromEntry` | `thursdayToEntry` | 1304-1312 |
| Friday | `fridayEnabledSwitch` | `fridayFromEntry` | `fridayToEntry` | 1313-1321 |
| Saturday | `saturdayEnabledSwitch` | `saturdayFromEntry` | `saturdayToEntry` | 1322-1330 |
| Sunday | `sundayEnabledSwitch` | `sundayFromEntry` | `sundayToEntry` | 1331-1339 |

| Setting | ID | Line |
|---------|-----|------|
| Schedule Type | `workingScheduleTypeSelect` | 1343 |

---

### Additional Sections
**Lines**: 1355-1371

Dynamic sections rendered from `camera_sections` dictionary. Each section with a `label` and `configs` array is rendered using the `config_item` macro.

---

### Frame Mode
**Lines**: 1381-1391
**Condition**: `{% if frame %}`

Minimal camera frame view for embedding, contains:
- `camera-frame` div with streaming attributes
- `camera-container` with placeholder and image elements
- `camera-progress` indicator

**Attributes on frame div**:
- `streaming_framerate`
- `streaming_server_resize`
- `proto`
- `url`

---

### Modal/Popup Containers
**Lines**: 1392-1394

| Element | CSS Class | Purpose |
|---------|-----------|---------|
| Glass overlay | `modal-glass` | Darkens background |
| Modal container | `modal-container` | Dialog boxes |
| Popup container | `popup-message-container` | Toast messages |

---

## CSS Classes Reference

### Configuration Classes
- `.main-config` - Main/global configuration items
- `.camera-config` - Per-camera configuration items
- `.prefs` - User preference items (stored in cookies)

### Section Classes
- `.settings-section-title` - Section header
- `.settings-item` - Individual setting row
- `.settings-item-label` - Setting name
- `.settings-item-value` - Setting input
- `.settings-item-separator` - Visual divider
- `.additional-config` - Dynamically loaded config

### Input Classes
- `.styled` - Styled input element
- `.number` - Numeric input
- `.range` - Slider input
- `.time` - Time input

### Category Classes (for config items)
- `.general` - General settings
- `.device` - Video device settings
- `.storage` - File storage settings
- `.text-overlay` - Text overlay settings
- `.streaming` - Video streaming settings
- `.still-images` - Still image settings
- `.movies` - Movie settings
- `.motion-detection` - Motion detection settings
- `.notifications` - Notification settings
- `.working-schedule` - Schedule settings

---

## Dependency System

Settings can depend on other settings using the `depends` attribute:
- `depends="settingName"` - Show when checkbox is checked
- `depends="!settingName"` - Show when checkbox is unchecked
- `depends="settingName=value"` - Show when setting equals value
- `depends="settingName=(val1|val2)"` - Show when setting matches any value
- Multiple conditions: `depends="cond1 cond2"` - AND logic

---

## i18n System

Two i18n systems are used:
1. **Legacy gettext.js** (line 75) - For JavaScript strings in `main.js`
2. **Client-side motionEyeI18n** (line 77) - For HTML `data-i18n` attributes

Translation attributes:
- `data-i18n="Key"` - Translate element text content
- `data-i18n-title="Key"` - Translate element title attribute

---

## Template Variables

Variables passed from Python backend:
- `title`, `hostname` - Page identification
- `version`, `motion_version`, `os_version` - Version info
- `settings` - User settings (includes `lingvo`, `langlist`)
- `admin_username` - Admin user name
- `frame` - Boolean for frame-only mode
- `has_motion` - Motion daemon availability
- `mask_width` - Mask editor grid width
- `enable_reboot`, `enable_update` - Feature flags
- `add_remove_cameras` - Permission flag
- `static_path` - Static file URL prefix
- `main_sections`, `camera_sections` - Dynamic config sections
- `camera_id`, `camera_config` - Frame mode camera data
- Hardware support flags: `has_h264_nvenc_support`, `has_h264_omx_support`, etc.
