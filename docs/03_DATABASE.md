# Database — MySQL

MySQL 8.x — backend storage MVP.

Сохраняются существующие сущности:
Calendar, Event, recurrence rules/exceptions, Plan, PlanTask, Task, List, ListItem, Category, Reminder и необходимые Settings.

Все изменения схемы — только через Alembic.

Date-only Task.dueDate хранится как date semantic, без UTC-сдвига. Task.recurrenceRuleId (optional) ссылается на RecurrenceRule; для повторяющихся задач dueDate обязателен (ADR-015).

Event/Plan сохраняют локально-задуманное время и timezone semantics.

Soft delete и Trash 30 дней сохраняются.

AI отдельной БД не получает.

Пароли и API keys только через environment. Реальные секреты не коммитить.

Будущая миграция: JSON export/import или DB migration → единая БД большого приложения. Не проектировать MVP как необратимый тупик.

Проверка на MySQL/MariaDB (production — MariaDB в Docker, D18):
- тесты сервера по умолчанию идут на временной SQLite;
- `TEST_DATABASE_URL=mysql+pymysql://user:pass@host:port/empty_db python -m pytest` гоняет тот же набор на пустой базе MySQL/MariaDB (кодировка utf8mb4);
- DATETIME в MySQL/MariaDB хранит целые секунды. Там, где порядок внутри секунды важен (`calendar_confirmations.recorded_at`), колонка объявлена как `DATETIME(6)`.
- Сопоставление по умолчанию в `mariadb:11` (`utf8mb4_uca1400_ai_ci`) не различает регистр и диакритику: `external_id` событий, задач и планов поэтому эти колонки на MySQL/MariaDB объявлены с `utf8mb4_bin` (миграция `4b5c6d7e8f96`) и сравниваются с учётом регистра, как на SQLite (решение владельца 2026-11-06).
