# Testing Strategy

Every wave has tests before it is considered complete.

## Layers

### Unit
Pure domain functions:
- recurrence;
- date/time;
- validation;
- task/plan rules;
- trash expiry.

### Integration
- repository persistence;
- import/export;
- notification adapter where practical.

### E2E
Critical user flows:
- create event;
- edit event;
- drag event;
- create recurring event;
- modify one occurrence;
- create plan and checklist;
- create task;
- move dated task;
- create list;
- search/filter;
- trash/restore;
- theme switching.

## Every wave

1. Run existing test suite.
2. Implement.
3. Add/update tests for new behavior.
4. Run targeted tests.
5. Run full regression.
6. Run typecheck/lint/build.
7. Only then mark wave complete.

Never remove tests to make CI green.
