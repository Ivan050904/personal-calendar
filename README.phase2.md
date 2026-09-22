# Calendar — финальный пакет для Cursor

Технический пакет для реализации существующего календаря + Smart Day + специализированного AI + backend.

## Зафиксированные решения
- Backend: Python + FastAPI + MySQL 8 + SQLAlchemy 2.x + Alembic + Pydantic v2.
- Docker **не требуется** для MVP.
- MySQL работает локально.
- Позже данные можно мигрировать в единую БД большого приложения через миграции/экспорт-импорт.
- AI не имеет прямого доступа к БД и не выполняет SQL.
- AI предлагает структурированную операцию; backend валидирует её; запись выполняется только после подтверждения.
- AI работает только с событиями, планами, задачами и списками.
- Голос: локальный Whisper, около 20 секунд максимум.
- API-ключи только в backend `.env`.

## Главный стартовый промпт
`prompts/START_ALL_WAVES.md`

Он заставляет Cursor пройти все волны последовательно в одном запуске, после каждой волны выполнять quality gate и автоматически переходить дальше. Не спрашивать «что дальше?», пока roadmap не закончена.

## Документы
- `docs/01_CHANGE_SPEC.md`
- `docs/02_BACKEND_ARCHITECTURE.md`
- `docs/03_DATABASE.md`
- `docs/04_API_CONTRACT.md`
- `docs/05_SMART_DAY.md`
- `docs/06_AI_ARCHITECTURE.md`
- `docs/07_AI_BEHAVIOR.md`
- `docs/08_AI_ACTIONS.md`
- `docs/09_AI_DRAFTS.md`
- `docs/10_AI_CONTEXT.md`
- `docs/11_AI_PROMPTS.md`
- `docs/12_AI_VALIDATION.md`
- `docs/13_WHISPER.md`
- `docs/14_TEST_CASES.md`
- `docs/15_SECURITY.md`
- `docs/16_LOCAL_SETUP.md`
- `docs/17_DECISIONS.md`
- `development/ROADMAP.md`
- `development/QUALITY_GATE.md`
- `development/CURRENT_TASK.md`
- `development/CHANGELOG.md`
- `prompts/START_ALL_WAVES.md`
- `prompts/WAVE_EXECUTION.md`
