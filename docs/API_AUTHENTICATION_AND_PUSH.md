# FloodShield API: Authentication and Push Notifications

This document describes the backend contract present in this archive after the consolidated security update.

## Authentication model

- Citizen email/password, backend-managed phone OTP, and Google Sign-In are supported.
- Email and phone OTPs are generated and verified by the FloodShield backend.
- Fast2SMS transports phone OTP messages; it does not generate or verify OTPs.
- Google ID tokens are verified by the backend against `GOOGLE_CLIENT_ID`.
- Firebase is used only for Firebase Cloud Messaging (FCM) push delivery.
- Admin API authentication remains separate from citizen account registration.
- Public registration always creates a citizen; never accept a public `role=admin` field.

All bearer-token API calls use:

```http
Authorization: Bearer <access_token>
```

Access tokens expire after 15 minutes. Refresh tokens expire after 30 days and are rotated by `/api/auth/refresh`. Reuse of a rotated refresh token revokes the associated session family. Logout revokes the current session family.

## Citizen authentication endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register a citizen account |
| POST | `/api/auth/verify-email` | Verify registration email OTP |
| POST | `/api/auth/resend-email-otp` | Resend registration email OTP |
| POST | `/api/auth/login` | Email/password citizen login |
| POST | `/api/auth/phone/request-otp` | Request phone login OTP |
| POST | `/api/auth/phone/verify-otp` | Verify phone OTP and log in |
| POST | `/api/auth/google` | Verify Google ID token and log in/register |
| POST | `/api/auth/forgot-password` | Request email password-reset OTP |
| POST | `/api/auth/reset-password` | Verify email OTP and set a new password |
| POST | `/api/auth/phone/recover-password/request-otp` | Request OTP for an already verified phone |
| POST | `/api/auth/phone/recover-password/verify-otp` | Verify phone OTP and reset password |
| POST | `/api/auth/change-password` | Change password for authenticated citizen |
| POST | `/api/auth/refresh` | Rotate refresh token and issue a new pair |
| POST | `/api/auth/logout` | Revoke the current session family |

### Typical payloads

Registration:

```json
{
  "name": "Citizen Name",
  "email": "citizen@example.com",
  "password": "Use-A-Strong-Password"
}
```

Email verification:

```json
{
  "email": "citizen@example.com",
  "otp": "123456"
}
```

Email/password login:

```json
{
  "email": "citizen@example.com",
  "password": "Use-A-Strong-Password"
}
```

Phone OTP request and verification:

```json
{
  "phone_number": "9876543210"
}
```

```json
{
  "phone_number": "9876543210",
  "otp": "123456"
}
```

Google login:

```json
{
  "id_token": "<Google-issued-ID-token>"
}
```

The backend does not trust a client-supplied email or Google subject. It verifies the ID token itself. If an account with the same email already exists but the Google subject is not linked, the backend refuses automatic account merging. The user must authenticate with the existing method and use the explicit linking endpoint.

Password reset:

```json
{
  "email": "citizen@example.com"
}
```

```json
{
  "email": "citizen@example.com",
  "otp": "123456",
  "new_password": "Another-Strong-Password"
}
```

Phone recovery:

```json
{
  "phone_number": "9876543210"
}
```

```json
{
  "phone_number": "9876543210",
  "otp": "123456",
  "new_password": "Another-Strong-Password"
}
```

Password change:

```json
{
  "current_password": "Current-Password",
  "new_password": "New-Strong-Password"
}
```

Password changes and recovery revoke existing refresh-session families. The client must sign in again.

## Identity linking and unlinking

All linking/unlinking endpoints require a citizen access token. They also require fresh proof of an already linked method: `current_password`, a verified `current_google_id_token`, or a one-time `current_phone_otp` with `current_phone_number`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/email/link/request-otp` | Send OTP to a new email |
| POST | `/api/auth/email/link/verify-otp` | Verify and replace the account email |
| POST | `/api/auth/phone/link/request-otp` | Send OTP to a new phone |
| POST | `/api/auth/phone/link/verify-otp` | Verify and link the phone |
| POST | `/api/auth/google/link` | Link a verified Google identity |
| POST | `/api/auth/identities/unlink` | Unlink `email`, `phone`, or `google` |

Email-link request:

```json
{
  "email": "new-address@example.com",
  "current_password": "Current-Password"
}
```

Email-link verification:

```json
{
  "email": "new-address@example.com",
  "otp": "123456"
}
```

Phone-link request:

```json
{
  "phone_number": "9876543210",
  "current_password": "Current-Password"
}
```

Phone-link verification:

```json
{
  "phone_number": "9876543210",
  "otp": "123456"
}
```

Google linking:

```json
{
  "id_token": "<Google-issued-ID-token>",
  "current_password": "Current-Password"
}
```

Unlinking:

```json
{
  "identity": "google",
  "current_password": "Current-Password"
}
```

A user must retain at least one usable sign-in method. An email identity can be unlinked only when another verified method remains; unlinking email also removes the password login associated with that email.

## Retired Firebase Authentication endpoints

The following legacy routes remain registered for compatibility but return HTTP `410 Gone`:

- `POST /api/auth/firebase`
- `POST /api/auth/firebase/link`

Do not call these routes from the Android app. Use backend phone OTP or Google Sign-In instead.

## FCM device registration

The Android client must obtain an **FCM registration token** from Firebase Messaging and send that token to FloodShield. A Firebase Installation ID (FID) is not an FCM message destination.

```http
POST /api/notifications/device-token
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "token": "<FCM-registration-token>",
  "platform": "android"
}
```

Supported platforms are `android` and `ios`. The backend stores the token, associates it with the authenticated user, and uses the token as the FCM message destination. Legacy FIDs remain stored for compatibility but are not used for push delivery.

Backend in-app notification records are saved independently of FCM delivery. A failed or unavailable push service must not remove the in-app notification.

## Admin authentication

- API administrator login: `POST /api/auth/admin/login`
- Browser dashboard login: `POST /admin/session`
- Dashboard: `GET /admin`
- Browser logout: `POST /admin/logout`

Admin registration is not public. Admin accounts must be created through a trusted administrative process. Browser sessions use the same server-side session-family revocation checks as API token sessions. Browser logout requires the JWT cookie CSRF header.

## Common responses

Successful responses use `{"status":"success", ...}`. Errors use `{"status":"error","message":"..."}`. Rate-limited requests return HTTP `429`. Retired Firebase Authentication endpoints return HTTP `410`.
