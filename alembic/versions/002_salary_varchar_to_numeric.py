"""Change employees.salary from VARCHAR to NUMERIC(12,2)

Revision ID: 002
Revises: 001
Create Date: 2026-03-04 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE employees
        ALTER COLUMN salary TYPE NUMERIC(12, 2)
        USING salary::NUMERIC(12, 2)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE employees
        ALTER COLUMN salary TYPE VARCHAR
        USING salary::VARCHAR
    """)
