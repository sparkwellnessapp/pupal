"""
GCS prefix cleanup for the B9 live smoke (closeout, owner-condition 1).

WRITTEN AND VERIFIED BEFORE THE RUN — that ordering is the whole point. A
cleanup written afterwards is a promise; this one is a tool that has already
been exercised in dry-run against the real bucket.

WHY A USER PREFIX, NOT `smoke/{timestamp}/` (deviation, surfaced not taken
silently): the intake path writes to `transcriptions/{user_id}/{uuid4()}.pdf`
(batch_grading.py:463). Forcing a `smoke/…` prefix would require changing that
line, which would mean the smoke no longer exercises the shipping code path —
the one thing it exists to prove. Running the smoke as a DEDICATED USER gives
an equally isolated, equally deletable prefix (`transcriptions/{smoke_user_id}/`)
with zero production-code change. Same guarantee, no test-only branch.

The database is wiped before launch; GCS is NOT. 120MB of real student
handwriting would otherwise outlive the wipe, so cleanup is mandatory, not
hygiene.

USAGE (dry-run is the default; deletion demands an explicit flag):
    python scripts/gcs_prefix_cleanup.py --prefix transcriptions/<uuid>/
    python scripts/gcs_prefix_cleanup.py --prefix transcriptions/<uuid>/ --delete
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):,.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True,
                    help="Object prefix to list/delete, e.g. transcriptions/<uuid>/")
    ap.add_argument("--delete", action="store_true",
                    help="Actually delete. Without this the run is READ-ONLY.")
    ap.add_argument("--yes-i-mean-it", action="store_true",
                    help="Required alongside --delete for prefixes outside a user folder.")
    args = ap.parse_args()

    prefix: str = args.prefix
    # Guardrail: an empty or bucket-root prefix would delete everything.
    if not prefix or prefix in ("/", "*"):
        print("REFUSED: empty/root prefix.")
        return 2
    if not prefix.endswith("/"):
        print("REFUSED: prefix must end with '/' — a bare prefix can match "
              "sibling folders by string overlap (transcriptions/ab vs ab-cd).")
        return 2
    broad = not prefix.startswith("transcriptions/") or prefix.count("/") < 2
    if args.delete and broad and not args.yes_i_mean_it:
        print(f"REFUSED: '{prefix}' is broader than a single user folder. "
              "Re-run with --yes-i-mean-it if that is truly intended.")
        return 2

    from google.cloud import storage
    client = (
        storage.Client.from_service_account_json(settings.gcs_credentials_file)
        if getattr(settings, "gcs_credentials_file", None)
        else storage.Client()
    )
    bucket = client.bucket(settings.gcs_bucket_name)

    blobs = list(client.list_blobs(bucket, prefix=prefix))
    total = sum(b.size or 0 for b in blobs)
    print("=" * 72)
    print(f"bucket : {settings.gcs_bucket_name}")
    print(f"prefix : {prefix}")
    print(f"objects: {len(blobs)}   total: {_mb(total)}")
    print("=" * 72)
    for b in blobs[:10]:
        print(f"  {b.name}  ({_mb(b.size or 0)})")
    if len(blobs) > 10:
        print(f"  … and {len(blobs) - 10} more")

    if not args.delete:
        print("\nDRY RUN — nothing deleted. Re-run with --delete to remove.")
        return 0

    if not blobs:
        print("\nNothing to delete.")
        return 0

    deleted = 0
    for b in blobs:
        b.delete()
        deleted += 1
    print(f"\nDeleted {deleted} object(s).")

    # VERIFY BY LISTING (the condition): deletion is not believed, it is checked.
    remaining = list(client.list_blobs(bucket, prefix=prefix))
    if remaining:
        print(f"VERIFY FAILED — {len(remaining)} object(s) still present:")
        for b in remaining[:10]:
            print(f"  {b.name}")
        return 1
    print("VERIFY OK — the prefix is empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
