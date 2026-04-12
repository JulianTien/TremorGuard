from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[2]


def run_upgrade(config_name: str, db_url: str) -> None:
    config = Config(str(BASE_DIR / config_name))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")


def main() -> None:
    run_upgrade("alembic_identity.ini", settings.identity_database_url)
    run_upgrade("alembic_clinical.ini", settings.clinical_database_url)


if __name__ == "__main__":
    main()
