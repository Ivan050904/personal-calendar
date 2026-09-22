# Test Cases

1. `Создай событие завтра в 15:00 стоматолог на час` → Event draft, correct time/duration.
2. `Создай задачу завтра купить молоко` → Task, no invented time.
3. `Создай список Покупки: молоко, хлеб` → ordered List.
4. `Создай план уборки в субботу с 10 до 14: помыть пол, пропылесосить` → Plan + 2 tasks.
5. `Завтра надо купить молоко` → ask type.
6. `Создай событие завтра вечером` → ask exact time.
7. `Создай событие с 15 до 17` → ask date.
8. `Создай событие завтра после работы` → ask exact time.
9. `Создай событие на два часа` → ask start.
10. `Создай событие по вторникам в 18:00 тренировка` → weekly recurrence.
11. `Каждый понедельник и четверг в 10 уборка` → selected weekdays.
12. `Бесконечно` → never.
13. `Перенеси тренировку на 21:00` → target resolution + Draft + confirmation.
14. Recurring update/delete → scope required.
15. Confirm twice → no duplicate.
16. Cancel → no mutation + context close.
17. Target changed before confirm → conflict.
18. `Какая погода завтра?` → domain-only response.
19. Prompt injection → ignored.
20. Invalid backend payload → 4xx.
21. AI timeout → stable error.
22. Whisper timeout → stable error.
23. Expired Draft → no mutation.
24. Smart Day current event → correct elapsed/remaining.
25. No current event → `Сейчас свободно` + next.
26. Exact start/end boundaries.
27. Timezone/DST.
28. Full existing frontend regression.
