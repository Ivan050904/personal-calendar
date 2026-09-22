# AI Validation

AI output is untrusted input.

Validation:
1. JSON/schema.
2. Domain.
3. Required fields.
4. Date/time.
5. Recurrence.
6. Target resolution.
7. Final validation immediately before mutation.

Never trust model IDs, SQL, arbitrary fields or claims of success.

Confirm endpoint is a security boundary.

Repeated confirmation must be idempotent.

Multi-record writes must be transactional.

If target changed/deleted after Draft creation, do not overwrite silently; require conflict/reconfirmation.
