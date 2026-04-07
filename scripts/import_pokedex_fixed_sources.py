"""Import external art source links from pokedex_fixed_links.xlsx into image_credits.source."""

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


@dataclass(slots=True)
class FixedSourceRow:
    dex_id: int
    name: str
    source_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import pokemon art source links from pokedex_fixed_links.xlsx into image_credits.source"
    )
    parser.add_argument("--xlsx", default="pokedex_fixed_links.xlsx", help="Path to source XLSX file")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only fill image_credits.source when it is NULL or empty",
    )
    return parser.parse_args()


def _load_dotenv() -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root:
        text = "".join(t.text or "" for t in item.iter("{%s}t" % XML_NS["a"]))
        strings.append(text)
    return strings


def load_rows(xlsx_path: str) -> list[FixedSourceRow]:
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
    index = {name.strip().lower(): pos for pos, name in enumerate(headers)}

    source_key = "sourse" if "sourse" in index else "source"
    required = ["national_dex", "name", source_key]
    missing = [name for name in required if name not in index]
    if missing:
        raise ValueError(f"Missing expected XLSX columns: {', '.join(missing)}")

    parsed_rows: list[FixedSourceRow] = []
    for row in rows[1:]:
        values = _row_values(row, shared_strings)
        if not values:
            continue

        def get(name: str) -> str:
            pos = index[name]
            return values[pos] if pos < len(values) else ""

        dex_raw = get("national_dex").strip()
        source_url = get(source_key).strip()
        if not dex_raw or not source_url:
            continue

        parsed_rows.append(
            FixedSourceRow(
                dex_id=int(dex_raw),
                name=get("name").strip(),
                source_url=source_url,
            )
        )

    return parsed_rows


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value


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


async def import_rows(rows: list[FixedSourceRow], *, only_missing: bool) -> tuple[int, int]:
    conn = await asyncpg.connect(**_db_connect_kwargs())
    updated = 0
    missing = 0
    try:
        async with conn.transaction():
            for row in rows:
                sql = """
                    UPDATE image_credits ic
                    SET source = $2
                    FROM pokemon_catalog pc
                    WHERE pc.id = $1
                      AND pc.image_credit_id = ic.id
                """
                if only_missing:
                    sql += " AND (ic.source IS NULL OR btrim(ic.source) = '')"

                result = await conn.execute(sql, row.dex_id, row.source_url)
                count = int(result.split()[-1])
                if count:
                    updated += count
                else:
                    missing += 1
    finally:
        await conn.close()

    return updated, missing


async def main() -> None:
    _load_dotenv()
    args = parse_args()
    rows = load_rows(args.xlsx)
    updated, missing = await import_rows(rows, only_missing=args.only_missing)
    print(f"Loaded rows: {len(rows)}")
    print(f"Updated image_credits: {updated}")
    print(f"Rows without linked image_credit: {missing}")


if __name__ == "__main__":
    asyncio.run(main())
