"""Create auth users table."""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_validated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("profile_picture_url", sa.String(length=2048), nullable=True),
        sa.Column("google_subject", sa.String(length=255), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_subject", "users", ["google_subject"], unique=True)
    op.create_table(
        "auth_email_sends",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_auth_email_sends_email", "auth_email_sends", ["email"], unique=False
    )
    op.create_index(
        "ix_auth_email_sends_purpose", "auth_email_sends", ["purpose"], unique=False
    )
    op.create_index(
        "ix_auth_email_sends_sent_at", "auth_email_sends", ["sent_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_auth_email_sends_sent_at", table_name="auth_email_sends")
    op.drop_index("ix_auth_email_sends_purpose", table_name="auth_email_sends")
    op.drop_index("ix_auth_email_sends_email", table_name="auth_email_sends")
    op.drop_table("auth_email_sends")
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
