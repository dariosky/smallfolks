"""Create durable world snapshots.

Revision ID: 0002_create_world_snapshots
Revises: 0001_create_users
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_create_world_snapshots"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("world_snapshots"):
        return
    op.create_table(
        "world_snapshots",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_world_snapshots_seed", "world_snapshots", ["seed"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("world_snapshots"):
        return
    op.drop_index("ix_world_snapshots_seed", table_name="world_snapshots")
    op.drop_table("world_snapshots")
