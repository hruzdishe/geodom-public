"""rename district longitude

Revision ID: ae1bd4623b24
Revises: f93b227bd449
Create Date: 2026-09-26 18:14:32.280143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae1bd4623b24'
down_revision: Union[str, Sequence[str], None] = 'f93b227bd449'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "districts",
        "center_longtitude",
        new_column_name="center_longitude"
    )


def downgrade() -> None:
    op.alter_column(
        "districts",
        "center_longitude",
        new_column_name="center_longtitude"
    )
