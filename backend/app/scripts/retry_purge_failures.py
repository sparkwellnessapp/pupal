"""Re-attempt every object a student purge could not delete (M-B2, PRV-3).

    python -m app.scripts.retry_purge_failures

A purge deletes her rows in one transaction and then her objects; an object
that fails lands in `purge_failures` (migration 033) and an ERROR line. This
command re-attempts every ledger row, clears the ones that now succeed, and
leaves the rest with their attempt count bumped. Safe to run at any time and
as often as wanted: a delete of an object already gone is a no-op, and every
target still passes the PRV-11 allow-list first.
"""
import asyncio
import logging
import sys

from sqlalchemy import text

from ..database import AsyncSessionLocal
from ..services.erasure import get_purge_storage, retry_purge_failures


async def run() -> tuple[int, int]:
    cleared = await retry_purge_failures(storage=get_purge_storage())
    async with AsyncSessionLocal() as db:
        remaining = (await db.execute(text("SELECT COUNT(*) FROM purge_failures"))).scalar_one()
    return cleared, remaining


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    cleared, remaining = asyncio.run(run())
    print(f"cleared {cleared}; {remaining} still in the ledger")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
