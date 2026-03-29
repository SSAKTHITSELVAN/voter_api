"""Add optional person name column

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("persons", "name")
