"""Move tables from public schema into per-service schemas.

Revision ID: 003
Revises: 002
Create Date: 2026-03-04 18:56:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Schema → tables mapping
SCHEMA_TABLES: dict[str, list[str]] = {
    "svc_auth": ["users"],
    "svc_projects": ["projects"],
    "svc_employees": ["employee_projects", "employees"],
    "svc_finance": ["budgets", "invoices"],
    "svc_payroll": ["payrolls"],
    "svc_kpis": ["kpis"],
    "svc_skills": ["skills"],
    "svc_dashboard": ["dashboard_widgets", "dashboard_layouts"],
}

# Cross-schema foreign keys to drop (constraint_name, table, schema)
CROSS_SCHEMA_FKS = [
    ("employees_user_id_fkey", "employees", "svc_employees"),
    ("employee_projects_employee_id_fkey", "employee_projects", "svc_employees"),
    ("employee_projects_project_id_fkey", "employee_projects", "svc_employees"),
    ("budgets_project_id_fkey", "budgets", "svc_finance"),
    ("invoices_project_id_fkey", "invoices", "svc_finance"),
    ("payrolls_employee_id_fkey", "payrolls", "svc_payroll"),
    ("kpis_employee_id_fkey", "kpis", "svc_kpis"),
    ("skills_employee_id_fkey", "skills", "svc_skills"),
    ("dashboard_layouts_user_id_fkey", "dashboard_layouts", "svc_dashboard"),
]


def upgrade() -> None:
    # 1. Create schemas
    for schema in SCHEMA_TABLES:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # 2. Move tables into their schemas (order matters: child tables first)
    for schema, tables in SCHEMA_TABLES.items():
        for table in tables:
            op.execute(f"ALTER TABLE public.{table} SET SCHEMA {schema}")

    # 3. Drop cross-schema foreign key constraints
    #    (intra-schema FKs like dashboard_widgets→dashboard_layouts survive the move)
    for fk_name, table, schema in CROSS_SCHEMA_FKS:
        op.execute(f"ALTER TABLE {schema}.{table} DROP CONSTRAINT IF EXISTS {fk_name}")


def downgrade() -> None:
    # 1. Move tables back to public (reverse order: parents first)
    reverse_map: dict[str, list[str]] = {
        "svc_dashboard": ["dashboard_layouts", "dashboard_widgets"],
        "svc_skills": ["skills"],
        "svc_kpis": ["kpis"],
        "svc_payroll": ["payrolls"],
        "svc_finance": ["invoices", "budgets"],
        "svc_employees": ["employees", "employee_projects"],
        "svc_projects": ["projects"],
        "svc_auth": ["users"],
    }
    for schema, tables in reverse_map.items():
        for table in tables:
            op.execute(f"ALTER TABLE {schema}.{table} SET SCHEMA public")

    # 3. Re-add cross-schema foreign keys
    op.execute("ALTER TABLE public.employees ADD CONSTRAINT employees_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.employee_projects ADD CONSTRAINT employee_projects_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id)")
    op.execute("ALTER TABLE public.employee_projects ADD CONSTRAINT employee_projects_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)")
    op.execute("ALTER TABLE public.budgets ADD CONSTRAINT budgets_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)")
    op.execute("ALTER TABLE public.invoices ADD CONSTRAINT invoices_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)")
    op.execute("ALTER TABLE public.payrolls ADD CONSTRAINT payrolls_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id)")
    op.execute("ALTER TABLE public.kpis ADD CONSTRAINT kpis_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id)")
    op.execute("ALTER TABLE public.skills ADD CONSTRAINT skills_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id)")
    op.execute("ALTER TABLE public.dashboard_layouts ADD CONSTRAINT dashboard_layouts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)")

    # 4. Drop schemas
    for schema in SCHEMA_TABLES:
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
