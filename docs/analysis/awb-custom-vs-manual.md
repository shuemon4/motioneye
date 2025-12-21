AWB Custom Mode vs Manual Controls

  Short Answer: AWB mode 7 (Custom) and manual colour controls are related but serve different purposes.
  You don't need to build separate UI for "Custom" - it's automatically implied when you set manual gains.

  How It Works

  1. AWB Enable (libcam_awb_enable): Master switch
    - true = Camera automatically adjusts white balance
    - false = Manual control enabled
  2. AWB Mode (libcam_awb_mode): Preset algorithms (when AWB enabled)
    - 0-6: Automatic presets (Auto, Incandescent, Tungsten, Fluorescent, Indoor, Daylight, Cloudy)
    - 7 (Custom): Tells libcamera to use manual ColourGains/ColourTemperature instead
  3. Manual Controls: The actual values
    - libcam_colour_gain_r (0.0-8.0)
    - libcam_colour_gain_b (0.0-8.0)
    - libcam_colour_temp (0-10000 Kelvin)

  Key Insight from Code (src/libcam.cpp:328, 740-743)

  // ColourGains and ColourTemperature typically require AwbEnable=false to take effect
  // Value of 0 for colour_temp/colour_gains means "don't set" (use automatic)

  if (pending_ctrls.colour_gain_r > 0.0f || pending_ctrls.colour_gain_b > 0.0f) {
      float cg[2] = {pending_ctrls.colour_gain_r, pending_ctrls.colour_gain_b};
      req_controls.set(controls::ColourGains, cg);
  }

  What Your UI Should Be

  Recommended UI Structure

  ┌─────────────────────────────────────┐
  │ White Balance                       │
  ├─────────────────────────────────────┤
  │ ○ Automatic                         │
  │   ├─ [ ] Auto                       │ ← awb_mode=0
  │   ├─ [ ] Incandescent               │ ← awb_mode=1
  │   ├─ [ ] Tungsten                   │ ← awb_mode=2
  │   ├─ [ ] Fluorescent                │ ← awb_mode=3
  │   ├─ [ ] Indoor                     │ ← awb_mode=4
  │   ├─ [ ] Daylight                   │ ← awb_mode=5
  │   └─ [ ] Cloudy                     │ ← awb_mode=6
  │                                      │
  │ ● Manual                             │ ← awb_enable=false
  │   Colour Temperature: [5500] K      │ ← libcam_colour_temp
  │   Red Gain:  [1.0] (0.0-8.0)        │ ← libcam_colour_gain_r
  │   Blue Gain: [1.0] (0.0-8.0)        │ ← libcam_colour_gain_b
  └─────────────────────────────────────┘

  Implementation Logic

  When AWB Enable is ON:
  - Show mode selector (0-6)
  - Hide/disable manual sliders
  - Set awb_enable=true, awb_mode=0-6

  When AWB Enable is OFF (Manual):
  - Hide mode selector
  - Show manual sliders (colour_temp, red gain, blue gain)
  - Set awb_enable=false
  - You DON'T need to explicitly set awb_mode=7 - libcamera will infer "Custom" when it sees manual gains
  with AWB disabled

  Critical Relationships

  | UI State             | Parameters Set                        | Effect                         |
  |----------------------|---------------------------------------|--------------------------------|
  | Auto mode selected   | awb_enable=true, awb_mode=0-6         | Camera uses preset algorithm   |
  | Manual mode selected | awb_enable=false, colour_gain_r/b set | Camera uses your manual values |
  | Manual with temp     | awb_enable=false, colour_temp set     | Camera converts temp to gains  |
  | Manual with gains    | awb_enable=false, colour_gain_r/b set | Direct gain control            |

  Example API Calls

  Automatic preset:
  curl "http://pi:8080/0/config/set?libcam_awb_enable=true&libcam_awb_mode=5"  # Daylight

  Manual control:
  # Set manual mode with specific gains
  curl
  "http://pi:8080/0/config/set?libcam_awb_enable=false&libcam_colour_gain_r=1.2&libcam_colour_gain_b=1.8"

  # OR set manual mode with colour temperature
  curl "http://pi:8080/0/config/set?libcam_awb_enable=false&libcam_colour_temp=5500"

  Summary

  You should build: Two-mode UI (Automatic vs Manual)
  - Automatic mode: Dropdown with 7 presets (0-6)
  - Manual mode: Sliders for colour temp OR red/blue gains

  You should NOT build: A separate "Custom" option - it's automatically implied by libcamera when you
  disable AWB and provide manual values.