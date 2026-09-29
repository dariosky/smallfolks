"""Add explicit snapshot format metadata.

Revision ID: 0003_add_world_format_version
Revises: 0002_create_world_snapshots
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_world_format_version"
down_revision = "0002_create_world_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("world_snapshots")}
    if "world_format_version" not in columns:
        op.add_column(
            "world_snapshots",
            sa.Column(
                "world_format_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("world_snapshots")}
    if "world_format_version" in columns:
        op.drop_column("world_snapshots", "world_format_version")
