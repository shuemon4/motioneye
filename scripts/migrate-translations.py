#!/usr/bin/env python3
"""
Migrate existing .po translations to new JSON format.

This script:
1. Reads the English .po file to get Esperanto -> English mapping
2. For each other locale, reads Esperanto -> Target mapping
3. Creates English -> Target JSON files for the new i18n system

Usage:
    python scripts/migrate-translations.py

Output:
    motioneye/static/js/i18n/{lang}.json for each locale
"""

import json
import re
from pathlib import Path


def parse_po_file(po_path: Path) -> dict[str, str]:
    """
    Parse a .po file into a dictionary of msgid -> msgstr.
    Handles multiline strings and escaped characters.
    """
    content = po_path.read_text(encoding='utf-8')
    translations = {}

    # State machine for parsing
    msgid_lines = []
    msgstr_lines = []
    in_msgid = False
    in_msgstr = False

    for line in content.split('\n'):
        line = line.strip()

        if line.startswith('#'):
            # Comment line, skip
            continue

        if line.startswith('msgid "'):
            # Save previous entry if exists
            if msgid_lines and msgstr_lines:
                msgid = ''.join(msgid_lines)
                msgstr = ''.join(msgstr_lines)
                if msgid:  # Don't store empty msgid (header)
                    translations[msgid] = msgstr

            # Start new msgid
            msgid_lines = [line[7:-1]]  # Extract content between quotes
            msgstr_lines = []
            in_msgid = True
            in_msgstr = False

        elif line.startswith('msgstr "'):
            msgstr_lines = [line[8:-1]]
            in_msgid = False
            in_msgstr = True

        elif line.startswith('"') and line.endswith('"'):
            # Continuation line
            content_part = line[1:-1]
            if in_msgstr:
                msgstr_lines.append(content_part)
            elif in_msgid:
                msgid_lines.append(content_part)

        elif line == '':
            # Empty line - save current entry
            if msgid_lines and msgstr_lines:
                msgid = ''.join(msgid_lines)
                msgstr = ''.join(msgstr_lines)
                if msgid:
                    translations[msgid] = msgstr
            msgid_lines = []
            msgstr_lines = []
            in_msgid = False
            in_msgstr = False

    # Don't forget the last entry
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


def migrate_locale(locale_dir: Path, english_map: dict[str, str], output_dir: Path) -> int:
    """
    Migrate a single locale from .po to .json.

    Args:
        locale_dir: Path to locale directory (e.g., locale/de/)
        english_map: Dictionary of Esperanto -> English
        output_dir: Output directory for JSON files

    Returns:
        Number of strings migrated
    """
    lang = locale_dir.name
    po_file = locale_dir / 'LC_MESSAGES' / 'motioneye.po'

    if not po_file.exists():
        print(f"  Skipping {lang}: no .po file found")
        return 0

    # Parse the target language .po file
    target_translations = parse_po_file(po_file)

    # Build English -> Target mapping
    # english_map: Esperanto -> English
    # target_translations: Esperanto -> Target
    # We want: English -> Target

    new_translations = {}
    for esperanto, english in english_map.items():
        if not english:
            # Skip if no English translation
            continue

        if esperanto in target_translations:
            target = target_translations[esperanto]
            if target and target != english:
                # Only include if there's a translation and it differs from English
                english_clean = unescape_po_string(english)
                target_clean = unescape_po_string(target)
                new_translations[english_clean] = target_clean

    if new_translations:
        output_file = output_dir / f'{lang}.json'
        output_file.write_text(
            json.dumps(new_translations, indent=2, ensure_ascii=False, sort_keys=True),
            encoding='utf-8'
        )
        return len(new_translations)
    else:
        print(f"  Skipping {lang}: no translations to migrate")
        return 0


def main():
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    base = project_root / 'motioneye'

    locale_base = base / 'locale'
    output_dir = base / 'static' / 'js' / 'i18n'

    print(f"Project root: {project_root}")
    print(f"Locale directory: {locale_base}")
    print(f"Output directory: {output_dir}")
    print()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse English .po to get Esperanto -> English mapping
    english_po = locale_base / 'en' / 'LC_MESSAGES' / 'motioneye.po'
    if not english_po.exists():
        print(f"ERROR: English .po file not found at {english_po}")
        return 1

    english_map = parse_po_file(english_po)
    print(f"Loaded {len(english_map)} English translations from {english_po.name}")
    print()

    # Migrate each locale (except English - it's the source language)
    total_strings = 0
    migrated_count = 0

    print("Migrating locales:")
    for locale_dir in sorted(locale_base.iterdir()):
        if locale_dir.is_dir() and locale_dir.name not in ('en', '__pycache__'):
            count = migrate_locale(locale_dir, english_map, output_dir)
            if count > 0:
                print(f"  {locale_dir.name}: {count} strings")
                total_strings += count
                migrated_count += 1

    print()
    print(f"Migration complete!")
    print(f"  Locales migrated: {migrated_count}")
    print(f"  Total translation strings: {total_strings}")
    print(f"  Output directory: {output_dir}")

    return 0


if __name__ == '__main__':
    exit(main())
