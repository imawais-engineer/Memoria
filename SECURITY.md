# Security Policy

## Reporting a vulnerability
Please **do not open a public issue** for security problems.
Report privately via GitHub: **Security → Report a vulnerability** on this repository, or contact the maintainer through the email on the [GitHub profile](https://github.com/imawais-engineer). Include steps to reproduce and impact. You can expect an acknowledgement within 72 hours.

## Secrets hygiene
- No credentials, API keys, tokens, keystores or `.env` files are committed. Configuration goes through environment variables; see `.env.example` where present.
- Every push, pull request and a weekly full-history run are scanned with [gitleaks](https://github.com/gitleaks/gitleaks) (`.github/workflows/security-scan.yml`).
- If a secret is ever exposed it is **rotated first**, then removed from history.

## Supported versions
Only the latest `main` branch is supported.

## Authentication and isolation
- `/auth/signup` and `/auth/login` return an `access_token` (JWT, HS256, signed with `SECRET_KEY`, `sub` is the user UUID, default lifetime 24 h, `ACCESS_TOKEN_TTL_MINUTES`). Clients send `Authorization: Bearer <token>`.
- Every route that touches user data (chat, sessions, memories, memorize, feedback, tasks, generate, archive, preferences) resolves the user from the token via `get_current_user`. A `user_id` in the body or query is optional; if present and different from the token it is rejected with 403. Row lookups filter by the token's user, so another user's rows return 404.
- With `ENVIRONMENT` other than `dev`, the app refuses to start when `SECRET_KEY` is the default or shorter than 32 characters.
- `X-API-Token` (`DEMO_API_TOKEN`) is an extra guard on destructive routes only while `ALLOW_DEMO_TOKEN` is on (default on in dev, off otherwise). It never identifies a user.
- Limits (`app/services/limits.py`): `RATE_LIMIT_PER_MIN` requests per user per minute on LLM-backed routes, and `DAILY_TOKEN_CAP` estimated tokens per user per UTC day (about 4 characters per token). Both return HTTP 429. Counters are kept in Redis and fall back to per-process memory if Redis is unreachable. Set a value to 0 to disable it.
- Known limits: tokens are stateless and cannot be revoked before expiry (rotate `SECRET_KEY` to invalidate all). The frontend keeps the token in `localStorage`, so an XSS bug would expose it.
