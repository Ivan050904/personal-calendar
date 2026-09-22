# Project Setup

The project uses npm, React, TypeScript, and Vite. Node.js 24 or newer is required.

## Commands

```bash
npm install
npm run dev
npm test
npm run typecheck
npm run lint
npm run build
```

## Source directories

The source tree follows the layers defined in `03_ARCHITECTURE.md`:

- `src/presentation` contains React UI;
- `src/application` contains use cases;
- `src/domain` contains pure models and rules;
- `src/infrastructure` contains persistence and external adapters.

There is intentionally no formatter configuration: the project did not have an existing formatter convention at bootstrap.

## Local persistence bootstrap

Wave 1 defines typed domain entities, pure validation, stable UUID generation, and repository interfaces. `src/infrastructure/indexed-db-repositories.ts` implements those interfaces with IndexedDB. On first use, the app creates one `Personal Calendar` using the device timezone supplied by the caller. Categories are intentionally not seeded; users create them themselves.

## Day calendar

The application opens the current day and displays a 24-hour timeline. Clicking an empty hour opens an event form with that date and time prefilled. Events can be created, edited, and soft-deleted; their calendar timezone is respected when converting between form values and stored timestamps. Week, month, recurrence, and drag/resize interactions are intentionally outside this wave.

## Week calendar

The Week view uses a Monday-first grid and time column. It navigates in seven-day increments, splits multi-day events across their relevant day columns, and assigns separate widths to overlapping segments.
