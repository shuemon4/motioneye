#!/usr/bin/env python3
"""Remove auto_brightness translations from all JSON i18n files."""

import json
import glob
import os

# Keys to remove
KEYS_TO_REMOVE = [
    "Automatic Brightness",
    "enables software automatic brightness (only recommended for cameras without autobrightness)"
]

def remove_translations(filepath):
    """Remove auto_brightness translation keys from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Track if anything was removed
        removed = []
        for key in KEYS_TO_REMOVE:
            if key in data:
                del data[key]
                removed.append(key)

        if removed:
            # Write back with proper formatting
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write('\n')  # Add trailing newline

            print(f"✓ {os.path.basename(filepath)}: Removed {len(removed)} keys")
            return True
        else:
            print(f"- {os.path.basename(filepath)}: No keys found")
            return False

    except Exception as e:
        print(f"✗ {os.path.basename(filepath)}: Error - {e}")
        return False

def main():
    # Find all i18n JSON files
    pattern = 'motioneye/static/js/i18n/*.json'
    files = glob.glob(pattern)

    if not files:
        print(f"No files found matching: {pattern}")
        return

    print(f"Found {len(files)} translation files\n")

    total_modified = 0
    for filepath in sorted(files):
        if remove_translations(filepath):
            total_modified += 1

    print(f"\n✓ Modified {total_modified} of {len(files)} files")

if __name__ == '__main__':
    main()
