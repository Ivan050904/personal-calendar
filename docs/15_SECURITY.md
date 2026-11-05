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

Connected apps (D35, wave 3): only owner-registered OAuth clients; exact `redirect_uri` match; Authorization Code + PKCE S256 for every client; codes (60 s, single use), access (15 min) and refresh (30 days, rotating) tokens stored only as SHA-256. Replaying a code or a rotated refresh token revokes the whole grant. Consent and login pages: CSRF token bound to the session, `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `Referrer-Policy: same-origin` (no-referrer made browsers send `Origin: null` and broke the form). The token endpoint shares the login rate limiter. An app token reaches only `/api/v2/calendars` (GET), `/api/v2/events*` and `/api/oauth/userinfo`, reads only calendars the user ticked, and writes only into its own app calendar; it never gets the calendar cookie. Users revoke apps in Settings → «Подключённые приложения»; tokens die immediately.

Sync and webhooks (D37, wave 4):
- An app's changes feed covers only the calendars it may read, and its cursors are HMAC-signed and bound to that connection.
- Webhooks go only to https URLs and carry no event data, only a hint and a feed cursor. They are signed with HMAC-SHA256 over `timestamp.body` using a per-subscription secret, which the server must keep in clear to sign.
- Before every delivery each resolved address of the host must be public (no loopback, private, link-local or metadata ranges); redirects are not followed; the timeout is 5 s. Residual risk: DNS can change between this check and the connection (rebinding). This is accepted for now because only owner-registered apps can add webhooks.
