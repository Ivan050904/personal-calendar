# AI Context

Пока Draft активен, AI получает только релевантный контекст:
- Draft;
- unresolved fields;
- recent messages;
- sanitized target candidates if needed.

После confirm/cancel/expiry context closes automatically.

`+ Новая команда` может существовать как ручной reset, но не обязателен.

AI не строится как календарный search/Q&A assistant. Пользователь смотрит календарь сам.

Для update/delete backend может передавать минимальные candidate summaries.
