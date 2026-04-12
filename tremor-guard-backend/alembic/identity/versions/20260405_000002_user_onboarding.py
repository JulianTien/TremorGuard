"""add user onboarding fields"""

from alembic import op
import sqlalchemy as sa

revision = "20260405_000002"
down_revision = "20260405_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending_onboarding"),
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_state",
            sa.String(length=50),
            nullable=False,
            server_default="profile_required",
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "auth_credentials", sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE users SET status = 'active', onboarding_state = 'active'")
    op.execute("UPDATE auth_credentials SET password_updated_at = created_at")
    with op.batch_alter_table("auth_credentials") as batch_op:
        batch_op.alter_column("password_updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    op.drop_column("auth_credentials", "password_updated_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "onboarding_state")
    op.drop_column("users", "status")
