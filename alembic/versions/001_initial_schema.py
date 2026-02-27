"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-02-27 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL NOT NULL,
            username VARCHAR NOT NULL,
            password VARCHAR NOT NULL,
            email VARCHAR NOT NULL,
            full_name VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (username),
            UNIQUE (email)
        )
    """)

    # Create projects table
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL NOT NULL,
            name VARCHAR NOT NULL,
            description TEXT,
            status VARCHAR NOT NULL DEFAULT 'active',
            start_date TIMESTAMP WITH TIME ZONE,
            end_date TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id)
        )
    """)

    # Create employees table
    op.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL NOT NULL,
            user_id INTEGER NOT NULL,
            first_name VARCHAR,
            last_name VARCHAR,
            position VARCHAR NOT NULL,
            department VARCHAR NOT NULL,
            salary VARCHAR NOT NULL,
            contract_status VARCHAR NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create employee_projects table
    op.execute("""
        CREATE TABLE IF NOT EXISTS employee_projects (
            id SERIAL NOT NULL,
            employee_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS employee_projects")
    op.execute("DROP TABLE IF EXISTS employees")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS users")
