from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

clinical_engine = create_engine(settings.clinical_database_url, future=True)
identity_engine = create_engine(settings.identity_database_url, future=True)

ClinicalSessionLocal = sessionmaker(
    bind=clinical_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
IdentitySessionLocal = sessionmaker(
    bind=identity_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_clinical_session() -> Generator[Session, None, None]:
    session = ClinicalSessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_identity_session() -> Generator[Session, None, None]:
    session = IdentitySessionLocal()
    try:
        yield session
    finally:
        session.close()
