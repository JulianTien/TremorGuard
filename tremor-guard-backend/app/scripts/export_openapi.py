import json
from pathlib import Path

from app.main import app


def main() -> None:
    output_path = Path(__file__).resolve().parents[2] / "openapi.json"
    output_path.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
