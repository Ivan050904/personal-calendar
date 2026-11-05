"""Owner tool for calendar accounts (D34): there is no email, so the owner creates
accounts and resets passwords here. Prints a one-time temporary password.

    python scripts/accounts.py create <login> [--name "Имя"] [--timezone Europe/Moscow]
    python scripts/accounts.py reset-password <login>
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.accounts import create_account, reset_password  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.infrastructure.db.session import SessionLocal  # noqa: E402


def main(argv=None, out=print) -> int:
    parser = argparse.ArgumentParser(description="Calendar accounts (owner only)")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("login")
    create.add_argument("--name")
    create.add_argument("--timezone", default="Europe/Moscow")
    reset = sub.add_parser("reset-password")
    reset.add_argument("login")
    args = parser.parse_args(argv)

    password = secrets.token_urlsafe(12)
    with SessionLocal() as db:
        try:
            if args.command == "create":
                row = create_account(db, args.login, password, args.name, args.timezone)
            else:
                row = reset_password(db, args.login, password)
            login = row.login
            db.commit()
        except AppError as exc:
            out(f"error: {exc.message}")
            return 1
    out(f"login: {login}")
    out(f"temporary password (shown once): {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
