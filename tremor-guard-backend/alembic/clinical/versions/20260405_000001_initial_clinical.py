"""initial clinical schema"""

from alembic import op
import sqlalchemy as sa

revision = "20260405_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "patient_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=False),
        sa.Column("diagnosis", sa.String(length=255), nullable=False),
        sa.Column("duration", sa.String(length=50), nullable=False),
        sa.Column("hospital", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patient_profiles_user_id", "patient_profiles", ["user_id"], unique=True)

    op.create_table(
        "device_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("patient_profiles.user_id"), nullable=False),
        sa.Column("device_serial", sa.String(length=100), nullable=False),
        sa.Column("device_name", sa.String(length=100), nullable=False),
        sa.Column("firmware_version", sa.String(length=50), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_bindings_user_id", "device_bindings", ["user_id"], unique=False)
    op.create_index("ix_device_bindings_device_serial", "device_bindings", ["device_serial"], unique=True)
    op.create_index("ix_device_bindings_api_key_hash", "device_bindings", ["api_key_hash"], unique=True)

    op.create_table(
        "device_status_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_binding_id", sa.String(length=36), sa.ForeignKey("device_bindings.id"), nullable=False),
        sa.Column("battery_level", sa.Integer(), nullable=False),
        sa.Column("connection", sa.String(length=20), nullable=False),
        sa.Column("connection_label", sa.String(length=100), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_days_label", sa.String(length=50), nullable=False),
        sa.Column("firmware_version", sa.String(length=50), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_status_snapshots_user_id", "device_status_snapshots", ["user_id"], unique=False)
    op.create_index("ix_device_status_snapshots_device_binding_id", "device_status_snapshots", ["device_binding_id"], unique=False)
    op.create_index("ix_device_status_snapshots_recorded_at", "device_status_snapshots", ["recorded_at"], unique=False)

    op.create_table(
        "medication_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dose", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medication_logs_user_id", "medication_logs", ["user_id"], unique=False)
    op.create_index("ix_medication_logs_taken_at", "medication_logs", ["taken_at"], unique=False)

    op.create_table(
        "tremor_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_binding_id", sa.String(length=36), sa.ForeignKey("device_bindings.id"), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("dominant_hz", sa.Float(), nullable=False),
        sa.Column("rms_amplitude", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "start_at", "source", name="uq_tremor_event_user_start_source"),
    )
    op.create_index("ix_tremor_events_user_id", "tremor_events", ["user_id"], unique=False)
    op.create_index("ix_tremor_events_start_at", "tremor_events", ["start_at"], unique=False)
    if bind.dialect.name == "postgresql":
        op.execute("SELECT create_hypertable('tremor_events', 'start_at', if_not_exists => TRUE)")

    op.create_table(
        "report_records",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_type", sa.String(length=255), nullable=False),
        sa.Column("size_label", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_records_user_id", "report_records", ["user_id"], unique=False)

    op.create_table(
        "consent_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("patient_profiles.user_id"), nullable=False),
        sa.Column("share_with_doctor", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rag_analysis_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cloud_sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consent_settings_user_id", "consent_settings", ["user_id"], unique=True)

    op.create_table(
        "api_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_summary", sa.JSON(), nullable=True),
        sa.Column("response_summary", sa.JSON(), nullable=True),
        sa.Column("risk_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("endpoint", "idempotency_key", name="uq_api_audit_endpoint_idempotency"),
    )
    op.create_index("ix_api_audit_logs_user_id", "api_audit_logs", ["user_id"], unique=False)
    op.create_index("ix_api_audit_logs_endpoint", "api_audit_logs", ["endpoint"], unique=False)
    op.create_index("ix_api_audit_logs_created_at", "api_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_audit_logs_created_at", table_name="api_audit_logs")
    op.drop_index("ix_api_audit_logs_endpoint", table_name="api_audit_logs")
    op.drop_index("ix_api_audit_logs_user_id", table_name="api_audit_logs")
    op.drop_table("api_audit_logs")
    op.drop_index("ix_consent_settings_user_id", table_name="consent_settings")
    op.drop_table("consent_settings")
    op.drop_index("ix_report_records_user_id", table_name="report_records")
    op.drop_table("report_records")
    op.drop_index("ix_tremor_events_start_at", table_name="tremor_events")
    op.drop_index("ix_tremor_events_user_id", table_name="tremor_events")
    op.drop_table("tremor_events")
    op.drop_index("ix_medication_logs_taken_at", table_name="medication_logs")
    op.drop_index("ix_medication_logs_user_id", table_name="medication_logs")
    op.drop_table("medication_logs")
    op.drop_index("ix_device_status_snapshots_recorded_at", table_name="device_status_snapshots")
    op.drop_index("ix_device_status_snapshots_device_binding_id", table_name="device_status_snapshots")
    op.drop_index("ix_device_status_snapshots_user_id", table_name="device_status_snapshots")
    op.drop_table("device_status_snapshots")
    op.drop_index("ix_device_bindings_api_key_hash", table_name="device_bindings")
    op.drop_index("ix_device_bindings_device_serial", table_name="device_bindings")
    op.drop_index("ix_device_bindings_user_id", table_name="device_bindings")
    op.drop_table("device_bindings")
    op.drop_index("ix_patient_profiles_user_id", table_name="patient_profiles")
    op.drop_table("patient_profiles")
