# FloodShield Security and Deployment Guide

## Production configuration

Set `APP_ENV=production` and configure the following environment variables outside source control.

| Variable | Required | Purpose |
|---|---:|---|
| `SECRET_KEY` | Yes | HMAC key for OTP hashing and Flask signing |
| `JWT_SECRET_KEY` | Yes | JWT signing key; must be different from `SECRET_KEY` |
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `RATELIMIT_STORAGE_URI` | Yes | Shared Redis storage URL for distributed rate limits |
| `FIREBASE_CREDENTIALS_PATH` | Yes for production push | Path to Firebase service-account JSON used for FCM only |
| `FAST2SMS_API_KEY` | For phone OTP | Fast2SMS transport credential |
| `FAST2SMS_SENDER_ID` | Provider-dependent | Fast2SMS sender configuration |
| `FAST2SMS_MESSAGE_ID` | Provider-dependent | Fast2SMS message/template configuration |
| `GOOGLE_CLIENT_ID` | For Google Sign-In | Expected Google OAuth client ID / audience |
| `SMTP_HOST` | For email OTP | SMTP host |
| `SMTP_PORT` | For email OTP | SMTP port, commonly 587 with STARTTLS |
| `SMTP_FROM_EMAIL` | For email OTP | Verified sender address |
| `SMTP_USERNAME` | Optional | SMTP username |
| `SMTP_PASSWORD` | Optional | SMTP password; configure together with username |
| `SMTP_USE_TLS` | Optional | Defaults to `true` |
| `SMTP_USE_SSL` | Optional | Defaults to `false`; cannot be true with TLS |
| `SMTP_TIMEOUT_SECONDS` | Optional | SMTP timeout; defaults to 15 |
| `CORS_ORIGINS` | Optional | Comma-separated explicit browser origins allowed to call `/api/*` |
| `RATELIMIT_STORAGE_URI` | Yes in production | Shared Redis-backed rate-limit storage |
| `LOG_LEVEL` | Optional | Defaults to `INFO` |
| `WEATHER_API_URL` | Optional | Defaults to Open-Meteo forecast endpoint |

Production startup rejects missing/weak signing secrets, identical signing secrets, a missing/non-PostgreSQL database URL, and missing/in-memory rate-limit storage. Production also requires Firebase service-account credentials for FCM push delivery.

Generate separate random secrets; for example, use a cryptographically secure password generator to create two independent values of at least 32 characters. Do not use the example values in automated tests or documentation as production secrets.

## Example `.env.example`

Copy this template to `.env` locally and replace every placeholder. Never commit `.env`.

```dotenv
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-secret
JWT_SECRET_KEY=replace-with-a-different-long-random-secret
DATABASE_URL=sqlite:///floodshield.db
RATELIMIT_STORAGE_URI=memory://

GOOGLE_CLIENT_ID=
FIREBASE_CREDENTIALS_PATH=

FAST2SMS_API_KEY=
FAST2SMS_SENDER_ID=
FAST2SMS_MESSAGE_ID=

SMTP_HOST=
SMTP_PORT=587
SMTP_FROM_EMAIL=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=15

CORS_ORIGINS=
LOG_LEVEL=INFO
```

For production, replace SQLite with PostgreSQL and `memory://` with a shared Redis URL. Never put credentials in Android source code, API responses, logs, or ZIP archives.

## Security controls in the application

- OTPs are randomly generated, HMAC-hashed at rest, time-limited, one-time use, and attempt-limited.
- OTP resend cooldowns and endpoint-level limits protect authentication workflows.
- Rate limiting has a general default cap; sensitive authentication endpoints have stricter limits.
- Production rate limiting requires shared storage so multiple workers enforce the same counters.
- Access tokens are short-lived; refresh tokens are rotated and stored as hashes.
- Reuse of a rotated refresh token revokes the session family.
- Logout, password change, and password recovery revoke active session families.
- Admin browser login creates a server-side session family; browser logout revokes it and clears cookies.
- Cookie-authenticated state-changing requests use CSRF protection.
- CORS is disabled unless explicit origins are configured; wildcard origins are not used.
- Responses include baseline security headers; HTTPS responses include HSTS.
- Authentication responses use `Cache-Control: no-store`.
- Report images are checked against allowed extensions, signatures, image formats, dimensions, size, and animation restrictions.
- User-owned report and notification resources are queried with ownership checks.
- Firebase Authentication routes are retired; Firebase Admin is initialized only for FCM push delivery.

## Deployment checklist

1. Deploy behind HTTPS only; terminate TLS at a trusted reverse proxy.
2. Set `APP_ENV=production`.
3. Set two separate random signing secrets of at least 32 characters.
4. Configure PostgreSQL and Redis.
5. Configure Fast2SMS and SMTP credentials as environment variables.
6. Configure Google OAuth client ID if Google Sign-In is enabled.
7. Store Firebase service-account JSON outside the repository and set `FIREBASE_CREDENTIALS_PATH`.
8. Configure `CORS_ORIGINS` only if a browser frontend is hosted on a different origin. Android native clients do not rely on browser CORS.
9. Run `flask db upgrade`.
10. Run `pytest -q` in the deployed build environment before release.
11. Verify OTP delivery using real provider credentials in a controlled test account.
12. Verify FCM delivery using a real Android FCM registration token.
13. Verify in-app notifications still appear if FCM is unavailable.
14. Confirm secrets, database files, service-account JSON, uploads, and logs are not publicly served or committed.
15. Back up PostgreSQL and test restoration before production launch.

## Local Windows verification

From the backend project directory with the virtual environment activated:

```cmd
python -m compileall -q app migrations tests
flask db current
flask db heads
pytest -q
```

The current Phase 7 archive has one migration head (`c6f7a8b9d0e1`). This consolidated update does not add a database migration: the FCM `token` column already exists, and the security changes use existing session and identity tables. Confirm that `flask db current` and `flask db heads` match on the local working database.
