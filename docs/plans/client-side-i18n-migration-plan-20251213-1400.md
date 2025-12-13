# Client-Side Internationalization Migration Plan

**Date**: 2025-12-13
**Status**: Ready for Implementation
**Goal**: Move all translations to client-side with English as source language

---

## Executive Summary

Migrate MotionEye from server-side Esperanto-based gettext to client-side English-based i18n. This offloads translation processing from the Pi to the client browser and makes English the default language (no translation needed for English users).

---

## Current State Analysis

### Translation Systems
| System | Location | Count | Format |
|--------|----------|-------|--------|
| Server-side (Jinja2) | `main.html` | 396 calls | `{{ _("Esperanto") }}` |
| Client-side (JS) | `main.js` | 139 calls | `i18n.gettext("Esperanto")` |
| Server locale files | `locale/*/motioneye.po` | 32 locales | gettext .po/.mo |
| Client locale files | `static/js/motioneye.*.json` | 32 locales | JSON |

### Problems with Current System
1. Esperanto as source language is non-standard and confusing
2. English users still require translation lookup
3. Server-side rendering loads Pi CPU for every page request
4. Two separate translation systems to maintain
5. New strings require updating .po files and regenerating .mo

---

## Target Architecture

### Design Principles
1. **English as source** - HTML/JS written in plain English
2. **Client-side only** - All translation happens in browser
3. **Single system** - One JSON-based translation mechanism
4. **Lazy loading** - Only load translation file for non-English users
5. **Graceful fallback** - Missing translations show English (not broken)

### New Translation Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                         SERVER (Pi)                              │
├─────────────────────────────────────────────────────────────────┤
│  main.html (English source)                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ <span data-i18n="Autofocus Mode">Autofocus Mode</span>      ││
│  │ <span data-i18n="settings">settings</span>                  ││
│  └─────────────────────────────────────────────────────────────┘│
│  No translation processing - just serves static HTML             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       CLIENT (Browser)                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Page loads with English text visible immediately             │
│  2. Check user's language preference                             │
│  3. If not English: fetch /static/js/i18n/{lang}.json           │
│  4. Translate all [data-i18n] elements                          │
│  5. Translate all JS strings via i18n.t("key")                  │
└─────────────────────────────────────────────────────────────────┘
```

### New File Structure
```
motioneye/
├── static/js/
│   ├── i18n.js              # New lightweight i18n library
│   └── i18n/                # New translation directory
│       ├── de.json          # German translations
│       ├── es.json          # Spanish translations
│       ├── fr.json          # French translations
│       └── ...              # Other languages
├── templates/
│   └── main.html            # English source, data-i18n attributes
└── locale/                  # DEPRECATED - can be removed after migration
```

### Translation JSON Format
```json
{
  "Autofocus Mode": "Autofokus-Modus",
  "Autofocus Range": "Autofokus-Bereich",
  "Focus Position": "Fokusposition",
  "Manual": "Manuell",
  "Continuous": "Kontinuierlich",
  "settings": "Einstellungen",
  "Apply": "Anwenden"
}
```

---

## Implementation Plan

### Phase 1: Infrastructure (Day 1)
**Create the new i18n system alongside existing one**

#### 1.1 Create lightweight i18n library
File: `motioneye/static/js/i18n.js`

```javascript
/**
 * Lightweight client-side i18n for MotionEye
 * - English is source language (no translation file needed)
 * - Translations loaded on-demand for non-English users
 * - Falls back to English if translation missing
 */
(function(window) {
    'use strict';

    var translations = {};
    var currentLang = 'en';
    var loaded = false;

    var i18n = {
        /**
         * Initialize i18n with user's language preference
         * @param {string} lang - Language code (e.g., 'de', 'fr', 'es')
         * @param {function} callback - Called when ready
         */
        init: function(lang, callback) {
            currentLang = lang || 'en';

            // English needs no translation file
            if (currentLang === 'en') {
                loaded = true;
                if (callback) callback();
                return;
            }

            // Load translation file for other languages
            var xhr = new XMLHttpRequest();
            xhr.open('GET', basePath + 'static/js/i18n/' + currentLang + '.json', true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        try {
                            translations = JSON.parse(xhr.responseText);
                        } catch (e) {
                            console.warn('i18n: Failed to parse translations for ' + currentLang);
                            translations = {};
                        }
                    } else {
                        console.warn('i18n: No translations found for ' + currentLang);
                    }
                    loaded = true;
                    if (callback) callback();
                }
            };
            xhr.send();
        },

        /**
         * Translate a string
         * @param {string} key - English source string
         * @returns {string} Translated string or original if not found
         */
        t: function(key) {
            if (currentLang === 'en' || !translations[key]) {
                return key;
            }
            return translations[key];
        },

        /**
         * Translate all elements with data-i18n attribute
         */
        translatePage: function() {
            if (currentLang === 'en') return; // No translation needed

            var elements = document.querySelectorAll('[data-i18n]');
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                var key = el.getAttribute('data-i18n');
                var translated = this.t(key);

                // Handle different element types
                if (el.tagName === 'INPUT' && el.type === 'text') {
                    if (el.placeholder) el.placeholder = translated;
                } else if (el.tagName === 'OPTION') {
                    el.textContent = translated;
                } else {
                    el.textContent = translated;
                }
            }

            // Translate title attributes (tooltips)
            var titled = document.querySelectorAll('[data-i18n-title]');
            for (var j = 0; j < titled.length; j++) {
                var tel = titled[j];
                tel.title = this.t(tel.getAttribute('data-i18n-title'));
            }
        },

        /**
         * Get current language
         */
        getLanguage: function() {
            return currentLang;
        },

        /**
         * Check if translations are loaded
         */
        isReady: function() {
            return loaded;
        }
    };

    window.i18n = i18n;
})(window);
```

#### 1.2 Create translation extraction script
File: `scripts/extract-translations.py`

```python
#!/usr/bin/env python3
"""
Extract English strings from main.html and main.js for translation.
Generates a template JSON that translators can use.
"""

import re
import json
from pathlib import Path

def extract_html_strings(html_path):
    """Extract strings from data-i18n attributes."""
    content = html_path.read_text()
    # Match data-i18n="..."
    pattern = r'data-i18n="([^"]+)"'
    return set(re.findall(pattern, content))

def extract_js_strings(js_path):
    """Extract strings from i18n.t('...') calls."""
    content = js_path.read_text()
    # Match i18n.t('...') or i18n.t("...")
    pattern = r"i18n\.t\(['\"]([^'\"]+)['\"]\)"
    return set(re.findall(pattern, content))

def main():
    base = Path(__file__).parent.parent / 'motioneye'

    html_strings = extract_html_strings(base / 'templates' / 'main.html')
    js_strings = extract_js_strings(base / 'static' / 'js' / 'main.js')

    all_strings = sorted(html_strings | js_strings)

    # Generate template (English -> empty for translators to fill)
    template = {s: "" for s in all_strings}

    output = base / 'static' / 'js' / 'i18n' / 'template.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(template, indent=2, ensure_ascii=False))

    print(f"Extracted {len(all_strings)} strings to {output}")

if __name__ == '__main__':
    main()
```

#### 1.3 Create migration script for existing translations
File: `scripts/migrate-translations.py`

```python
#!/usr/bin/env python3
"""
Migrate existing .po translations to new JSON format.
Maps Esperanto->Target to English->Target using English .po as bridge.
"""

import json
import re
from pathlib import Path

def parse_po_file(po_path):
    """Parse .po file into dict of msgid -> msgstr."""
    content = po_path.read_text(encoding='utf-8')
    translations = {}

    # Simple .po parser (handles multiline strings)
    msgid = None
    msgstr = None

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('msgid "'):
            msgid = line[7:-1]
        elif line.startswith('msgstr "'):
            msgstr = line[8:-1]
            if msgid and msgstr:
                translations[msgid] = msgstr
            msgid = None
            msgstr = None
        elif line.startswith('"') and line.endswith('"'):
            # Continuation line
            if msgstr is not None:
                msgstr += line[1:-1]
            elif msgid is not None:
                msgid += line[1:-1]

    return translations

def migrate_locale(locale_dir, english_map, output_dir):
    """Migrate a single locale from .po to .json."""
    lang = locale_dir.name
    po_file = locale_dir / 'LC_MESSAGES' / 'motioneye.po'

    if not po_file.exists():
        return

    # Parse the target language .po
    target_translations = parse_po_file(po_file)

    # Build English -> Target mapping
    # english_map: Esperanto -> English
    # target_translations: Esperanto -> Target
    # We want: English -> Target

    new_translations = {}
    for esperanto, english in english_map.items():
        if esperanto in target_translations and target_translations[esperanto]:
            target = target_translations[esperanto]
            if english and target:  # Both must be non-empty
                new_translations[english] = target

    if new_translations:
        output_file = output_dir / f'{lang}.json'
        output_file.write_text(
            json.dumps(new_translations, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        print(f"Migrated {lang}: {len(new_translations)} strings")

def main():
    base = Path(__file__).parent.parent / 'motioneye'
    locale_base = base / 'locale'
    output_dir = base / 'static' / 'js' / 'i18n'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse English .po to get Esperanto -> English mapping
    english_po = locale_base / 'en' / 'LC_MESSAGES' / 'motioneye.po'
    english_map = parse_po_file(english_po)

    print(f"Loaded {len(english_map)} English translations")

    # Migrate each locale
    for locale_dir in locale_base.iterdir():
        if locale_dir.is_dir() and locale_dir.name != 'en':
            migrate_locale(locale_dir, english_map, output_dir)

if __name__ == '__main__':
    main()
```

---

### Phase 2: HTML Migration (Day 2-3)
**Convert main.html from server-side to client-side translation**

#### 2.1 Pattern transformations

| Before (Esperanto + Jinja2) | After (English + data-i18n) |
|-----------------------------|-----------------------------|
| `{{ _("Aŭtofokusa Reĝimo") }}` | `<span data-i18n="Autofocus Mode">Autofocus Mode</span>` |
| `title="{{ _("agordojn") }}"` | `data-i18n-title="settings" title="settings"` |
| `<option>{{ _("Mana") }}</option>` | `<option data-i18n="Manual">Manual</option>` |

#### 2.2 Conversion script
File: `scripts/convert-html.py`

```python
#!/usr/bin/env python3
"""
Convert main.html from Jinja2 _() to data-i18n attributes.
Uses English .po file to map Esperanto -> English.
"""

import re
from pathlib import Path

def load_english_translations(po_path):
    """Load Esperanto -> English mapping from .po file."""
    content = po_path.read_text(encoding='utf-8')
    translations = {}

    msgid = None
    msgstr_lines = []
    in_msgstr = False

    for line in content.split('\n'):
        if line.startswith('msgid "'):
            if msgid and msgstr_lines:
                translations[msgid] = ''.join(msgstr_lines)
            msgid = line[7:-1]
            msgstr_lines = []
            in_msgstr = False
        elif line.startswith('msgstr "'):
            msgstr_lines.append(line[8:-1])
            in_msgstr = True
        elif line.startswith('"') and in_msgstr:
            msgstr_lines.append(line[1:-1])
        elif line.startswith('"') and msgid is not None:
            msgid += line[1:-1]

    if msgid and msgstr_lines:
        translations[msgid] = ''.join(msgstr_lines)

    return translations

def convert_inline_text(match, translations):
    """Convert {{ _("text") }} to data-i18n span."""
    esperanto = match.group(1)
    english = translations.get(esperanto, esperanto)
    return f'<span data-i18n="{english}">{english}</span>'

def convert_title_attr(match, translations):
    """Convert title="{{ _("text") }}" to data-i18n-title."""
    esperanto = match.group(1)
    english = translations.get(esperanto, esperanto)
    return f'data-i18n-title="{english}" title="{english}"'

def convert_option(match, translations):
    """Convert <option>{{ _("text") }}</option>."""
    esperanto = match.group(1)
    english = translations.get(esperanto, esperanto)
    return f'data-i18n="{english}">{english}<'

def main():
    base = Path(__file__).parent.parent / 'motioneye'

    # Load translations
    po_path = base / 'locale' / 'en' / 'LC_MESSAGES' / 'motioneye.po'
    translations = load_english_translations(po_path)
    print(f"Loaded {len(translations)} translations")

    # Read HTML
    html_path = base / 'templates' / 'main.html'
    content = html_path.read_text(encoding='utf-8')
    original = content

    # Convert patterns
    # 1. Inline text: {{ _("text") }} -> <span data-i18n="...">...</span>
    # But NOT inside attributes

    # 2. Title attributes: title="{{ _("text") }}"
    content = re.sub(
        r'title="\{\{ _\("([^"]+)"\) \}\}"',
        lambda m: convert_title_attr(m, translations),
        content
    )

    # 3. Inside spans that already exist
    content = re.sub(
        r'>(\{\{ _\("([^"]+)"\) \}\})<',
        lambda m: f' data-i18n="{translations.get(m.group(2), m.group(2))}">{translations.get(m.group(2), m.group(2))}<',
        content
    )

    # Write output
    backup_path = html_path.with_suffix('.html.bak')
    html_path.rename(backup_path)
    html_path.write_text(content, encoding='utf-8')

    print(f"Converted {html_path}")
    print(f"Backup saved to {backup_path}")

if __name__ == '__main__':
    main()
```

#### 2.3 Manual review checklist
After running conversion script:
- [ ] Verify all `{{ _() }}` calls are converted
- [ ] Check that HTML structure is preserved
- [ ] Test page loads without JavaScript errors
- [ ] Verify English text displays correctly

---

### Phase 3: JavaScript Migration (Day 3-4)
**Convert main.js from old i18n to new system**

#### 3.1 Pattern transformations

| Before | After |
|--------|-------|
| `i18n.gettext("Esperanto")` | `i18n.t("English")` |

#### 3.2 Update main.js initialization

Replace old i18n setup in main.html:
```html
<!-- OLD -->
<script src="{{static_path}}js/gettext.min.js"></script>
<script>
    var i18n = window.i18n();
    {% if settings.lingvo != 'eo' %}
    var i18njson=Get("{{static_path}}js/motioneye.{{settings.lingvo}}.json");
    i18n.loadJSON(i18njson, 'messages');
    {% endif %}
    i18n.setLocale('{{settings.lingvo}}');
</script>

<!-- NEW -->
<script src="{{static_path}}js/i18n.js"></script>
<script>
    var userLang = '{{settings.lingvo}}';
    i18n.init(userLang, function() {
        i18n.translatePage();
    });
</script>
```

---

### Phase 4: Testing & Cleanup (Day 5)

#### 4.1 Testing matrix
| Language | Expected Behavior |
|----------|-------------------|
| English | No translation file loaded, English text shown |
| German | de.json loaded, German text shown |
| Spanish | es.json loaded, Spanish text shown |
| Unknown | Fallback to English |

#### 4.2 Files to remove after migration
```
motioneye/locale/           # Entire directory (32 locales)
motioneye/static/js/gettext.min.js
motioneye/static/js/motioneye.*.json  # Old format files
```

#### 4.3 Files to keep
```
motioneye/static/js/i18n.js
motioneye/static/js/i18n/*.json
```

---

## Migration Mapping: Autofocus Strings

Example of what the German translation file would contain:

```json
{
  "Autofocus Mode": "Autofokus-Modus",
  "Autofocus Range": "Autofokus-Bereich",
  "Focus Position": "Fokusposition",
  "Manual": "Manuell",
  "Auto (Single)": "Auto (Einzel)",
  "Continuous": "Kontinuierlich",
  "Normal": "Normal",
  "Macro (Close-up)": "Makro (Nahaufnahme)",
  "Full Range": "Voller Bereich",
  "select the autofocus mode: manual (fixed focus distance), auto (focuses once), or continuous (always focusing)": "Autofokus-Modus auswählen: Manuell (feste Fokusdistanz), Auto (fokussiert einmal), oder Kontinuierlich (fokussiert ständig)",
  "select the focus search range: normal for general use, macro for close objects, full for maximum range": "Fokus-Suchbereich auswählen: Normal für allgemeine Nutzung, Makro für nahe Objekte, Voll für maximale Reichweite",
  "manual focus position in dioptres: 0 = infinity, 2 = 0.5m, 10 = 0.1m (macro)": "Manuelle Fokusposition in Dioptrien: 0 = Unendlich, 2 = 0,5m, 10 = 0,1m (Makro)"
}
```

---

## Performance Analysis

### Server (Pi) Impact
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| CPU per request | gettext lookup | None | ~100% reduction |
| Memory | .mo files loaded | None | ~50KB freed |
| Response time | Template render + translate | Template render only | ~10-20ms faster |

### Client Impact
| Metric | English User | Non-English User |
|--------|--------------|------------------|
| Extra HTTP request | None | 1 (JSON file ~5-15KB) |
| Translation time | None | ~5-20ms |
| Visual delay | None | Minimal (text already visible) |

---

## Rollback Plan

If issues discovered:
1. Restore `main.html.bak`
2. Revert i18n.js changes
3. Re-enable gettext.min.js loading
4. Keep locale/ directory intact until migration confirmed

---

## Success Criteria

- [ ] English users see English text immediately (no translation lookup)
- [ ] Non-English users see translated text within 100ms of page load
- [ ] All 32 existing languages continue to work
- [ ] No Esperanto visible anywhere in UI
- [ ] Pi CPU usage reduced during page loads
- [ ] New strings can be added by editing HTML directly in English

---

## Future Enhancements

1. **Browser language auto-detection**: Use `navigator.language` as default
2. **Crowdsourced translations**: JSON format is easy for community contribution
3. **Translation coverage report**: Script to identify untranslated strings
4. **Lazy section loading**: Only translate visible sections initially
