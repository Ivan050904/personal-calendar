# Security

Never commit API keys, DB passwords or real secrets.

Use backend `.env`; provide `.env.example`.

Never send AI provider keys to frontend.

Never log keys/passwords/raw auth headers.

MVP can be unauthenticated only for local IndexedDB opt-out (`VITE_USE_API=false`). Do not expose an unauthenticated API publicly.

API mode uses single-user session auth (D17): httpOnly cookie after `POST /api/auth/login`; credentials live only in backend env.

AI has no SQL/repository/DB credential access.

Audio temporary data must be removed.

Before public deployment: HTTPS + auth (D17) are required.

Accounts (D34): passwords stored only as Argon2id hashes; unknown login and wrong password return the same 401 and cost the same time; failed logins are rate-limited per login and per IP; password change/reset revokes sessions. Self-registration stays off (`REGISTRATION_ENABLED=false`) until anti-abuse protection exists. Owner-issued temporary passwords are printed once and never logged.
