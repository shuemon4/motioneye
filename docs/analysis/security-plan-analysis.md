Here’s what I think is missing / risky / likely to bite you later in the plan, based on your plan + scratchpad, plus some realistic Raspberry Pi platform constraints.

Key gaps & shortcomings in the plan
1) You didn’t plan to fix the request-signature SHA1

Your scratchpad flags SHA1 being used for request signatures as a weakness, but the plan doesn’t include a remediation. This matters because signature auth is one of motionEye’s core controls (and you’re leaning on it for CSRF-ish protection).

Add: migrate signatures to HMAC-SHA256 (or SHA-512) with:
- versioned signature format (like you’re doing for passwords)
- constant-time compare
- explicit timestamp + max clock skew + replay protection

2) Command injection fix: don’t “double-fix” with shlex.quote() when you stop using shell=True

Your Phase 1.1 fix correctly moves away from shell=True by switching to argv lists, but it also says “Apply shlex.quote() to all user-supplied paths”.

If you pass a list of args to subprocess.Popen(..., shell=False), quoting is not only unnecessary, it can break paths (you end up passing literal quotes to ffmpeg). The “quote everything” guidance is for shell strings, not argv lists.

Add: a small helper like ensure_safe_path() + “argv only” policy. No shell strings anywhere.

3) Rate limiting design is vulnerable to memory growth + proxy/NAT weirdness
Your token bucket prototype stores attempts in an unbounded dict keyed by identifier. That can be abused (send lots of requests with changing identifiers → memory growth).

Also, if users run motionEye behind a reverse proxy (common once you add TLS), remote_ip may become the proxy’s IP unless you explicitly handle forwarded headers.

Add:
- bounded LRU/TTL cache for attempts (cap keys, expire aggressively)
- rate limit by (IP + username) not just IP
- correct client IP handling behind proxy (or explicitly document “rate limiting only correct without proxy unless configured”)

4) Path traversal hardening: startswith() checks are subtly unsafe

Your safe_path_join() uses startswith(base_dir) checks. This can be bypassed by prefix tricks (e.g., /base vs /base_evil) unless you do it carefully.

Add: use os.path.commonpath([base_dir, real_path]) == base_dir rather than startswith(), and normalize path separators consistently.

5) “Add HTTPS support” is good, but the plan ignores the secure deployment default

The scratchpad notes motionEye binds on 0.0.0.0:8765 by default. Adding TLS in-app helps, but the plan should also change defaults and document a recommended topology.

Add:
- new setting: bind to 127.0.0.1 by default (or “first-run wizard” forces a choice)
- recommended: reverse proxy (Caddy/Nginx) for TLS + motionEye on localhost
- explicit warning if running HTTP on LAN/Wi-Fi (“passwords in plaintext”) 

6) The plan doesn’t address “passwords in remote URLs” (called out in scratchpad)

Your scratchpad flags that remote camera communication includes credentials in URLs. That’s a big real-world leak vector (logs, browser history, referrers, proxies).

Add: migrate remote auth to headers (Authorization) or request body, and scrub sensitive data from logs.

7) Webhook security is absent

Your scratchpad lists motioneye/webhook.py as in-scope, but the plan doesn’t mention it. Webhooks often become the “one URL that does privileged things.”

Add: webhook authentication (HMAC signature with rotating secret), allowlist of destinations, and strict timeouts.

8) “Encrypt stored credentials” may not buy much without key management

Encrypting secrets in config using Fernet helps only if:
- the key is protected better than the encrypted file
- file permissions are locked down
- backups don’t scoop up the key alongside the ciphertext

Add: treat this as optional hardening, and prioritize:

file permissions + ownership + “secrets in env vars” first (you already do this for OAuth) clear documentation about threat model (“protects against accidental disclosure / non-root reads”, not full device compromise)

9) Dependency/version requirements section is outdated and could mislead

Your plan says “OpenSSL 1.1.1+”, but OpenSSL 1.1.1 reached EOL in 2023 OpenSSL Corporation. On modern Raspberry Pi OS releases, you’re likely to be on OpenSSL 3.x anyway.

Add: update requirement language to something like:

“OpenSSL 3.x preferred; must support TLS 1.2+ (TLS 1.3 recommended)”
pin + audit python deps (pip-audit) as part of “security work,” not just code changes
Raspberry Pi version limitations that affect your security plan
OS / architecture reality

Raspberry Pi OS 32-bit is the “all models” option 
Raspberry Pi, because not all Raspberry Pi hardware can run 64-bit userlands.

That matters because some security-oriented Python wheels (notably cryptography) can be painful on older ARM / 32-bit systems—build times, missing wheels, and performance overhead.

Practical plan change: explicitly document “supported platforms” and consider making cryptography an optional extra (or gate it behind “if available”).

Pi 4 has a documented boot security chain of trust, but it’s not a typical “bring your own signing key” secure boot flow (the ROM verifies Raspberry Pi Ltd-signed code; customer countersigning isn’t supported on BCM2711).

Pi 5 secure boot discussions emphasize it’s intended for buildroot-like images, and “using it with Raspberry Pi OS is not recommended/supported”.

Practical plan change: don’t treat secure boot as a general mitigation you can assume users will adopt. Keep it as “advanced hardening” guidance.

CPU crypto acceleration varies / may be quirky

There are community reports around ARM crypto extension behavior on Pi 4/5. Whether or not that’s perfectly representative, the takeaway is:

Don’t bake your security posture into “we’ll rely on fast crypto.”
Design so TLS + PBKDF2/Argon2 settings are configurable and can scale down for weaker boards.

The “missing items” I’d add to your roadmap (high impact, low drama)
- Signature auth migration SHA1 → HMAC-SHA256 (with versioning) 
- Fix remote camera credential-in-URL issue 
- Bounded rate limiter + proxy-aware client IP 
- Safer path checks (commonpath) and symlink policy 
- Secure-by-default bind / deployment guidance (0.0.0.0 is a footgun) 
- Update dependency requirements: OpenSSL wording (1.1.1 is EOL) 

**References**
- docs/plans/security-optimization-plan-20251218-1030.md
- docs/plans/security-analysis-20251218-1000
 
OpenSSL Corporation

If you want, I can turn this into a patch-level checklist (what files/functions to touch and what tests to add) that matches your Phase 1/2/3 structure, but with the missing items slotted into the right phases.