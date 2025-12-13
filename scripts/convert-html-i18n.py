#!/usr/bin/env python3
"""
Convert main.html from Jinja2 _() server-side translation to
client-side data-i18n attributes with English as source.

This script:
1. Reads the English .po file to map Esperanto -> English
2. Converts {{ _("esperanto") }} to data-i18n="English">English
3. Handles various patterns: text content, titles, options, etc.

Usage:
    python scripts/convert-html-i18n.py [--dry-run]

The script creates a backup before modifying main.html.
"""

import re
import sys
from pathlib import Path
from typing import Callable


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


def escape_html_attr(s: str) -> str:
    """Escape string for use in HTML attribute."""
    return (s
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


class HtmlConverter:
    def __init__(self, translations: dict[str, str]):
        self.translations = translations
        self.stats = {
            'title_attrs': 0,
            'span_labels': 0,
            'option_text': 0,
            'inline_text': 0,
            'section_titles': 0,
            'button_text': 0,
            'other': 0,
            'not_found': 0,
        }

    def get_english(self, esperanto: str) -> str:
        """Get English translation for Esperanto string."""
        english = self.translations.get(esperanto, '')
        if not english:
            self.stats['not_found'] += 1
            # Fallback: use the Esperanto string as-is
            # This shouldn't happen if .po file is complete
            print(f"  WARNING: No English translation for: {esperanto[:50]}...")
            return esperanto
        return unescape_po_string(english)

    def convert_title_attr(self, match: re.Match) -> str:
        """Convert title="{{ _("text") }}" to data-i18n-title="English" title="English"."""
        esperanto = match.group(1)
        english = self.get_english(esperanto)
        self.stats['title_attrs'] += 1
        return f'data-i18n-title="{escape_html_attr(english)}" title="{escape_html_attr(english)}"'

    def convert_span_label(self, match: re.Match) -> str:
        """Convert <span class="settings-item-label">{{ _("text") }}</span>."""
        esperanto = match.group(1)
        english = self.get_english(esperanto)
        self.stats['span_labels'] += 1
        return f'<span class="settings-item-label" data-i18n="{escape_html_attr(english)}">{english}</span>'

    def convert_section_title(self, match: re.Match) -> str:
        """Convert <a class="settings-section-title">{{ _("text") }}</a>."""
        esperanto = match.group(1)
        english = self.get_english(esperanto)
        self.stats['section_titles'] += 1
        return f'<a class="settings-section-title" data-i18n="{escape_html_attr(english)}">{english}</a>'

    def convert_option_text(self, match: re.Match) -> str:
        """Convert <option value="x">{{ _("text") }}</option>."""
        prefix = match.group(1)  # e.g., '<option value="0">'
        esperanto = match.group(2)
        english = self.get_english(esperanto)
        self.stats['option_text'] += 1
        # Insert data-i18n before the closing >
        prefix_without_close = prefix[:-1]  # Remove trailing >
        return f'{prefix_without_close} data-i18n="{escape_html_attr(english)}">{english}</option>'

    def convert_button_text(self, match: re.Match) -> str:
        """Convert button/div with {{ _("text") }} content."""
        esperanto = match.group(1)
        english = self.get_english(esperanto)
        self.stats['button_text'] += 1
        return f' data-i18n="{escape_html_attr(english)}">{english}<'

    def convert_inline_jinja(self, match: re.Match) -> str:
        """Convert standalone {{ _("text") }} to <span data-i18n="...">...</span>."""
        esperanto = match.group(1)
        english = self.get_english(esperanto)
        self.stats['inline_text'] += 1
        return f'<span data-i18n="{escape_html_attr(english)}">{english}</span>'

    def convert(self, html: str) -> str:
        """Convert all translation patterns in HTML."""
        result = html

        # 1. Title attributes: title="{{ _("text") }}"
        result = re.sub(
            r'title="\{\{\s*_\("([^"]+)"\)\s*\}\}"',
            self.convert_title_attr,
            result
        )

        # 2. Settings item labels: <span class="settings-item-label">{{ _("text") }}</span>
        result = re.sub(
            r'<span class="settings-item-label">\{\{\s*_\("([^"]+)"\)\s*\}\}</span>',
            self.convert_span_label,
            result
        )

        # 3. Section titles: <a class="settings-section-title">{{ _("text") }}</a>
        result = re.sub(
            r'<a class="settings-section-title">\{\{\s*_\("([^"]+)"\)\s*\}\}</a>',
            self.convert_section_title,
            result
        )

        # 4. Option elements: <option value="...">{{ _("text") }}</option>
        result = re.sub(
            r'(<option[^>]*>)\{\{\s*_\("([^"]+)"\)\s*\}\}</option>',
            self.convert_option_text,
            result
        )

        # 5. Button/div text: >{{ _("text") }}<
        result = re.sub(
            r'>\{\{\s*_\("([^"]+)"\)\s*\}\}<',
            self.convert_button_text,
            result
        )

        # 6. Remaining inline {{ _("text") }} - wrap in span
        result = re.sub(
            r'\{\{\s*_\("([^"]+)"\)\s*\}\}',
            self.convert_inline_jinja,
            result
        )

        return result


def main():
    dry_run = '--dry-run' in sys.argv

    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    base = project_root / 'motioneye'

    html_path = base / 'templates' / 'main.html'
    po_path = base / 'locale' / 'en' / 'LC_MESSAGES' / 'motioneye.po'

    print(f"HTML file: {html_path}")
    print(f"English .po file: {po_path}")
    print(f"Dry run: {dry_run}")
    print()

    if not html_path.exists():
        print(f"ERROR: HTML file not found: {html_path}")
        return 1

    if not po_path.exists():
        print(f"ERROR: English .po file not found: {po_path}")
        return 1

    # Load translations
    translations = parse_po_file(po_path)
    print(f"Loaded {len(translations)} English translations")

    # Read HTML
    original_html = html_path.read_text(encoding='utf-8')

    # Count patterns before conversion
    jinja_count = len(re.findall(r'\{\{\s*_\(', original_html))
    print(f"Found {jinja_count} Jinja2 _() calls to convert")
    print()

    # Convert
    converter = HtmlConverter(translations)
    converted_html = converter.convert(original_html)

    # Count remaining patterns (should be 0)
    remaining = len(re.findall(r'\{\{\s*_\(', converted_html))

    print("Conversion statistics:")
    for key, count in converter.stats.items():
        if count > 0:
            print(f"  {key}: {count}")
    print()
    print(f"Remaining unconverted: {remaining}")

    if remaining > 0:
        # Find and show remaining patterns
        print("\nUnconverted patterns:")
        for match in re.finditer(r'.{0,30}\{\{\s*_\([^\)]+\)\s*\}\}.{0,30}', converted_html):
            print(f"  ...{match.group(0)}...")

    if dry_run:
        print("\nDry run - no files modified")
        # Show a sample of changes
        print("\nSample changes (first 5):")
        import difflib
        diff = list(difflib.unified_diff(
            original_html.splitlines()[:100],
            converted_html.splitlines()[:100],
            lineterm='',
            n=1
        ))
        for line in diff[:30]:
            print(line)
    else:
        # Create backup
        backup_path = html_path.with_suffix('.html.bak')
        html_path.rename(backup_path)
        print(f"\nBackup created: {backup_path}")

        # Write converted HTML
        html_path.write_text(converted_html, encoding='utf-8')
        print(f"Converted HTML written: {html_path}")

    return 0


if __name__ == '__main__':
    exit(main())
