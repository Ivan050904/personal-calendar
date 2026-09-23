#!/usr/bin/env python3
"""Deploy Personal Calendar to Beget VPS (calendar.folio-one.ru).

Usage (PowerShell):
  $env:BEGET_SSH_PASSWORD='…'
  python scripts/deploy_calendar.py

Reads optional AUTH_* / GROQ_* from backend/.env for server .env seeding.
"""
from __future__ import annotations

import io
import os
import secrets
import tarfile
import time
from pathlib import Path

import paramiko

HOST = "155.212.132.213"
USER = "root"
DOMAIN = "calendar.folio-one.ru"
APP_DIR = "/opt/personal-calendar"
API_PORT = 8060
STATIC_PORT = 8061
DB_PORT = 3307
NGINX_CONF = "/root/-Mobile-application-for-expense-tracking/backend/nginx.conf"
CERTBOT_EMAIL = "admin@folio-one.ru"
MARKER = f"# Personal Calendar ({DOMAIN})"

# Folio AI proxy (NL). Beget cannot call api.groq.com directly (403 Forbidden).
WHISPER_PROXY_BASE = "http://91.186.214.4:8787/groq/v1"
WHISPER_PROXY_MODEL = "whisper-large-v3-turbo"

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DIST = ROOT / "dist"


def password() -> str:
    pw = (os.environ.get("BEGET_SSH_PASSWORD") or os.environ.get("SSH_PASSWORD") or "").strip()
    if not pw:
        # Fallback used by sibling folio deploys on this machine (not committed here).
        deploy_env = Path(r"C:\Users\Пользователь\Desktop\шува\wishlist\.env.deploy")
        if deploy_env.exists():
            for line in deploy_env.read_text(encoding="utf-8").splitlines():
                if line.startswith("BEGET_SSH_PASSWORD="):
                    pw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not pw:
        raise SystemExit("Set BEGET_SSH_PASSWORD or SSH_PASSWORD")
    return pw


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> tuple[int, str, str]:
    print(f"\n$ {cmd[:160]}{'...' if len(cmd) > 160 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")

    def _safe(s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")

    if out.strip():
        print(_safe(out[-4000:]))
    if err.strip() and code != 0:
        print("ERR:", _safe(err[-2000:]))
    return code, out, err


def read_local_backend_env() -> dict[str, str]:
    path = BACKEND / ".env"
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def build_tarball() -> bytes:
    if not DIST.exists():
        raise SystemExit("dist/ missing — run npm run build first")
    buf = io.BytesIO()
    skip_dirs = {".venv", "__pycache__", ".pytest_cache", "node_modules", ".git"}
    skip_names = {".env", ".env.local"}
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in BACKEND.rglob("*"):
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.name in skip_names:
                continue
            if path.is_file():
                arc = Path("backend") / path.relative_to(BACKEND)
                tar.add(path, arcname=str(arc).replace("\\", "/"))
        for path in DIST.rglob("*"):
            if path.is_file():
                arc = Path("frontend") / path.relative_to(DIST)
                tar.add(path, arcname=str(arc).replace("\\", "/"))
    return buf.getvalue()


def upload_bundle(client: paramiko.SSHClient, payload: bytes) -> None:
    sftp = client.open_sftp()
    with sftp.open("/tmp/personal-calendar.tgz", "wb") as remote:
        remote.write(payload)
    sftp.close()
    run(client, f"mkdir -p {APP_DIR} && tar -xzf /tmp/personal-calendar.tgz -C {APP_DIR}")


def ensure_mariadb(client: paramiko.SSHClient, db_password: str) -> None:
    _, names, _ = run(client, "docker ps -a --format '{{.Names}}'")
    if "calendar-mariadb" not in names:
        run(
            client,
            "docker run -d --name calendar-mariadb --restart unless-stopped "
            f"-e MYSQL_DATABASE=calendar -e MYSQL_USER=calendar "
            f"-e MYSQL_PASSWORD='{db_password}' -e MYSQL_ROOT_PASSWORD='{db_password}' "
            f"-p 127.0.0.1:{DB_PORT}:3306 mariadb:11",
            timeout=300,
        )
    else:
        run(client, "docker start calendar-mariadb || true")
    for _ in range(40):
        code, _, _ = run(
            client,
            f"docker exec calendar-mariadb mariadb -ucalendar -p'{db_password}' -e 'SELECT 1' calendar",
        )
        if code == 0:
            return
        time.sleep(2)
    raise SystemExit("MariaDB did not become ready")


def write_server_env(client: paramiko.SSHClient, db_password: str) -> None:
    code, _, _ = run(client, f"test -f {APP_DIR}/backend/.env")
    if code == 0:
        print("Keeping existing server .env (AI/auth/DB unchanged)")
        return
    local = read_local_backend_env()
    session_secret = local.get("AUTH_SESSION_SECRET") or secrets.token_urlsafe(32)
    auth_user = local.get("AUTH_USERNAME") or "петр"
    auth_pass = local.get("AUTH_PASSWORD") or "12345678"
    groq = local.get("GROQ_API_KEY") or local.get("AI_API_KEY") or ""
    body = "\n".join(
        [
            f"DATABASE_URL=mysql+pymysql://calendar:{db_password}@127.0.0.1:{DB_PORT}/calendar",
            "APP_NAME=personal-calendar-api",
            "APP_ENV=production",
            "API_PREFIX=/api",
            f"CORS_ORIGINS=https://{DOMAIN},http://{DOMAIN}",
            f"AUTH_USERNAME={auth_user}",
            f"AUTH_PASSWORD={auth_pass}",
            f"AUTH_SESSION_SECRET={session_secret}",
            "AI_PROVIDER=groq",
            f"AI_API_KEY={groq}",
            "AI_BASE_URL=https://api.groq.com/openai/v1",
            "AI_MODEL=openai/gpt-oss-20b",
            f"GROQ_API_KEY={groq}",
            "GROQ_BASE_URL=https://api.groq.com/openai/v1",
            "GROQ_MODEL=openai/gpt-oss-20b",
            "WHISPER_BACKEND=remote",
            f"WHISPER_API_BASE_URL={WHISPER_PROXY_BASE}",
            f"WHISPER_API_KEY={groq}",
            f"WHISPER_REMOTE_MODEL={WHISPER_PROXY_MODEL}",
            "WHISPER_MODEL=small",
            "",
        ]
    )
    sftp = client.open_sftp()
    with sftp.open(f"{APP_DIR}/backend/.env", "w") as remote:
        remote.write(body)
    sftp.close()


def ensure_remote_whisper_env(client: paramiko.SSHClient) -> None:
    """Force production Whisper via NL Groq proxy — never local torch on Beget."""
    cmd = (
        f"ENV={APP_DIR}/backend/.env; touch \"$ENV\"; "
        "grep -q '^APP_ENV=' \"$ENV\" && sed -i 's/^APP_ENV=.*/APP_ENV=production/' \"$ENV\" || echo 'APP_ENV=production' >> \"$ENV\"; "
        "grep -q '^WHISPER_BACKEND=' \"$ENV\" && sed -i 's/^WHISPER_BACKEND=.*/WHISPER_BACKEND=remote/' \"$ENV\" || echo 'WHISPER_BACKEND=remote' >> \"$ENV\"; "
        f"grep -q '^WHISPER_API_BASE_URL=' \"$ENV\" && sed -i 's|^WHISPER_API_BASE_URL=.*|WHISPER_API_BASE_URL={WHISPER_PROXY_BASE}|' \"$ENV\" || echo 'WHISPER_API_BASE_URL={WHISPER_PROXY_BASE}' >> \"$ENV\"; "
        f"grep -q '^WHISPER_REMOTE_MODEL=' \"$ENV\" && sed -i 's/^WHISPER_REMOTE_MODEL=.*/WHISPER_REMOTE_MODEL={WHISPER_PROXY_MODEL}/' \"$ENV\" || echo 'WHISPER_REMOTE_MODEL={WHISPER_PROXY_MODEL}' >> \"$ENV\"; "
        # Prefer proxy token (AI_API_KEY); do not use blocked direct Groq keys from Beget.
        "A=$(grep '^AI_API_KEY=' \"$ENV\" | head -1 | cut -d= -f2-); "
        "if [ -n \"$A\" ]; then "
        "grep -q '^WHISPER_API_KEY=' \"$ENV\" && sed -i \"s|^WHISPER_API_KEY=.*|WHISPER_API_KEY=$A|\" \"$ENV\" || echo \"WHISPER_API_KEY=$A\" >> \"$ENV\"; "
        "fi; "
    )
    run(client, cmd)


def ensure_venv_and_migrate(client: paramiko.SSHClient) -> None:
    run(
        client,
        f"cd {APP_DIR}/backend && python3 -m venv .venv && "
        f".venv/bin/pip install -U pip && "
        f".venv/bin/pip install -e '.[dev]'",
        timeout=900,
    )
    code, _, _ = run(client, f"cd {APP_DIR}/backend && .venv/bin/alembic upgrade head")
    if code != 0:
        raise SystemExit("alembic upgrade failed")


def write_systemd(client: paramiko.SSHClient) -> None:
    api_unit = f"""[Unit]
Description=Personal Calendar API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory={APP_DIR}/backend
EnvironmentFile={APP_DIR}/backend/.env
ExecStart={APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port {API_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    static_unit = f"""[Unit]
Description=Personal Calendar static SPA
After=network.target

[Service]
Type=simple
WorkingDirectory={APP_DIR}/frontend
ExecStart=/usr/bin/python3 -m http.server {STATIC_PORT} --bind 0.0.0.0 --directory {APP_DIR}/frontend
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
"""
    sftp = client.open_sftp()
    with sftp.open("/etc/systemd/system/personal-calendar-api.service", "w") as f:
        f.write(api_unit)
    with sftp.open("/etc/systemd/system/personal-calendar-web.service", "w") as f:
        f.write(static_unit)
    sftp.close()
    run(client, "systemctl daemon-reload")
    run(
        client,
        f"ufw allow from 172.16.0.0/12 to any port {API_PORT} proto tcp comment 'personal-calendar-api' || true",
    )
    run(
        client,
        f"ufw allow from 172.16.0.0/12 to any port {STATIC_PORT} proto tcp comment 'personal-calendar-web' || true",
    )
    run(client, "systemctl enable --now personal-calendar-api.service personal-calendar-web.service")
    run(client, "systemctl restart personal-calendar-api.service personal-calendar-web.service")


def nginx_http_block() -> str:
    return f"""
{MARKER}
    server {{
        listen 80;
        server_name {DOMAIN};
        client_max_body_size 25M;
        location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
        location /api/ {{
            proxy_pass http://172.19.0.1:{API_PORT};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
        }}
        location / {{
            proxy_pass http://172.19.0.1:{STATIC_PORT};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
"""


def nginx_https_block() -> str:
    return f"""
{MARKER}
    server {{
        listen 80;
        server_name {DOMAIN};
        location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
        location / {{ return 301 https://$host$request_uri; }}
    }}

    server {{
        listen 443 ssl http2;
        server_name {DOMAIN};

        ssl_certificate /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        client_max_body_size 25M;

        location /api/ {{
            proxy_pass http://172.19.0.1:{API_PORT};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
            proxy_send_timeout 120s;
        }}
        location / {{
            proxy_pass http://172.19.0.1:{STATIC_PORT};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
"""


def strip_markers(conf: str) -> str:
    while MARKER in conf:
        start = conf.find(MARKER)
        # remove from marker through the next blank line before following comment/server,
        # by finding matching server blocks until next top-level marker or closing brace of http.
        # Simpler: delete from MARKER to the blank line that precedes the next "# " at column-ish
        # Use brace counting from first "server {" after marker.
        rest = conf[start:]
        server_idx = rest.find("server {")
        if server_idx < 0:
            conf = conf[:start] + conf[start + len(MARKER) :]
            continue
        i = start + server_idx
        # walk both http + https server blocks that belong to this marker section
        # Count braces from first server until we've closed two servers or hit next MARKER/end
        depth = 0
        j = i
        servers = 0
        while j < len(conf):
            if conf.startswith("server {", j):
                servers += 1
            if conf[j] == "{":
                depth += 1
            elif conf[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    # after closing a server, if next nonspace is another server belonging to us, continue
                    k = j
                    while k < len(conf) and conf[k] in " \t\r\n":
                        k += 1
                    if conf.startswith("server {", k) and servers < 2:
                        j = k
                        continue
                    break
            j += 1
        conf = conf[:start] + conf[j:]
    return conf


def ensure_nginx(client: paramiko.SSHClient, https: bool) -> None:
    sftp = client.open_sftp()
    with sftp.open(NGINX_CONF, "r") as f:
        conf = f.read().decode("utf-8")
    conf = strip_markers(conf)
    block = nginx_https_block() if https else nginx_http_block()
    idx = conf.rfind("}")
    conf = conf[:idx] + "\n" + block + "\n" + conf[idx:]
    with sftp.open(NGINX_CONF, "w") as f:
        f.write(conf)
    sftp.close()
    code, _, _ = run(client, "docker exec billing-nginx nginx -t")
    if code != 0:
        raise SystemExit("nginx -t failed")
    run(client, "docker exec billing-nginx nginx -s reload")


def try_ssl(client: paramiko.SSHClient) -> None:
    ensure_nginx(client, https=False)
    run(client, "mkdir -p /var/www/certbot")
    run(
        client,
        f"certbot certonly --webroot -w /var/www/certbot -d {DOMAIN} "
        f"--non-interactive --agree-tos -m {CERTBOT_EMAIL} --keep-until-expiring",
        timeout=180,
    )
    code, _, _ = run(client, f"test -f /etc/letsencrypt/live/{DOMAIN}/fullchain.pem")
    if code == 0:
        ensure_nginx(client, https=True)
        print("HTTPS enabled")
    else:
        print("Cert missing — HTTP only")


def wait_api(client: paramiko.SSHClient) -> None:
    for _ in range(30):
        _, out, _ = run(
            client,
            f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{API_PORT}/api/health || true",
        )
        if "200" in out:
            print("API health 200")
            return
        time.sleep(2)
    run(client, "journalctl -u personal-calendar-api -n 80 --no-pager")
    raise SystemExit("API did not become healthy")


def main() -> None:
    print(f"Packing {ROOT} …")
    bundle = build_tarball()
    print(f"Bundle {len(bundle)} bytes")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password(), timeout=30)

    # Persist DB password across redeploys if container already exists
    db_password = secrets.token_urlsafe(18)
    _, names, _ = run(client, "docker ps -a --format '{{.Names}}'")
    if "calendar-mariadb" in names:
        # keep existing password from current .env if present
        code, out, _ = run(
            client,
            f"grep '^DATABASE_URL=' {APP_DIR}/backend/.env 2>/dev/null || true",
        )
        if "mysql+pymysql://calendar:" in out:
            try:
                db_password = out.split("mysql+pymysql://calendar:", 1)[1].split("@", 1)[0]
            except IndexError:
                pass

    print("Uploading…")
    upload_bundle(client, bundle)
    print("MariaDB…")
    ensure_mariadb(client, db_password)
    print("Env…")
    write_server_env(client, db_password)
    print("Whisper remote…")
    ensure_remote_whisper_env(client)
    print("Python deps + migrations…")
    ensure_venv_and_migrate(client)
    print("systemd…")
    write_systemd(client)
    wait_api(client)
    print("nginx + SSL…")
    try_ssl(client)

    _, out, _ = run(
        client,
        f"curl -sI -o /dev/null -w '%{{http_code}}' --resolve {DOMAIN}:443:{HOST} "
        f"https://{DOMAIN}/ || true",
    )
    print(f"\nDone: https://{DOMAIN}")
    print(f"HTTPS probe: {out.strip()}")
    client.close()


if __name__ == "__main__":
    main()
