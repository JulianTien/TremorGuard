from __future__ import annotations

import os
import shutil
import sys
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "tremor-guard-backend"
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

try:
    from app.main import app  # noqa: E402
except Exception as exc:  # pragma: no cover - hosted runtime diagnostic fallback
    from fastapi import FastAPI  # noqa: E402
    from fastapi.responses import JSONResponse  # noqa: E402

    app = FastAPI(title="TremorGuard Backend Import Error")

    @app.get("/{path:path}")
    def backend_import_error(path: str) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "status": "backend_import_failed",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "path": f"/{path}",
            },
        )
