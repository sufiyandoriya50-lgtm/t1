# Consolidated FloodShield Phases 8–10 Change Log

## Phase 8 — Security hardening

- Added production validation for strong, separate Flask and JWT signing secrets.
- Added explicit-origin CORS configuration; CORS remains disabled when no origins are configured.
- Added baseline security response headers and HSTS on HTTPS responses.
- Added `no-store` caching policy for authentication and admin session responses.
- Added a default API rate limit while retaining stricter limits on authentication routes.
- Fixed the Phase 7 phone-link OTP request argument mismatch.
- Revoked active session families after email password reset and authenticated password change.
- Applied server-side session-family tracking and revocation to admin browser sessions.
- Retired Firebase Authentication login/link endpoints with HTTP 410 responses.
- Hardened auth JSON payload shape handling.

## Phase 9 — Regression and security tests

- Updated Firebase legacy route tests to assert HTTP 410.
- Updated device-registration and push-delivery tests to use FCM registration tokens.
- Added tests for actual FCM token registration and ownership protection.
- Added tests for phone-link route argument binding.
- Added tests for password-reset session revocation.
- Added tests for security headers, auth no-store headers, explicit CORS origins, and admin browser session revocation.
- Updated production config tests for strong separate signing secrets.

## Phase 10 — Documentation and frontend readiness

- Added `docs/API_AUTHENTICATION_AND_PUSH.md`.
- Added `docs/SECURITY_DEPLOYMENT.md`.
- Added this change log.
- Updated the API route inventory.

## Migration impact

No database migration is required for this batch. The archive already includes `DeviceToken.token`, `RefreshSession`, and `RevokedToken`; the changes use these existing structures. Do not run `flask db migrate` for this batch. `flask db upgrade` is safe to run as a status-preserving check, but the revision should remain unchanged.

## Verification status

The source archive compiled successfully before editing. The updated Python files are syntax-compiled after editing. Full pytest execution requires the project's Flask/JWT/Firebase dependencies, which are not installed in the preparation environment. Run the full suite in the project's activated Windows virtual environment before treating the implementation as verified.
