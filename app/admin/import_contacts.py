from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.services.contacts_importer import parse_csv_contacts, parse_json_contacts, upsert_contacts


def _infer_format(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    return None


async def _run(path: str, fmt: str, update_existing: bool) -> int:
    file_path = Path(path)
    if not file_path.exists():
        print(f"contacts import: file not found ({file_path})")
        return 1

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    if fmt == "json":
        contacts = parse_json_contacts(content)
    elif fmt == "csv":
        contacts = parse_csv_contacts(content)
    else:
        print("contacts import: format must be json or csv")
        return 2

    if not contacts:
        print("contacts import: no contacts found")
        return 3

    async with AsyncSessionLocal() as session:
        result = await upsert_contacts(session, contacts, update_existing=update_existing)

    print(
        "contacts import complete:",
        f"created={result['created']}",
        f"updated={result['updated']}",
        f"skipped={result['skipped']}",
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Instagram contacts from file")
    parser.add_argument("--path", help="Path to JSON/CSV file")
    parser.add_argument("--format", choices=["json", "csv"], help="File format")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        default=False,
        help="Update existing contacts",
    )
    args = parser.parse_args()

    path = args.path or os.getenv("CONTACTS_IMPORT_FILE")
    fmt = args.format or os.getenv("CONTACTS_IMPORT_FORMAT")
    if not path:
        print("contacts import: missing --path or CONTACTS_IMPORT_FILE")
        raise SystemExit(2)
    if not fmt:
        fmt = _infer_format(path)
    if fmt not in {"json", "csv"}:
        print("contacts import: invalid format; use --format json|csv")
        raise SystemExit(2)

    raise SystemExit(asyncio.run(_run(path, fmt, update_existing=args.update_existing)))


if __name__ == "__main__":
    main()
