"""add medical records archive and longitudinal reports"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_000003"
down_revision = "20260405_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_record_archives",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("consent_policy", sa.String(length=100), nullable=False, server_default="rag_and_cloud_sync_required"),
        sa.Column("retention_policy", sa.String(length=100), nullable=False, server_default="retain_until_user_deletion_request"),
        sa.Column("delete_policy", sa.String(length=100), nullable=False, server_default="support_assisted_delete"),
        sa.Column("export_policy", sa.String(length=100), nullable=False, server_default="pdf_export_only"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medical_record_archives_user_id", "medical_record_archives", ["user_id"], unique=False)

    op.create_table(
        "medical_record_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("archive_id", sa.String(length=36), sa.ForeignKey("medical_record_archives.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("processing_status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_medical_record_files_archive_id", "medical_record_files", ["archive_id"], unique=False)
    op.create_index("ix_medical_record_files_user_id", "medical_record_files", ["user_id"], unique=False)
    op.create_index("ix_medical_record_files_processing_status", "medical_record_files", ["processing_status"], unique=False)

    op.create_table(
        "medical_record_extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("archive_id", sa.String(length=36), sa.ForeignKey("medical_record_archives.id"), nullable=False),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("medical_record_files.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=100), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("structured_payload", sa.JSON(), nullable=True),
        sa.Column("source_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("file_id", "version", name="uq_medical_record_extraction_file_version"),
    )
    op.create_index("ix_medical_record_extractions_archive_id", "medical_record_extractions", ["archive_id"], unique=False)
    op.create_index("ix_medical_record_extractions_file_id", "medical_record_extractions", ["file_id"], unique=False)
    op.create_index("ix_medical_record_extractions_user_id", "medical_record_extractions", ["user_id"], unique=False)
    op.create_index("ix_medical_record_extractions_status", "medical_record_extractions", ["status"], unique=False)

    op.create_table(
        "longitudinal_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("archive_id", sa.String(length=36), sa.ForeignKey("medical_record_archives.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="病历联合健康报告"),
        sa.Column("report_window_start", sa.Date(), nullable=False),
        sa.Column("report_window_end", sa.Date(), nullable=False),
        sa.Column("monitoring_window_start", sa.Date(), nullable=False),
        sa.Column("monitoring_window_end", sa.Date(), nullable=False),
        sa.Column("medication_window_start", sa.Date(), nullable=False),
        sa.Column("medication_window_end", sa.Date(), nullable=False),
        sa.Column("disclaimer_version", sa.String(length=50), nullable=False, server_default="non-diagnostic-v1"),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("report_payload", sa.JSON(), nullable=True),
        sa.Column("narrative_text", sa.Text(), nullable=True),
        sa.Column("pdf_status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("archive_id", "version", name="uq_longitudinal_report_archive_version"),
    )
    op.create_index("ix_longitudinal_reports_archive_id", "longitudinal_reports", ["archive_id"], unique=False)
    op.create_index("ix_longitudinal_reports_user_id", "longitudinal_reports", ["user_id"], unique=False)
    op.create_index("ix_longitudinal_reports_status", "longitudinal_reports", ["status"], unique=False)

    op.create_table(
        "report_input_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("longitudinal_reports.id"), nullable=False),
        sa.Column("archive_id", sa.String(length=36), sa.ForeignKey("medical_record_archives.id"), nullable=False),
        sa.Column("input_type", sa.String(length=30), nullable=False),
        sa.Column("input_id", sa.String(length=36), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_input_links_report_id", "report_input_links", ["report_id"], unique=False)
    op.create_index("ix_report_input_links_archive_id", "report_input_links", ["archive_id"], unique=False)
    op.create_index("ix_report_input_links_input_id", "report_input_links", ["input_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_report_input_links_input_id", table_name="report_input_links")
    op.drop_index("ix_report_input_links_archive_id", table_name="report_input_links")
    op.drop_index("ix_report_input_links_report_id", table_name="report_input_links")
    op.drop_table("report_input_links")

    op.drop_index("ix_longitudinal_reports_status", table_name="longitudinal_reports")
    op.drop_index("ix_longitudinal_reports_user_id", table_name="longitudinal_reports")
    op.drop_index("ix_longitudinal_reports_archive_id", table_name="longitudinal_reports")
    op.drop_table("longitudinal_reports")

    op.drop_index("ix_medical_record_extractions_status", table_name="medical_record_extractions")
    op.drop_index("ix_medical_record_extractions_user_id", table_name="medical_record_extractions")
    op.drop_index("ix_medical_record_extractions_file_id", table_name="medical_record_extractions")
    op.drop_index("ix_medical_record_extractions_archive_id", table_name="medical_record_extractions")
    op.drop_table("medical_record_extractions")

    op.drop_index("ix_medical_record_files_processing_status", table_name="medical_record_files")
    op.drop_index("ix_medical_record_files_user_id", table_name="medical_record_files")
    op.drop_index("ix_medical_record_files_archive_id", table_name="medical_record_files")
    op.drop_table("medical_record_files")

    op.drop_index("ix_medical_record_archives_user_id", table_name="medical_record_archives")
    op.drop_table("medical_record_archives")
