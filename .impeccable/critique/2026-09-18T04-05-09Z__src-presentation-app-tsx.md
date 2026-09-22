---
target: frontend App shell
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-09-18T04-05-09Z
slug: src-presentation-app-tsx
---
Method: dual-agent (A: 1a7b7ea1-c9a3-4803-a232-43b7c45e2830 · B: dc7878ba-3c32-4ac9-9948-9d4c2ad68a01)

Target: src/presentation/App.tsx (+ AiChatPanel, calendars, CSS)
Mode: Operate
Browser overlays: unavailable (MCP tab could not be held; Vite :5173 HTTP 200 confirmed)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Chat phase pill ok; calendar refresh silent; draft status raw English; nav active CSS may not paint |
| 2 | Match System / Real World | 3 | Russian mostly natural; Trash `entityType` + draft `ready`/`collecting` leak English |
| 3 | User Control and Freedom | 3 | Esc/cancel ok; weak undo; dense day grid hard to escape |
| 4 | Consistency and Standards | 2 | Chat craft ≠ calendar craft; duplicate week date chrome; all scope buttons primary |
| 5 | Error Prevention | 2 | Recurrence scope ok; non-recurring delete unconfirmed; event identity = color only |
| 6 | Recognition Rather Than Recall | 2 | Nav labeled; shortcuts buried in Settings; search hits dead (no jump) |
| 7 | Flexibility and Efficiency | 2 | Shortcuts exist but hidden; week/month DnD incomplete vs UX spec |
| 8 | Aesthetic and Minimalist Design | 1 | Equal-weight chrome; 7 nav peers; cream+teal template kit |
| 9 | Error Recovery | 2 | Chat errors clearer than calendar success |
| 10 | Help and Documentation | 1 | Chat welcome only; no calendar coaching |
| **Total** | | **20/40** | **Poor / low Acceptable** |

## Design Specificity Verdict

**FAIL — category-interchangeable.**

**LLM assessment:** Cream `#f3f1ec` + teal `#0f766e` + IBM Plex + bordered surfaces (`day-calendar.css`) is stock “AI productivity” kit. Calendar chrome is generic CRUD. Only Smart Day and the assistant chat show authored intent.

**Deterministic scan:** `detect.mjs --json` on App/AiChatPanel/Week/Month → exit 0, **0 findings**. Detector did not catch CSS antipatterns or the aria-current contract break (TSX-only scan false negative risk).

**Visual overlays:** No reliable user-visible overlay (browser tab evaporated after navigate). Fallback: HTTP 200 on :5173; judgment from source + Assessment A.

## Technical audit (companion)

| Dimension | Score | Key finding |
|-----------|------:|-------------|
| Accessibility | 3 | Landmarks ok; `aria-current="page"` vs CSS `[aria-current="true"]`; some controls &lt;44px |
| Performance | 3 | Light motion; reduced-motion covered |
| Responsive | 3 | Mobile breakpoints exist; week grid horizontal squeeze |
| Theming | 3 | Light/dark tokens; hardcoded `#fff` on event blocks |
| Implementation Integrity | 1 | Active-nav styles never match live attribute |
| **Total** | **13/20** | **Acceptable — integrity weak** |

## Overall Impression

Backend/AI path is serious; the board UI still looks like a wave-1 scaffold with a nicer chat bolted on. Biggest opportunity: one authored **today** surface (calendar day under pressure) and demote the rest — stop treating seven peers as equal.

## What's Working

1. **Assistant shell** — phase pill, draft confirm, mic pulse, enter motion (`app-shell.css` / `AiChatPanel.tsx`).
2. **Operate-floor basics** — `--control-min: 44px`, focus-visible, reduced-motion, Russian empty-state next steps.
3. **Smart Day IA** — current / elapsed / remaining / next is product-specific thinking the chrome elsewhere ignores.

## Priority Issues

### [P0] Interchangeable visual system
- **What:** Cream/teal/Plex template; day = 24-row ledger; events = colored bricks with hover-only actions.
- **Why:** Feels like any SaaS admin, not a personal calendar; user correctly calls it primitive.
- **Fix:** Replace visual world (time/pressure metaphor OR clear Russian calendar identity); hierarchy for now-line, dim past, dense next hours; real resize handles.
- **Suggested command:** `/impeccable shape` then `/impeccable bolder` (or full redesign via init + new-work)

### [P0] Active nav styles broken (integrity)
- **What:** `aria-current="page"` in `App.tsx` vs `[aria-current="true"]` in CSS — accent never applies.
- **Why:** User cannot see where they are; fails status visibility.
- **Fix:** Align selector to `[aria-current="page"]` (or set attribute `"true"`).
- **Suggested command:** `/impeccable polish` (quick) or harden

### [P1] Nav bloat vs UX spec
- **What:** 7 equal peers (Сейчас / Ассистент / Календарь / …); startup = `now`, spec says open Today.
- **Why:** Primary job (plan the day) buried; first-timers don’t know where “today” lives.
- **Fix:** Collapse to spec primary nav; nest Smart Day + Assistant into Calendar/today; default section = calendar day.
- **Suggested command:** `/impeccable distill` + `/impeccable layout`

### [P1] Craft schizophrenia
- **What:** Chat has radial wash/bubbles; week/month are bare grids with duplicate prev/next.
- **Why:** Product feels unfinished; assistant “voted” as the real UI.
- **Fix:** One system: shared density, type scale, surfaces for day/week/month to match or intentionally defer to chat.
- **Suggested command:** `/impeccable typeset` + `/impeccable layout`

### [P2] Cognitive overload on create
- **What:** Event form dumps recurrence radios, weekdays, ends, reminders, color, notes at once; scope dialog all-primary buttons.
- **Why:** Creates anxiety; blocks confident first event.
- **Fix:** Progressive disclosure; one primary action in scope dialog.
- **Suggested command:** `/impeccable distill` + `/impeccable clarify`

## Persona Red Flags

**Jordan (First-Timer):** 7 destinations; Сейчас vs Календарь unclear; English draft status; Trash `event:` jargon; three create paths (hour click / form / Ассистент) compete.

**Alex (Power):** Shortcuts hidden in Settings; no bulk; week/month DnD incomplete vs `05_UI_UX.md`; resize affordance is “↕”.

**Casey (Mobile):** Wrapped top nav not thumb-primary; day = endless 24h scroll; week `minmax(110px)` × 7 forces horizontal scroll.

## Minor Observations

- Search results list titles with no navigation to the entity.
- `DEFAULT_COLOR` equals accent — events blend into brand.
- Month ≤2 titles is good restraint; week white-on-color scan is poor.
- Dark theme tokens exist; light is the bland default.
- Plans/tasks in `<details>` under day — good disclosure, visually orphaned.

## Questions to Consider

1. If you stripped the AI chat, would anything left feel like *this* calendar?
2. Should one surface own “today” (Сейчас *or* День)?
3. Day as time-under-pressure (now-line, dim past) vs 24-row ledger?
4. Is the assistant the product and the calendar a read-back — or the reverse?
5. Defend a distinct metaphor (stationery / wall calendar / metro schedule) against cream+teal SaaS?
