"""Create local directories for each pokemon name from the XLSX catalog."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from import_pokedex_xlsx import load_rows

INVALID_PATH_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one local folder per pokemon from the XLSX catalog"
    )
    parser.add_argument(
        "--xlsx",
        default="pokedex_all_pokemon_with_safebooru.xlsx",
        help="Path to source XLSX file",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/pokemon",
        help="Directory where pokemon folders will be created",
    )
    return parser.parse_args()


def sanitize_name(name: str) -> str:
    sanitized = INVALID_PATH_CHARS_RE.sub("-", name).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    sanitized = sanitized.rstrip(". ")
    return sanitized or "unknown"


def main() -> None:
    args = parse_args()
    rows = load_rows(args.xlsx)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_count = 0
    for row in rows:
        folder_name = sanitize_name(row.name)
        target_dir = output_dir / folder_name
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            created_count += 1

    print(f"Created {created_count} new folders in {output_dir}")
    print(f"Total pokemon rows processed: {len(rows)}")


if __name__ == "__main__":
    main()
