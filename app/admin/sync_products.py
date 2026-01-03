from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

from app.services.product_sync import run_product_sync  # noqa: E402


def main() -> None:
    asyncio.run(run_product_sync())


if __name__ == "__main__":
    main()
