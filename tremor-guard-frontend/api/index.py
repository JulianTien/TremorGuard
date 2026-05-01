from __future__ import annotations

import os
import shutil
import sys
import json
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FRONTEND_ROOT.parent
BACKEND_DIR = next(
    (
        path
        for path in (
            REPO_ROOT / "tremor-guard-backend",
            FRONTEND_ROOT / "api" / "_backend_bundle",
        )
        if path.exists()
    ),
    REPO_ROOT / "tremor-guard-backend",
)
TMP_DIR = Path("/tmp/tremor-guard")


def _copy_sqlite_database(source_name: str, target_name: str) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    source = BACKEND_DIR / source_name
    target = TMP_DIR / target_name
    if source.exists() and not target.exists():
        shutil.copy2(source, target)
    return target


clinical_db = _copy_sqlite_database("clinical.db", "clinical.db")
identity_db = _copy_sqlite_database("identity.db", "identity.db")

os.environ.setdefault("CLINICAL_DATABASE_URL", f"sqlite:///{clinical_db}")
os.environ.setdefault("IDENTITY_DATABASE_URL", f"sqlite:///{identity_db}")
os.environ.setdefault(
    "CORS_ORIGINS",
    json.dumps(
        [
            "https://tremor-guard.vercel.app",
            "https://tremor-guard-juliantiens-projects.vercel.app",
            "https://tremor-guard-git-main-juliantiens-projects.vercel.app",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    ),
)
os.environ.setdefault("MEDICAL_RECORDS_STORAGE_DIR", str(BACKEND_DIR / "storage" / "medical_records"))

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
