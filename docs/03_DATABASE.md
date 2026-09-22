# Database — MySQL

MySQL 8.x — backend storage MVP.

Сохраняются существующие сущности:
Calendar, Event, recurrence rules/exceptions, Plan, PlanTask, Task, List, ListItem, Category, Reminder и необходимые Settings.

Все изменения схемы — только через Alembic.

Date-only Task.dueDate хранится как date semantic, без UTC-сдвига.

Event/Plan сохраняют локально-задуманное время и timezone semantics.

Soft delete и Trash 30 дней сохраняются.

AI отдельной БД не получает.

Пароли и API keys только через environment. Реальные секреты не коммитить.

Будущая миграция: JSON export/import или DB migration → единая БД большого приложения. Не проектировать MVP как необратимый тупик.
