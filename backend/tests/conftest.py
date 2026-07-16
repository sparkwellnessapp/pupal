"""
Pytest configuration for backend.

The backend code uses absolute imports like `from app.services...`.
When running pytest from the repo root, `vivi-codebase/backend` is not
automatically on sys.path, so `import app` fails during test collection.

This file makes the backend package importable for local/CI test runs.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]  # .../vivi-codebase/backend
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

