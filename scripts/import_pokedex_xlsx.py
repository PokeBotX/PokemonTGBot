"""Import Pokemon catalog data from the local XLSX into PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import asyncpg

XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CELL_REF_RE = re.compile(r"([A-Z]+)")


@dataclass
class PokemonRow:
    dex_id: int
    name: str
    pokemon_type: str | None
    rarity: str | None
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import pokemon_catalog rows from pokedex_all_pokemon_with_safebooru.xlsx"
    )
    parser.add_argument(
        "--xlsx",
        default="pokedex_all_pokemon_with_safebooru.xlsx",
        help="Path to source XLSX file",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Update existing pokemon_catalog rows instead of leaving them unchanged",
    )
    return parser.parse_args()


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("a:v", XML_NS)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text)]
    return value.text


def _column_index(cell_ref: str) -> int:
    match = CELL_REF_RE.match(cell_ref)
    if not match:
        raise ValueError(f"Unexpected cell reference: {cell_ref}")

    column = 0
    for char in match.group(1):
        column = column * 26 + (ord(char) - ord("A") + 1)
    return column - 1


def _row_values(row: ET.Element, shared_strings: list[str]) -> list[str]:
    values: list[str] = []
    for cell in row:
        cell_index = _column_index(cell.attrib["r"])
        while len(values) <= cell_index:
            values.append("")
        values[cell_index] = _cell_value(cell, shared_strings)
    return values


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root:
        text = "".join(t.text or "" for t in item.iter("{%s}t" % XML_NS["a"]))
        strings.append(text)
    return strings


def _compose_type(primary: str, secondary: str) -> str | None:
    primary = primary.strip().lower()
    secondary = secondary.strip().lower()
    if primary and secondary:
        return f"{primary}/{secondary}"
    return primary or secondary or None


def load_rows(xlsx_path: str) -> list[PokemonRow]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    sheet_data = sheet.find("a:sheetData", XML_NS)
    if sheet_data is None:
        raise ValueError("sheet1.xml does not contain sheetData")

    rows = list(sheet_data)
    if not rows:
        return []

    headers = _row_values(rows[0], shared_strings)
    index = {name: pos for pos, name in enumerate(headers)}

    required = [
        "national_dex",
        "name",
        "type_1",
        "type_2",
        "rarity",
        "hp",
        "atk",
        "def",
        "spd",
    ]
    missing = [name for name in required if name not in index]
    if missing:
        raise ValueError(f"Missing expected XLSX columns: {', '.join(missing)}")

    parsed_rows: list[PokemonRow] = []
    for row in rows[1:]:
        values = _row_values(row, shared_strings)
        if not values or not values[index["national_dex"]].strip():
            continue

        def get(name: str) -> str:
            pos = index[name]
            return values[pos] if pos < len(values) else ""

        parsed_rows.append(
            PokemonRow(
                dex_id=int(get("national_dex")),
                name=get("name").strip(),
                pokemon_type=_compose_type(get("type_1"), get("type_2")),
                rarity=get("rarity").strip() or None,
                base_hp=int(get("hp") or 0),
                base_attack=int(get("atk") or 0),
                base_defense=int(get("def") or 0),
                base_stamina=int(get("spd") or 0),
            )
        )

    return parsed_rows


def _db_connect_kwargs() -> dict[str, object]:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return {"dsn": dsn}
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": _required_env("DB_NAME"),
        "user": _required_env("DB_USER"),
        "password": _required_env("DB_PASSWORD"),
    }


async def import_rows(rows: list[PokemonRow], replace: bool) -> None:
    conn = await asyncpg.connect(**_db_connect_kwargs())
    try:
        sql = """
            INSERT INTO pokemon_catalog (
                id,
                name,
                type,
                rarity,
                base_hp,
                base_attack,
                base_defense,
                base_stamina
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        if replace:
            sql += """
            ON CONFLICT (id) DO UPDATE
            SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                rarity = EXCLUDED.rarity,
                base_hp = EXCLUDED.base_hp,
                base_attack = EXCLUDED.base_attack,
                base_defense = EXCLUDED.base_defense,
                base_stamina = EXCLUDED.base_stamina
            """
        else:
            sql += " ON CONFLICT (id) DO NOTHING"

        await conn.executemany(
            sql,
            [
                (
                    row.dex_id,
                    row.name,
                    row.pokemon_type,
                    row.rarity,
                    row.base_hp,
                    row.base_attack,
                    row.base_defense,
                    row.base_stamina,
                )
                for row in rows
            ],
        )
    finally:
        await conn.close()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value


async def main() -> None:
    args = parse_args()
    rows = load_rows(args.xlsx)
    await import_rows(rows, replace=args.replace)
    print(f"Imported {len(rows)} rows from {args.xlsx}")


if __name__ == "__main__":
    asyncio.run(main())
