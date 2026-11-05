"""Owner tool: register the apps allowed to connect to calendars (D35).

    python scripts/oauth_clients.py create --name "Репетитор" --redirect-uri https://tutor.example/calendar/callback
        [--redirect-uri ...] [--scope events.read --scope events.write ...] [--public]
    python scripts/oauth_clients.py list
    python scripts/oauth_clients.py disable <client_id>

`create` prints client_id and, for server apps, a client_secret that is shown only once.
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.application.oauth import SUPPORTED_SCOPES, digest, validate_redirect_uri  # noqa: E402
from app.infrastructure.db.models import OAuthClientModel  # noqa: E402
from app.infrastructure.db.session import SessionLocal  # noqa: E402

DEFAULT_SCOPES = ["openid", "profile", "calendars.read", "events.read", "events.write"]


def main(argv=None, out=print) -> int:
    parser = argparse.ArgumentParser(description="Connected apps (owner only)")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--redirect-uri", action="append", required=True)
    create.add_argument("--scope", action="append")
    create.add_argument("--public", action="store_true", help="app without a server (mobile/SPA): no secret")
    sub.add_parser("list")
    disable = sub.add_parser("disable")
    disable.add_argument("client_id")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "list":
            for row in db.scalars(select(OAuthClientModel)):
                out(f"{row.id}  {row.name}  {row.client_type}  {'active' if row.active else 'disabled'}  "
                    f"{' '.join(row.allowed_scopes)}  {' '.join(row.redirect_uris)}")
            return 0
        if args.command == "disable":
            row = db.get(OAuthClientModel, args.client_id)
            if row is None:
                out("error: no such client")
                return 1
            row.active = False
            db.commit()
            out(f"disabled: {row.id}")
            return 0
        scopes = args.scope or DEFAULT_SCOPES
        unknown = set(scopes) - set(SUPPORTED_SCOPES)
        name = args.name.strip()
        try:
            uris = [validate_redirect_uri(uri) for uri in args.redirect_uri]
        except ValueError as exc:
            out(f"error: {exc}")
            return 1
        if unknown or not name:
            out(f"error: unknown scopes {sorted(unknown)}" if unknown else "error: name is required")
            return 1
        client_id = "pcl_" + secrets.token_urlsafe(12)
        secret = None if args.public else "pcs_" + secrets.token_urlsafe(32)
        db.add(OAuthClientModel(id=client_id, name=name, secret_hash=digest(secret) if secret else None,
                                client_type="public" if args.public else "confidential",
                                redirect_uris=uris, allowed_scopes=list(dict.fromkeys(scopes)), active=True))
        db.commit()
    out(f"client_id: {client_id}")
    if secret:
        out(f"client_secret (shown once): {secret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
