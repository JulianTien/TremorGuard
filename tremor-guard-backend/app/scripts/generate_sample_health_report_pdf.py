from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import desc, select

from app.core.config import get_settings
from app.db.session import ClinicalSessionLocal
from app.models.clinical import LongitudinalReport
from app.services.medical_records import (
    HEALTH_REPORT_TEMPLATE_TITLE,
    MARKDOWN_PDF_RENDERER,
    _render_report_markdown_from_payload,
    _report_download_filename,
    _report_sections,
)


def _parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Generate a styled TremorGuard health report PDF sample.")
    parser.add_argument("--report-id", help="Existing succeeded health report id to render.")
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "output"),
        help="Directory for the generated PDF. Defaults to the repository output/ folder.",
    )
    return parser.parse_args()


def _select_report(report_id: str | None) -> LongitudinalReport:
    with ClinicalSessionLocal() as session:
        if report_id:
            report = session.get(LongitudinalReport, report_id)
            if report is None:
                raise SystemExit(f"Report id not found: {report_id}")
            return report

        report = session.scalars(
            select(LongitudinalReport)
            .where(
                LongitudinalReport.title == HEALTH_REPORT_TEMPLATE_TITLE,
                LongitudinalReport.status == "succeeded",
            )
            .order_by(desc(LongitudinalReport.completed_at), desc(LongitudinalReport.created_at))
            .limit(1)
        ).first()
        if report is None:
            raise SystemExit("No succeeded health report found. Pass --report-id after generating one.")
        return report


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    report = _select_report(args.report_id)
    markdown = report.report_markdown or _render_report_markdown_from_payload(report.report_payload)
    if not markdown:
        raise SystemExit(f"Report {report.id} has no markdown or payload to render.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / _report_download_filename(report)
    input_snapshot = report.input_snapshot if isinstance(report.input_snapshot, dict) else {}
    report_metadata = input_snapshot.get("report_metadata") if isinstance(input_snapshot, dict) else {}
    if not isinstance(report_metadata, dict):
        report_metadata = {}

    output_path.write_bytes(
        MARKDOWN_PDF_RENDERER.render(
            report.title,
            markdown,
            metadata={
                "report_id": report.id,
                "template_name": report.template_name,
                "template_version": report.template_version,
                "created_at": report.completed_at.isoformat() if report.completed_at else None,
                "context": report.input_snapshot,
                "sections": _report_sections(report),
                "report_payload": report.report_payload,
                "mask_identifiers": bool(
                    report_metadata.get("mask_identifiers", settings.health_report_mask_identifiers)
                ),
            },
        )
    )
    print(output_path)


if __name__ == "__main__":
    main()
