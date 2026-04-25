"""add markdown pipeline fields to longitudinal reports"""

from alembic import op
import sqlalchemy as sa

revision = "20260419_000005"
down_revision = "20260415_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("longitudinal_reports", sa.Column("template_name", sa.String(length=100), nullable=True))
    op.add_column("longitudinal_reports", sa.Column("template_version", sa.String(length=50), nullable=True))
    op.add_column("longitudinal_reports", sa.Column("report_markdown", sa.Text(), nullable=True))
    op.add_column("longitudinal_reports", sa.Column("pipeline_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("longitudinal_reports", "pipeline_state")
    op.drop_column("longitudinal_reports", "report_markdown")
    op.drop_column("longitudinal_reports", "template_version")
    op.drop_column("longitudinal_reports", "template_name")
