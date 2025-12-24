The best fix is to stop depending on cross-language URL canonicalization for login security.

Here are better approaches, in order of “most robust / least brittle”:

Option A (best for MotionEye web UI): Server-side session cookie auth

Instead of signing each request in JS, do a normal login:

Browser POSTs username/password over HTTPS.

Python verifies password hash (bcrypt/argon2).

Python sets a session cookie:

HttpOnly (JS can’t read it)

Secure (HTTPS only)

SameSite=Lax or Strict

All subsequent requests are authenticated by the cookie.

This completely eliminates the “signing the path” problem and is the standard approach for browser-based UIs.

Add-ons you should include:

CSRF protection for state-changing endpoints (or SameSite+CSRF token).

Rate limiting / backoff on login attempts.

Short session lifetime + rotation on privilege changes.