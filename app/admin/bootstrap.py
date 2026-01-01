from __future__ import annotations

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, init_db
from app.models.admin_user import AdminUser
from app.services.auth import hash_password


async def _create_admin(email: str, password: str, role: str) -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == email)
        )
        existing = result.scalars().first()
        if existing:
            raise ValueError(f"Admin user already exists: {email}")

        admin = AdminUser(
            username=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    print(f"Created admin user: {admin.username} (id={admin.id}, role={admin.role})")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an initial admin user (stored as username)."
    )
    parser.add_argument("--email", required=True, help="Admin email (used as username).")
    parser.add_argument("--password", help="Admin password (prompted if omitted).")
    parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "staff"],
        help="Role to assign to the user.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    email = args.email.strip().lower()
    password = args.password or getpass.getpass("Password: ")
    if not password.strip():
        raise SystemExit("Password is required")

    try:
        asyncio.run(_create_admin(email=email, password=password, role=args.role))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
