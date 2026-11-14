# FloodShield Backend API Reference

This inventory reflects the routes registered by the Flask backend in this archive. For authentication payloads, identity linking, OTP flows, and FCM token registration, see [API Authentication and Push](API_AUTHENTICATION_AND_PUSH.md).

## Access levels

- **Public:** no FloodShield JWT required.
- **Citizen JWT:** valid FloodShield access token required. Resource ownership is enforced where records are user-owned.
- **Admin JWT:** valid access token belonging to a database user with `role=admin`.
- **Admin browser cookie:** dashboard session established through `/admin/session`; state-changing cookie requests require the CSRF header.

## Health and weather

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Health check |
| GET | `/api/weather/current` | Public | Fetch current weather for latitude/longitude |
| POST | `/api/weather/collect` | Admin JWT | Fetch and store weather observation |
| GET | `/api/weather/latest` | Public | Latest stored weather for coordinates |
| GET | `/api/weather/history` | Public | Stored weather history; bounded `limit` |
| GET | `/api/weather/history/date-range` | Public | Stored weather in an ISO-8601 date range |

Weather coordinate parameters use `latitude` and `longitude`. The history endpoint accepts `limit` from 1 through 100.

## Flood reports and media

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| POST | `/api/reports` | Citizen JWT | Submit a flood report |
| GET | `/api/reports` | Citizen JWT | List visible reports with optional filters and pagination |
| GET | `/api/reports/<report_id>` | Citizen JWT | Read own report, an admin-visible report, or a verified public report |
| POST | `/api/reports/<report_id>/media` | Citizen JWT + ownership | Upload report photographs |
| GET | `/api/reports/<report_id>/media` | Citizen JWT + report visibility | List report photograph metadata |
| GET | `/api/reports/<report_id>/media/<media_id>` | Citizen JWT + report visibility | View one report photograph |
| DELETE | `/api/reports/<report_id>/media/<media_id>` | Citizen JWT + ownership | Delete own report photograph |
| PATCH | `/api/reports/<report_id>/status` | Admin JWT | Update report status |

Report submission uses latitude and longitude, optional `water_depth_cm`, and optional description. Photograph uploads are limited by the backend image validator and report media-count limit.

## Historical flood and weather data

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/historical-floods` | Public | Search/list historical flood events |
| GET | `/api/historical-floods/<event_id>` | Public | Read one historical flood event |
| POST | `/api/historical-floods` | Admin JWT | Create a historical flood event |
| POST | `/api/admin/historical-floods/import` | Admin JWT | Import historical flood events from CSV |
| GET | `/api/historical-weather` | Public | Query historical weather observations |
| GET | `/api/historical-weather/<record_id>` | Public | Read one historical weather observation |

## Risk assessment

All risk routes require a citizen JWT.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/risk/assess` | Calculate and store flood risk near supplied coordinates |
| GET | `/api/risk/latest` | Read the latest assessment near supplied coordinates |
| GET | `/api/risk/history` | Read paginated assessment history near supplied coordinates |
| GET | `/api/risk/<assessment_id>` | Read one stored assessment |

Location parameters are `latitude`, `longitude`, and optional `radius_km`. Coordinates and radius are validated by the backend.

## Notifications

All notification routes require a citizen JWT.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/notifications/device-token` | Register an actual FCM registration token |
| GET | `/api/notifications` | Read the authenticated user's notification history |
| PATCH | `/api/notifications/<notification_id>/read` | Mark an owned notification as read |
| GET | `/api/notifications/preferences` | Read notification preferences |
| PATCH | `/api/notifications/preferences` | Update notification preferences |

The device registration payload is `{"token":"<FCM-registration-token>","platform":"android"}` or `ios`. Do not submit a Firebase Installation ID as the push token. In-app notification storage is independent of FCM delivery.

## Administrator API

All `/api/admin/*` endpoints require Admin JWT access.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/admin/reports/pending` | List pending reports |
| GET | `/api/admin/reports/<report_id>` | Read report details for moderation |
| PATCH | `/api/admin/reports/<report_id>/verify` | Verify a report |
| PATCH | `/api/admin/reports/<report_id>/reject` | Reject a report |
| GET | `/api/admin/reports/<report_id>/history` | Read moderation history |
| GET | `/api/admin/dashboard/stats` | Dashboard statistics |
| GET | `/api/admin/reports` | Search/filter reports |
| GET | `/api/admin/citizens` | List citizens |
| GET | `/api/admin/citizens/<citizen_id>` | Read citizen details |

Admin browser routes use cookie authentication:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/admin/login` | Render administrator login page |
| POST | `/admin/session` | Create administrator browser session |
| GET | `/admin` | Render protected dashboard |
| POST | `/admin/logout` | Revoke browser session and clear cookies |

## Authentication route details

The full authentication contract is documented in [API Authentication and Push](API_AUTHENTICATION_AND_PUSH.md). The legacy Firebase Authentication routes return `410 Gone` and must not be used. Firebase is retained only for FCM push delivery.

## Common behavior

- JSON errors use a consistent `status: error` response.
- Invalid inputs generally return `400`; missing/invalid authentication returns `401`; insufficient role/ownership returns `403` or a not-found response where the route intentionally avoids disclosing another user's resource.
- Rate-limited requests return `429`.
- Authentication responses are marked `Cache-Control: no-store`.
- The global rate limit is 300 requests per hour per client IP; sensitive authentication endpoints apply stricter route-specific limits.
