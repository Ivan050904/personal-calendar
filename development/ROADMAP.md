# Roadmap

## Wave 0 — Audit/baseline ✅
Inspect actual repo, stack, package manager, tests, lint, typecheck, build, current domain/repository. Do not rewrite working code.

## Wave 1 — Backend foundation ✅
FastAPI, config, .env.example, MySQL connection, SQLAlchemy, Alembic, health, errors, tests, startup docs.

## Wave 2 — Persistence ✅
Map current Calendar/Event/Plan/PlanTask/Task/List/ListItem/Category/Reminder semantics to MySQL; migrations; repositories; tests.

## Wave 3 — API bridge ✅
DTOs + CRUD/API services; preserve IndexedDbRepository; add ApiRepository path without duplicating domain logic.

## Wave 4 — Smart Day ✅
Current/next/free, elapsed/remaining, real-time UI, tests.

## Wave 5 — Plan progress ✅
Computed completed/total and percentage, UI + tests.

## Wave 6 — AI provider ✅
AIProvider abstraction, Grok/NVIDIA provider based on available configuration, structured output, timeout/retry, mocked tests.

## Wave 7 — AI behavior ✅
Intent, type extraction, clarification, off-topic, recurrence, anti-hallucination, prompt tests.

## Wave 8 — Draft engine ✅
Draft states, validation, confirmation, cancel, expiry, idempotency, tests.

## Wave 9 — Create operations ✅
Event/Plan/Task/List creation, domain execution, confirmation, tests.

## Wave 10 — Target/update/delete ✅
TargetSelector, candidate resolution, ambiguity, update/delete, recurring scopes, conflicts, confirmation, tests.

## Wave 11 — AI chat UI ✅
Text + voice UI shell, compact Draft card, Create/Edit/Cancel, success, automatic context close, mobile.

## Wave 12 — Whisper ✅
Recording, 20 sec limits, backend Whisper (`openai/whisper` from GitHub), benchmark on RTX 3050 → `small`.

## Wave 13 — Security/resilience ✅
Secrets, limits, safe logs, provider/DB failures, stale drafts, concurrency, local-only deployment boundary.

## Wave 14 — Full E2E ✅
Frontend→FastAPI→MySQL; real provider smoke (Groq); voice→Whisper path stubbed until model install; create/update/delete/Smart Day; regression.

## Wave 15 — Final audit ✅
Requirement-by-requirement audit, all tests, lint, typecheck, build, migration verification, secret scan, docs/changelog. Then STOP.
