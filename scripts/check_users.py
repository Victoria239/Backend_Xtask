"""Quick script to check users in the database."""
import asyncio
from sqlalchemy import text
from shared.database import engine


async def main():
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, username, email, role FROM svc_auth.users ORDER BY id")
        )
        rows = result.fetchall()
        if not rows:
            print("No users found.")
        for row in rows:
            print(f"id={row[0]}  username={row[1]}  email={row[2]}  role={row[3]}")


asyncio.run(main())
