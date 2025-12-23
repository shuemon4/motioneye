#!/usr/bin/env python3
"""Remove MMAL translations from all .po translation files.

This script removes legacy MMAL camera references from gettext .po files.
MMAL is no longer supported on 64-bit Raspberry Pi OS - only libcamera is used.
"""

import re
import glob
import os
from pathlib import Path


# Esperanto msgid strings to remove (source language)
MSGIDS_TO_REMOVE = [
    "Loka MMAL-kamerao",
    "Lokaj MMAL-kameraoj estas aparatoj konektitaj rekte al via motionEye-sistemo. Ĉi tiuj estas kutime kart-specifaj kameraoj.",
]


def remove_po_entry(content: str, msgid: str) -> tuple[str, bool]:
    """
    Remove a msgid/msgstr pair from .po file content.

    Args:
        content: Full .po file content
        msgid: The msgid string to remove

    Returns:
        Tuple of (modified_content, was_removed)
    """
    # Escape special regex characters in msgid
    escaped_msgid = re.escape(msgid)

    # Pattern to match msgid + msgstr pair (handles multiline strings)
    # Matches from msgid to the next blank line or next msgid
    pattern = (
        rf'^msgid "{escaped_msgid}"\s*\n'  # msgid line
        r'msgstr ".*?"\s*\n'                # msgstr line
        r'(?:\n|(?=msgid))'                 # blank line or next msgid
    )

    modified = re.sub(pattern, '', content, flags=re.MULTILINE)
    removed = modified != content

    return modified, removed


def process_po_file(filepath: Path) -> bool:
    """
    Remove MMAL translations from a single .po file.

    Args:
        filepath: Path to .po file

    Returns:
        True if file was modified, False otherwise
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        removed_count = 0

        # Remove each msgid
        for msgid in MSGIDS_TO_REMOVE:
            content, was_removed = remove_po_entry(content, msgid)
            if was_removed:
                removed_count += 1

        if removed_count > 0:
            # Write back the modified content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✓ {filepath}: Removed {removed_count} MMAL entries")
            return True
        else:
            print(f"- {filepath}: No MMAL entries found")
            return False

    except Exception as e:
        print(f"✗ {filepath}: Error - {e}")
        return False


def main():
    """Remove MMAL translations from all .po files."""

    # Find all .po files
    po_pattern = 'motioneye/locale/*/LC_MESSAGES/*.po'
    po_files = [Path(f) for f in glob.glob(po_pattern)]

    if not po_files:
        print(f"No .po files found matching: {po_pattern}")
        return

    print(f"Found {len(po_files)} .po translation files")
    print(f"Removing {len(MSGIDS_TO_REMOVE)} MMAL msgid entries:\n")
    for msgid in MSGIDS_TO_REMOVE:
        print(f"  - {msgid[:60]}{'...' if len(msgid) > 60 else ''}")
    print()

    total_modified = 0
    for filepath in sorted(po_files):
        if process_po_file(filepath):
            total_modified += 1

    print(f"\n{'='*70}")
    print(f"✓ Modified {total_modified} of {len(po_files)} .po files")
    print(f"  Removed all MMAL camera translation strings")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
