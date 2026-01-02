from __future__ import annotations

import asyncio

from app.services.product_sync import run_product_sync


def main() -> None:
    asyncio.run(run_product_sync())


if __name__ == "__main__":
    main()
