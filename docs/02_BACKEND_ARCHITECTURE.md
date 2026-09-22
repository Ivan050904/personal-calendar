# Backend Architecture

## Stack
Python + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic + MySQL 8.x + pytest + HTTPX + Uvicorn.

## Почему MySQL
Для одного пользователя PostgreSQL не даёт обязательного преимущества. MySQL полностью подходит для CRUD/API календаря. Важнее миграции, стабильные ID, service/repository boundaries и переносимость данных.

## Docker
Не использовать в MVP. Архитектура:
Browser → FastAPI → MySQL.

Docker можно добавить позже как инфраструктурное решение большого приложения.

## Слои
- API: HTTP/DTO/errors.
- Application: use cases.
- Domain: календарные правила и recurrence.
- Infrastructure: MySQL/SQLAlchemy/AI/Whisper.
- AI: natural language → structured proposal.

AI не вызывает repositories и не знает SQL.

## Suggested structure
backend/
  app/
    main.py
    core/
    api/routes/
    domain/
    application/
    infrastructure/db/
    infrastructure/repositories/
    ai/
    whisper/
    schemas/
  alembic/
  tests/
  pyproject.toml
  .env.example

Можно адаптировать имена под фактический репозиторий, сохранив границы ответственности.

## Future integration
API versioned; UUID/client IDs; createdAt/updatedAt/deletedAt; revision/version где это не создаёт лишней сложности. Будущий путь: local Calendar → account/auth → import/migration → unified DB.
