# Motion API Troubleshooting Guide

This guide covers common errors when MotionEye communicates with Motion.

---

## HTTP 403 Forbidden - CSRF Validation Failed

### Symptoms

- Error in logs: `CSRF token validation failed (HTTP 403)`
- Camera operations fail (pause/start detection, snapshot, config changes)

### Causes

1. Motion CSRF token has become stale
2. Motion was restarted
3. Communication issue between MotionEye and Motion

### Solutions

**Automatic Recovery**:
MotionEye automatically refreshes the CSRF token on 403 errors. The operation should succeed on retry.

**Manual Steps**:

1. Check Motion is running:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion logs for errors:
   ```bash
   sudo journalctl -u motion -n 100 --no-pager
   ```

3. Restart MotionEye to clear cache:
   ```bash
   sudo systemctl restart motioneye
   ```

4. If problem persists, verify Motion version:
   ```bash
   motion -h | grep Version
   ```
   Expected: 5.0.0 or higher

---

## HTTP 405 Method Not Allowed

### Symptoms

- Error in logs: `Motion rejected request: wrong HTTP method`
- API calls fail with HTTP 405

### Cause

Version mismatch between MotionEye and Motion.

### Solution

1. Verify Motion version is 5.0+:
   ```bash
   motion -h | grep Version
   ```

2. Verify MotionEye is up to date:
   ```bash
   pip3 show motioneye | grep Version
   ```

3. If Motion < 5.0, upgrade Motion
4. If issue persists, file a bug report

---

## CSRF Token Not Found

### Symptoms

- Error in logs: `CSRF token not found in Motion response`
- MotionEye cannot communicate with Motion

### Causes

1. Motion version too old (< 5.0)
2. Motion not running
3. Wrong port configured

### Solutions

1. Verify Motion is running:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion web interface accessible:
   ```bash
   curl http://127.0.0.1:7999/
   ```

3. Verify Motion control port in MotionEye settings (default: 7999)

4. Check Motion version:
   ```bash
   motion -h | grep Version
   ```
   Must be 5.0 or higher

---

## Connection Timeout

### Symptoms

- Error in logs: `Connection timeout`
- Operations take a long time then fail

### Causes

1. Motion is overloaded
2. Network issue on localhost
3. Motion crashed/hung

### Solutions

1. Check Motion status:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion CPU usage:
   ```bash
   top -p $(pgrep motion)
   ```

3. Restart Motion if hung:
   ```bash
   sudo systemctl restart motion
   ```

4. Check MotionEye timeout settings (default: 5 seconds)

---

## Performance Issues

### Symptoms

- Slow response from camera operations
- Delayed snapshot capture
- UI lag

### Solutions

1. Check CSRF token caching is working:
   - Look for `Using cached CSRF token` in DEBUG logs
   - Should NOT see token retrieval on every request

2. Enable DEBUG logging:
   ```bash
   # In motioneye.conf
   log_level debug
   ```

3. Monitor token retrieval frequency:
   ```bash
   sudo journalctl -u motioneye -f | grep "CSRF token"
   ```

Expected: Token retrieved once per Motion session, cached for subsequent requests

---

## Getting Help

If none of these solutions work:

1. Collect logs:
   ```bash
   sudo journalctl -u motioneye -n 200 > motioneye.log
   sudo journalctl -u motion -n 200 > motion.log
   ```

2. Check versions:
   ```bash
   motion -h | grep Version
   pip3 show motioneye | grep Version
   ```

3. File issue at: https://github.com/motioneye-project/motioneye/issues

Include:
- Log files
- Motion version
- MotionEye version
- Description of problem
- Steps to reproduce
