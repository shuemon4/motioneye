#!/usr/bin/env python3
"""
Convert main.js from old Esperanto i18n.gettext() to new English motionEyeI18n.t().

This script:
1. Reads the English .po file to map Esperanto -> English
2. Converts i18n.gettext("Esperanto") to motionEyeI18n.t("English")

Usage:
    python scripts/convert-js-i18n.py [--dry-run]
"""

import re
import sys
from pathlib import Path


def parse_po_file(po_path: Path) -> dict[str, str]:
    """Parse a .po file into a dictionary of msgid -> msgstr."""
    content = po_path.read_text(encoding='utf-8')
    translations = {}

    msgid_lines = []
    msgstr_lines = []
    in_msgid = False
    in_msgstr = False

    for line in content.split('\n'):
        line = line.strip()

        if line.startswith('#'):
            continue

        if line.startswith('msgid "'):
            if msgid_lines and msgstr_lines:
                msgid = ''.join(msgid_lines)
                msgstr = ''.join(msgstr_lines)
                if msgid:
                    translations[msgid] = msgstr

            msgid_lines = [line[7:-1]]
            msgstr_lines = []
            in_msgid = True
            in_msgstr = False

        elif line.startswith('msgstr "'):
            msgstr_lines = [line[8:-1]]
            in_msgid = False
            in_msgstr = True

        elif line.startswith('"') and line.endswith('"'):
            content_part = line[1:-1]
            if in_msgstr:
                msgstr_lines.append(content_part)
            elif in_msgid:
                msgid_lines.append(content_part)

        elif line == '':
            if msgid_lines and msgstr_lines:
                msgid = ''.join(msgid_lines)
                msgstr = ''.join(msgstr_lines)
                if msgid:
                    translations[msgid] = msgstr
            msgid_lines = []
            msgstr_lines = []
            in_msgid = False
            in_msgstr = False

    if msgid_lines and msgstr_lines:
        msgid = ''.join(msgid_lines)
        msgstr = ''.join(msgstr_lines)
        if msgid:
            translations[msgid] = msgstr

    return translations


def unescape_po_string(s: str) -> str:
    """Unescape .po file string escapes."""
    return (s
            .replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\"', '"')
            .replace('\\\\', '\\'))


def escape_js_string(s: str) -> str:
    """Escape string for JavaScript."""
    return (s
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t'))


class JsConverter:
    def __init__(self, translations: dict[str, str]):
        self.translations = translations
        self.converted = 0
        self.not_found = 0
        self.missing = []

    def convert_gettext(self, match: re.Match) -> str:
        """Convert i18n.gettext("esperanto") to motionEyeI18n.t("English")."""
        esperanto = match.group(1)
        english = self.translations.get(esperanto, '')

        if not english:
            self.not_found += 1
            self.missing.append(esperanto)
            # Keep the Esperanto as fallback
            return f'motionEyeI18n.t("{escape_js_string(esperanto)}")'

        self.converted += 1
        english_clean = unescape_po_string(english)
        return f'motionEyeI18n.t("{escape_js_string(english_clean)}")'

    def convert_gettext_single(self, match: re.Match) -> str:
        """Convert i18n.gettext('esperanto') to motionEyeI18n.t('English')."""
        esperanto = match.group(1)
        english = self.translations.get(esperanto, '')

        if not english:
            self.not_found += 1
            self.missing.append(esperanto)
            # Keep the Esperanto as fallback
            return f"motionEyeI18n.t('{escape_js_string(esperanto)}')"

        self.converted += 1
        english_clean = unescape_po_string(english)
        # Use single quotes to match original
        escaped = escape_js_string(english_clean).replace("\\'", "'").replace("'", "\\'")
        return f"motionEyeI18n.t('{escaped}')"

    def convert(self, js: str) -> str:
        """Convert all i18n.gettext calls."""
        # Match i18n.gettext("...") with double quotes
        result = re.sub(
            r'i18n\.gettext\("([^"]+)"\)',
            self.convert_gettext,
            js
        )
        # Match i18n.gettext('...') with single quotes
        result = re.sub(
            r"i18n\.gettext\('([^']+)'\)",
            self.convert_gettext_single,
            result
        )
        return result


def main():
    dry_run = '--dry-run' in sys.argv

    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    base = project_root / 'motioneye'

    js_path = base / 'static' / 'js' / 'main.js'
    po_path = base / 'locale' / 'en' / 'LC_MESSAGES' / 'motioneye.po'
    # Also check the JS-specific .po file
    js_po_path = base / 'locale' / 'en' / 'LC_MESSAGES' / 'motioneye.js.po'

    print(f"JS file: {js_path}")
    print(f"English .po file: {po_path}")
    print(f"Dry run: {dry_run}")
    print()

    if not js_path.exists():
        print(f"ERROR: JS file not found: {js_path}")
        return 1

    # Load translations from both .po files
    translations = {}

    if po_path.exists():
        translations.update(parse_po_file(po_path))
        print(f"Loaded {len(translations)} translations from motioneye.po")

    if js_po_path.exists():
        js_translations = parse_po_file(js_po_path)
        translations.update(js_translations)
        print(f"Loaded {len(js_translations)} additional translations from motioneye.js.po")

    # Read JS
    original_js = js_path.read_text(encoding='utf-8')

    # Count patterns before conversion
    gettext_count = len(re.findall(r'i18n\.gettext\(', original_js))
    print(f"Found {gettext_count} i18n.gettext() calls to convert")
    print()

    # Convert
    converter = JsConverter(translations)
    converted_js = converter.convert(original_js)

    print(f"Converted: {converter.converted}")
    print(f"Not found (kept as-is): {converter.not_found}")

    if converter.missing:
        print(f"\nMissing translations (first 10):")
        for m in converter.missing[:10]:
            print(f"  - {m[:60]}...")

    if dry_run:
        print("\nDry run - no files modified")
    else:
        # Create backup
        backup_path = js_path.with_suffix('.js.bak')
        if not backup_path.exists():
            js_path.rename(backup_path)
            print(f"\nBackup created: {backup_path}")

        # Write converted JS
        js_path.write_text(converted_js, encoding='utf-8')
        print(f"Converted JS written: {js_path}")

    return 0


if __name__ == '__main__':
    exit(main())
