"""extend device bindings for onboarding"""

from alembic import op
import sqlalchemy as sa

revision = "20260405_000002"
down_revision = "20260405_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_bindings") as batch_op:
        batch_op.add_column(
            sa.Column("activation_code_hash", sa.String(length=255), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("binding_status", sa.String(length=50), nullable=False, server_default="available")
        )
        batch_op.add_column(sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("unbound_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=True)

    op.execute(
        "UPDATE device_bindings SET binding_status = 'bound', bound_at = created_at "
        "WHERE user_id IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("device_bindings") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column("unbound_at")
        batch_op.drop_column("bound_at")
        batch_op.drop_column("binding_status")
        batch_op.drop_column("activation_code_hash")
