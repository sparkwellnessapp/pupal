"""Dump the FastAPI OpenAPI schema to a file WITHOUT starting a server or a DB.

Used by the frontend codegen (`npm run gen:api`) and the CI drift check (PR-4).

`app.openapi()` runs on import alone — the lifespan (`init_db`) never fires, so no
DB connection is attempted. Requirements to run:
  - the backend must be importable: run with the backend dir on PYTHONPATH, and
    `PYTHONUTF8=1` on Windows;
  - `app.config` reads a few env vars at import — a schema dump needs no live
    services, so CI may pass dummy values (DATABASE_URL / OPENAI_API_KEY / ...).

Output is written with `sort_keys=True` so the bytes are DETERMINISTIC across runs
on identical code — that is what makes the CI `git diff --exit-code` check meaningful.

Usage:  python scripts/dump_openapi.py [out_path=openapi.json]
"""
import json
import sys

from app.main import app


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    schema = app.openapi()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
    paths = len(schema.get("paths", {}))
    comps = len(schema.get("components", {}).get("schemas", {}))
    print(f"OPENAPI_OK version={schema.get('openapi')} paths={paths} schemas={comps} -> {out}")


if __name__ == "__main__":
    main()
