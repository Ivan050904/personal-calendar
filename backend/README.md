# Backend — local startup

## Prerequisites
- Python 3.12+
- MySQL 8.x or MariaDB (local, no Docker)
- Database `calendar` and user (example below)

## One-time DB setup (MariaDB / MySQL)

```bat
"C:\Program Files\MariaDB 13.0\bin\mysqld.exe" --defaults-file="C:\Program Files\MariaDB 13.0\data\my.ini"
```

In another terminal:

```bat
"C:\Program Files\MariaDB 13.0\bin\mysql.exe" -u root -e "CREATE DATABASE IF NOT EXISTS calendar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'calendar'@'localhost' IDENTIFIED BY 'calendar_dev'; GRANT ALL PRIVILEGES ON calendar.* TO 'calendar'@'localhost'; FLUSH PRIVILEGES;"
```

## Backend setup

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Edit `.env` if your DB credentials differ. Put AI keys only in `.env` (never commit).

## Migrations

```bat
cd backend
.venv\Scripts\activate
alembic upgrade head
```

## Run API

```bat
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Health check: http://127.0.0.1:8000/api/health

## Tests

```bat
cd backend
.venv\Scripts\activate
pytest
```

## Whisper (local)

Installed from GitHub `openai/whisper` into `backend/.venv`.
Benchmark on this machine (RTX 3050): `small` selected (~1.4s / ≤20s clip, ~1GB VRAM).

```bat
cd backend
.venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install "git+https://github.com/openai/whisper.git" soundfile
```

Set in `.env`: `WHISPER_MODEL=small`

Status: `GET http://127.0.0.1:8000/api/ai/whisper/status`
Transcribe: `POST /api/ai/transcribe` (multipart `audio`)
