"""add rehab guidance templates and plans"""

from alembic import op
import sqlalchemy as sa

revision = "20260415_000004"
down_revision = "20260412_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rehab_plan_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("scenario_key", sa.String(length=100), nullable=False),
        sa.Column("intensity", sa.String(length=30), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("frequency_label", sa.String(length=100), nullable=False),
        sa.Column("cautions", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("template_key"),
    )
    op.create_index("ix_rehab_plan_templates_template_key", "rehab_plan_templates", ["template_key"], unique=False)
    op.create_index("ix_rehab_plan_templates_scenario_key", "rehab_plan_templates", ["scenario_key"], unique=False)

    op.create_table(
        "rehab_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("evaluation_window", sa.String(length=30), nullable=False, server_default="calendar_day"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("scenario", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("conflict_status", sa.String(length=30), nullable=False, server_default="consistent"),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_current_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_plan_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rehab_plans_user_id", "rehab_plans", ["user_id"], unique=False)
    op.create_index("ix_rehab_plans_as_of_date", "rehab_plans", ["as_of_date"], unique=False)
    op.create_index("ix_rehab_plans_status", "rehab_plans", ["status"], unique=False)
    op.create_index("ix_rehab_plans_is_current_active", "rehab_plans", ["is_current_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rehab_plans_is_current_active", table_name="rehab_plans")
    op.drop_index("ix_rehab_plans_status", table_name="rehab_plans")
    op.drop_index("ix_rehab_plans_as_of_date", table_name="rehab_plans")
    op.drop_index("ix_rehab_plans_user_id", table_name="rehab_plans")
    op.drop_table("rehab_plans")

    op.drop_index("ix_rehab_plan_templates_scenario_key", table_name="rehab_plan_templates")
    op.drop_index("ix_rehab_plan_templates_template_key", table_name="rehab_plan_templates")
    op.drop_table("rehab_plan_templates")
