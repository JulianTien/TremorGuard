from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_clinical_session, get_identity_session
from app.main import app
from app.services.seeds import seed_clinical, seed_identity


def run_upgrade(config_path: Path, database_url: str) -> None:
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    identity_db_path = tmp_path / "identity.sqlite3"
    clinical_db_path = tmp_path / "clinical.sqlite3"

    repo_root = Path(__file__).resolve().parents[2]
    run_upgrade(repo_root / "alembic_identity.ini", f"sqlite:///{identity_db_path}")
    run_upgrade(repo_root / "alembic_clinical.ini", f"sqlite:///{clinical_db_path}")

    identity_engine = create_engine(f"sqlite:///{identity_db_path}", future=True)
    clinical_engine = create_engine(f"sqlite:///{clinical_db_path}", future=True)
    identity_session_factory = sessionmaker(bind=identity_engine, expire_on_commit=False, future=True)
    clinical_session_factory = sessionmaker(bind=clinical_engine, expire_on_commit=False, future=True)

    with identity_session_factory() as identity_session:
        user_id = seed_identity(identity_session)

    with clinical_session_factory() as clinical_session:
        seed_clinical(clinical_session, user_id)

    def override_identity_session() -> Generator[Session, None, None]:
        with identity_session_factory() as session:
            yield session

    def override_clinical_session() -> Generator[Session, None, None]:
        with clinical_session_factory() as session:
            yield session

    app.dependency_overrides[get_identity_session] = override_identity_session
    app.dependency_overrides[get_clinical_session] = override_clinical_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
