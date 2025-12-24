# Deploy and Test Authentication Overhaul - Pi 4 then Pi 5

**Created**: 2025-12-24 20:45
**Priority**: P1 - Critical Security
**Target**: Pi 4 (192.168.1.246) first, then Pi 5 (192.168.1.176)

---

## Objective

Deploy the completed authentication overhaul (session cookies + bcrypt passwords) to Pi 4, verify functionality, then deploy to Pi 5.

---

## Prerequisites

**Verified Status**:
- ✅ Bcrypt 4.2.0 installed on both Pis
- ✅ Code complete on local development machine
- ❌ Code NOT yet deployed to either Pi

---

## Deployment Steps - Pi 4

### 1. Sync Code to Pi 4
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
    /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.246:~/motioneye/
```

### 2. Install on Pi 4
```bash
ssh admin@192.168.1.246 "cd ~/motioneye && sudo pip3 install . --break-system-packages"
```

### 3. Restart MotionEye Service
```bash
ssh admin@192.168.1.246 "sudo systemctl restart motioneye"
```

### 4. Check Service Status
```bash
ssh admin@192.168.1.246 "sudo systemctl status motioneye --no-pager"
```

### 5. Review Logs
```bash
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 50 --no-pager"
```

---

## Testing Sequence - Pi 4

### Test 1: Session Cookie Login
1. Open browser: `http://192.168.1.246:8765/`
2. Clear browser cookies for this site
3. Login with existing credentials
4. **Check**: Browser DevTools → Application → Cookies
   - Cookie name: `meye_session`
   - Attributes: `HttpOnly`, `SameSite=Lax`
   - Value: 64-character hex token

### Test 2: Password Auto-Upgrade (SHA1 → Bcrypt)

**Check logs for upgrade message:**
```bash
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 100 --no-pager | grep -i bcrypt"
```
Expected: `@admin_password upgraded to bcrypt` or `@normal_password upgraded to bcrypt`

**Verify config file format:**
```bash
ssh admin@192.168.1.246 "sudo grep -E '@admin_password|@normal_password' /etc/motioneye/motioneye.conf"
```
Expected: `$2b$12$...` (bcrypt format, NOT 40-char SHA1 hex)

### Test 3: Session Persistence
1. Navigate to Settings panel (requires auth)
2. Refresh page → should stay authenticated
3. Close browser, reopen, navigate to site → should stay authenticated (within 24h)

### Test 4: Logout
1. Click logout button
2. **Check**: `meye_session` cookie is cleared
3. Try to access Settings → should redirect/prompt for login

### Test 5: Password Change
1. Login as admin
2. Settings → change admin password to new value
3. **Check config file** - new password should be bcrypt format:
   ```bash
   ssh admin@192.168.1.246 "sudo grep '@admin_password' /etc/motioneye/motioneye.conf"
   ```
4. Logout and login with new password → should work

### Test 6: HTTP Basic Auth (API Clients)
```bash
# Test with bcrypt password (after upgrade)
curl -u admin:PASSWORD http://192.168.1.246:8765/config/main/list
```
Expected: Returns config JSON (not 401 Unauthorized)

### Test 7: Legacy Compatibility (Optional)
If you have remote cameras using URL signatures, verify they still connect.

---

## Success Criteria - Pi 4

- [ ] Service starts without errors
- [ ] Login creates `meye_session` cookie with correct attributes
- [ ] SHA1 password auto-upgrades to bcrypt on first login
- [ ] Config file shows bcrypt hash (`$2b$12$...`)
- [ ] Authenticated requests succeed
- [ ] Session persists across page refreshes
- [ ] Logout clears session cookie
- [ ] Password changes stored as bcrypt
- [ ] HTTP Basic Auth works with bcrypt passwords

---

## Rollback Plan - Pi 4

If critical issues occur:

1. **Check logs** for specific errors:
   ```bash
   ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 200 --no-pager"
   ```

2. **Session issues**: Session code is additive - can clear cookies to force legacy auth

3. **Password issues**: Bcrypt verification supports SHA1/plaintext fallback - existing passwords still work

4. **Complete rollback** (if necessary):
   ```bash
   # Revert to previous version from git
   git checkout HEAD~1
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
       /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.246:~/motioneye/
   ssh admin@192.168.1.246 "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"
   ```

---

## Deployment Steps - Pi 5

**Only proceed after Pi 4 testing succeeds!**

### 1. Sync Code to Pi 5
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
    /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/
```

### 2. Install on Pi 5
```bash
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"
```

### 3. Restart MotionEye Service
```bash
ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
```

### 4. Check Service Status
```bash
ssh admin@192.168.1.176 "sudo systemctl status motioneye --no-pager"
```

### 5. Review Logs
```bash
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"
```

---

## Testing Sequence - Pi 5

Run the same test sequence as Pi 4:
1. Session Cookie Login - `http://192.168.1.176:8765/`
2. Password Auto-Upgrade
3. Session Persistence
4. Logout
5. Password Change
6. HTTP Basic Auth

---

## Success Criteria - Pi 5

Same as Pi 4 - all tests must pass.

---

## Critical Files Deployed

### New Files
- `motioneye/session.py` - Session management
- `motioneye/passwords.py` - Bcrypt utilities

### Modified Files
- `pyproject.toml` - Bcrypt dependency
- `motioneye/handlers/login.py` - Login with auto-upgrade
- `motioneye/handlers/base.py` - Auth flow + logout + bcrypt HTTP Basic Auth
- `motioneye/config/camera/converters.py` - Password storage with bcrypt
- `motioneye/static/js/main.js` - Session login/logout functions

---

## Monitoring Commands

```bash
# Watch logs in real-time
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -f"

# Check for errors
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 100 --no-pager | grep -i error"

# Check for authentication events
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 100 --no-pager | grep -E 'login|logout|Session|bcrypt|upgrade'"

# Check service status
ssh admin@192.168.1.246 "sudo systemctl is-active motioneye"
```

---

## Related Documents

- Summary: `docs/summaries/auth-overhaul-completion-20251224-2030.md`
- Handoff: `docs/handoff-prompts/HANDOFF-auth-overhaul-20251224-2010.md`
- Plans: `docs/plans/session-cookie-auth-migration-20251224-1930.md`
- Plans: `docs/plans/bcrypt-password-migration-20251224-2000.md`
