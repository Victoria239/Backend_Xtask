"""Seed demo data — para correr UNA vez después de provisionar la DB.

Uso local:
  cd Backend_Xtask
  DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo.py

En Render: abrir el Shell del web service y ejecutar:
  python scripts/seed_demo.py

Crea:
  - tenant slug=default (id 1)
  - user demo@xtask.app / Demo#2026 (rol admin) en svc_auth.users
  - membership default ↔ demo user
Idempotente — si ya existen, no duplica.
"""

from __future__ import annotations

import asyncio
import os
import sys

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL no seteada", file=sys.stderr)
        sys.exit(1)

    if "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(url, echo=False)

    pwd_hash = bcrypt.hashpw("Demo#2026".encode(), bcrypt.gensalt()).decode()

    async with engine.begin() as conn:
        # Schemas e índices ya creados por Alembic / init_db.
        # Tenant
        await conn.execute(text("""
            INSERT INTO svc_tenants.tenants (slug, name, domain, plan, is_active, settings)
            VALUES ('default', 'Demo Tenant', NULL, 'demo', true, '{}'::json)
            ON CONFLICT (slug) DO NOTHING
        """))
        tenant_row = (await conn.execute(text(
            "SELECT id FROM svc_tenants.tenants WHERE slug = 'default'"
        ))).first()
        if not tenant_row:
            print("ERROR: no se pudo crear/leer tenant default", file=sys.stderr)
            sys.exit(2)
        tenant_id = int(tenant_row[0])

        # User demo
        await conn.execute(text("""
            INSERT INTO svc_auth.users
              (username, password, email, full_name, role, is_active, created_at)
            VALUES
              ('demo', :pwd, 'demo@xtask.app', 'Demo User', 'admin', true, NOW())
            ON CONFLICT (email) DO NOTHING
        """), {"pwd": pwd_hash})

        user_row = (await conn.execute(text(
            "SELECT id FROM svc_auth.users WHERE email = 'demo@xtask.app'"
        ))).first()
        user_id = int(user_row[0])

        # Membership
        await conn.execute(text("""
            INSERT INTO svc_tenants.tenant_memberships
              (tenant_id, user_id, role, is_default)
            VALUES (:tid, :uid, 'admin', true)
            ON CONFLICT DO NOTHING
        """), {"tid": tenant_id, "uid": user_id})

    await engine.dispose()
    print("OK — seed completado")
    print(f"  Tenant default: id={tenant_id}")
    print(f"  User demo@xtask.app id={user_id} / Demo#2026")


if __name__ == "__main__":
    asyncio.run(main())
