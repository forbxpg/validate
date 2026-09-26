# vld-auth

Accounts of validate: registration by email and password, address confirmation,
login, sessions, password reset and change, roles, the admin flag and the audit
of all of it. Login through MEPhI CAS comes later, as one more way in.

## Layout

```
domain/          User, Profile, VerificationToken, Role, errors, events
application/     use cases by process, ports, the AuthApi contract for neighbours
infrastructure/  ORM models, repositories, bcrypt, JWT, Redis stores, letters
api/             routers and schemas, one module per process; the descriptor
di/              dishka providers; AUTH_PROVIDERS is the whole set
console/         vld-auth: what only an operator with shell access may do
migrations/      the revisions of the auth schema
```

## Accounts

- An address is stored lower-cased; a CHECK holds it, a unique index keeps one
  account per address.
- The role (`student` or `teacher`) is picked at registration. Admin rights are a
  flag set only from the console: `vld-auth grant-admin EMAIL`.
- An account is active or turned off (`is_active`). Deleting is for good and only
  from the console: `vld-auth delete-user EMAIL` (the audit keeps the id alone).
- A password has at least 8 characters, an upper and a lower case letter, and at
  most 72 bytes (bcrypt). Hashes are bcrypt of cost 12, the scheme of
  doi-arxiv-app, so its hashes keep working after the move.

## Sessions

| Token | Lives | Where |
|---|---|---|
| access | 15 minutes | `validate_access` cookie or `Authorization: Bearer` |
| refresh | 30 days, never past the session ceiling | `validate_refresh` cookie or the body |
| session ceiling | 90 days from login | `session_exp` claim of the refresh token |
| device marker | a year | `validate_device` cookie |

- HS256 with `JWT_SECRET_KEY` (at least 32 bytes).
- A refresh revokes the presented token first (`SET NX` in Redis). A repeat within
  30 seconds gets the same pair (a retry); a repeat later is refused and logged as
  reuse.
- `tokens_invalidated_after` voids every token issued before it: logout
  everywhere, a password change or reset, a deactivation. A pair issued in the
  same second carries the mark as its `iat`, so it is not void at birth.
- The device marker lets its own account past the per-address login limit, so a
  stranger guessing the password cannot lock the owner out.

## Letters

Registration and a reset request write an event to `auth.outbox` in the same
transaction; `vld-worker` delivers it. The token of a letter is derived from the
outbox row, so a retried delivery sends the same link, and only its SHA-256 is
stored. Following a reset link also confirms the address. Without `EMAIL_HOST`
letters go to the worker log, and that sender refuses to start in production.

## Rate limits

| What | By address | By client address |
|---|---|---|
| login | 5 in 15 minutes | 30 in 15 minutes |
| registration | — | 10 an hour |
| another confirmation letter | 3 an hour | 5 an hour |
| reset letter | 3 an hour | 5 an hour |
| reset by link | — | 30 in 15 minutes |

Bucket keys carry a SHA-256 of the address, not the address.

## Audit

Logins, logouts, password changes and resets, admin actions and console actions
go to `audit.log` in the transaction of the action. The log is append-only: the
API role may only insert and read, and triggers refuse any update, delete or
truncate. A failed login stores the SHA-256 of the address, not the address.
