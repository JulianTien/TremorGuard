from __future__ import annotations

import argparse
from types import SimpleNamespace

from sqlalchemy import select

from app.db.session import ClinicalSessionLocal, IdentitySessionLocal
from app.models.clinical import LongitudinalReport
from app.models.identity import User
from app.services.medical_records import (
    HEALTH_REPORT_TEMPLATE_TITLE,
    _initial_pipeline_state,
    process_pending_report,
)


LOW_QUALITY_MARKERS = (
    "姓名：当前用户",
    "累计记录 0 次震颤事件",
    "用药窗口内共记录 0 条用药记录",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reprocess TremorGuard health reports.")
    parser.add_argument("--report-id", action="append", default=[], help="Specific report id to reprocess.")
    parser.add_argument(
        "--low-quality-only",
        action="store_true",
        help="Reprocess succeeded health reports whose markdown contains known low-quality placeholders.",
    )
    return parser.parse_args()


def _display_names_by_user_id() -> dict[str, str]:
    with IdentitySessionLocal() as session:
        return {
            user.id: user.display_name
            for user in session.scalars(select(User).where(User.display_name.is_not(None)))
        }


def _select_reports(report_ids: list[str], low_quality_only: bool) -> list[LongitudinalReport]:
    with ClinicalSessionLocal() as session:
        if report_ids:
            reports = list(
                session.scalars(select(LongitudinalReport).where(LongitudinalReport.id.in_(report_ids)))
            )
            missing = sorted(set(report_ids) - {report.id for report in reports})
            if missing:
                raise SystemExit(f"Report id not found: {', '.join(missing)}")
            return reports

        if not low_quality_only:
            raise SystemExit("Pass at least one --report-id or use --low-quality-only.")

        reports = list(
            session.scalars(
                select(LongitudinalReport).where(
                    LongitudinalReport.title == HEALTH_REPORT_TEMPLATE_TITLE,
                    LongitudinalReport.status == "succeeded",
                )
            )
        )
        return [
            report
            for report in reports
            if any(marker in (report.report_markdown or "") for marker in LOW_QUALITY_MARKERS)
        ]


def main() -> None:
    args = _parse_args()
    selected_reports = _select_reports(args.report_id, args.low_quality_only)
    display_names = _display_names_by_user_id()

    if not selected_reports:
        print("No reports matched.")
        return

    with ClinicalSessionLocal() as session:
        for selected in selected_reports:
            report = session.get(LongitudinalReport, selected.id)
            if report is None:
                continue

            report.status = "queued"
            report.pdf_status = "queued"
            report.report_markdown = None
            report.narrative_text = None
            report.report_payload = None
            report.summary = None
            report.pdf_path = None
            report.error_summary = None
            report.completed_at = None
            report.pipeline_state = _initial_pipeline_state()
            session.commit()

            process_pending_report(
                session,
                SimpleNamespace(
                    id=report.user_id,
                    display_name=display_names.get(report.user_id) or "当前用户",
                ),
                report.id,
            )
            session.refresh(report)
            print(f"{report.id}: {report.status}/{report.pdf_status} via {report.model_name}")


if __name__ == "__main__":
    main()
