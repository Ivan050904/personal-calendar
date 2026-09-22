# Draft Lifecycle

States:
collecting, ready, confirmed, cancelled, expired, failed.

Draft:
draftId, conversationId/requestId, operation, entityType, payload, target, missingFields, status, createdAt, updatedAt, expiresAt.

Flow:
AI proposal → validate → Draft.
Missing fields → clarification → same Draft.
Ready → compact card.
Confirm → revalidate → execute → confirmed.
Cancel → cancelled; no domain mutation.

Confirm is idempotent. Repeated confirm cannot duplicate.

If target changed between draft and confirmation, return conflict/reconfirmation.

Draft TTL must be bounded and documented.
