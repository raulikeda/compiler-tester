# Automatic IP Blocking System - Implementation Summary

## Overview

Your server now has **automatic IP blocking** to protect against reconnaissance, scanning attempts, and other abuse. The system detected and would have blocked the attack patterns in your logs.

## What Was Implemented

### 1. Core IP Blocking Module (`security/ip_blocker.py`)

**IPBlocker Class** - Manages IP blocking logic:
- Tracks suspicious request patterns (scanning for `.env`, `.git`, config files, RPC endpoints)
- Counts failed HTTP requests (400, 401, 403, 404, 405, 500, 502, 503)
- Automatically blocks IPs after thresholds are exceeded
- Persists blocked IPs to `security/blocked_ips.json` (survives restarts)
- Stores detailed statistics in `security/ip_stats.json`
- Automatically expires blocks after 24 hours (configurable)

### 2. FastAPI Middleware (`security/middleware.py`)

**IPBlockingMiddleware** - Integrates blocking into request/response cycle:
- Blocks requests from already-blocked IPs before reaching endpoints
- Tracks all requests and their responses
- Triggers blocking on pattern detection
- Returns HTTP 403 (Forbidden) to blocked IPs

### 3. Configuration Module (`security/config.py`)

Centralized settings for easy customization:
- `SUSPICIOUS_REQUESTS_THRESHOLD` - Block after N suspicious requests (default: 5)
- `FAILED_REQUESTS_THRESHOLD` - Block after N failed requests in time window (default: 20)
- `TIME_WINDOW_SECONDS` - Rate limiting window (default: 300s / 5 minutes)
- `BLOCK_DURATION_HOURS` - How long to block IPs (default: 24 hours)
- `SUSPICIOUS_PATTERNS` - List of patterns indicating attacks
- `WHITELIST_IPS` - Trusted IPs that should never be blocked

### 4. Admin CLI Dashboard (`admin/security_monitor.py`)

Interactive monitoring tool:
- View summary statistics (total blocked IPs, total attack attempts)
- Display currently blocked IPs with unblock times
- Show IPs with suspicious activity not yet blocked
- Clear statistics
- Commands: `summary`, `blocked`, `suspicious`, `clear-stats`, `all`

### 5. Testing Tool (`admin/test_blocking.py`)

Verify the blocking system works:
- Simulate suspicious path scanning
- Simulate RPC endpoint probing
- Simulate excessive failed requests
- Run with: `python test_blocking.py https://your-server.com --no-verify-ssl`

## Integration Points

### Main Application (`main.py`)

Added:
```python
from security.middleware import IPBlockingMiddleware
from security.ip_blocker import ip_blocker

# Middleware added to FastAPI app
app.add_middleware(IPBlockingMiddleware)
```

### New Admin API Endpoints

```
GET  /api/security/blocked-ips                 # List blocked IPs
GET  /api/security/ip-stats/{ip}              # Stats for specific IP
POST /api/security/unblock-ip/{ip}            # Manually unblock IP
```

All endpoints require `X-API-Secret` header authentication.

## Detection Rules

### Suspicious Pattern Detection (Threshold: 5 attempts)

Automatically blocks IPs attempting to access:
- Configuration files: `.env`, `.git`, `.aws`, `.ssh`, `config.php`, `web.config`
- Credentials: `.git-credentials`, `.htpasswd`, AWS config
- Database files: `backup.sql`, `dump.sql`, `database.yml`
- RPC endpoints: `/mcp`, `/jsonrpc`, `/actuator`
- System info: `/proc/self`, terraform files, Kubernetes config

### Rate Limiting (Threshold: 20 failures in 5 minutes)

Blocks IPs making too many failed requests:
- 404 (Not Found)
- 403 (Forbidden)
- 401 (Unauthorized)
- 400 (Bad Request)
- 405 (Method Not Allowed)
- 5xx errors (Server errors)

## Data Files

### `security/blocked_ips.json`
Persistent storage of blocked IPs and unblock times:
```json
{
  "203.0.113.45": "2026-06-18T19:34:58.227000",
  "198.51.100.89": "2026-06-19T12:15:30.123000"
}
```

### `security/ip_stats.json`
Statistics for all tracked IPs:
```json
{
  "203.0.113.45": {
    "suspicious_count": 12,
    "failed_count": 25,
    "last_request": "2026-06-17T19:34:58.227000",
    "blocked": true
  }
}
```

## Attack Patterns from Your Logs (Would Be Blocked)

### IP: 3.39.243.117
- **Type**: Comprehensive vulnerability scanner
- **Attempts**: 90+ requests
- **Pattern**: Scanning for `.env`, `.git`, config files, AWS credentials, SSH keys
- **Detection**: Suspicious pattern threshold (5 attempts) → **BLOCKED after ~5-10 requests**

### IP: 35.227.17.75
- **Type**: Git exposure scanner
- **Attempts**: 20+ requests
- **Pattern**: Scanning for `.git`, `.env`, config files
- **Detection**: Either suspicious pattern OR failed request rate → **BLOCKED after ~20 requests**

### IP: 199.45.155.88
- **Type**: RPC endpoint prober
- **Attempts**: 5 requests probing `/mcp`, `/jsonrpc`, POST requests
- **Detection**: Suspicious pattern (RPC endpoints) → **BLOCKED after 5 requests**

### IP: 66.132.172.137
- **Type**: Reconnaissance scanner (similar to 199.45.155.88)
- **Detection**: Same pattern → **BLOCKED after 5 suspicious requests**

## How to Use

### Start Server

```bash
python main.py
```

Blocking system is **automatically enabled**.

### Monitor Activity

```bash
# Option 1: CLI Dashboard
python admin/security_monitor.py summary
python admin/security_monitor.py blocked

# Option 2: Watch logs
tail -f log/uvicorn-*.log | grep -i blocked

# Option 3: API
curl -H "X-API-Secret: your-secret" https://server.com/api/security/blocked-ips
```

### Customize Settings

Edit `security/config.py`:

```python
# For stricter blocking (recommended for public servers)
SUSPICIOUS_REQUESTS_THRESHOLD = 2
FAILED_REQUESTS_THRESHOLD = 10

# For more lenient blocking (if you get false positives)
SUSPICIOUS_REQUESTS_THRESHOLD = 10
FAILED_REQUESTS_THRESHOLD = 50

# Change block duration
BLOCK_DURATION_HOURS = 48  # Block for 48 hours instead of 24

# Whitelist trusted services
WHITELIST_IPS = [
    "203.0.113.1",  # Your monitoring service
    "198.51.100.1", # Your CI/CD pipeline
]
```

### Unblock an IP

```bash
# Via API
curl -X POST -H "X-API-Secret: your-secret" \
  https://server.com/api/security/unblock-ip/203.0.113.45

# Or edit blocked_ips.json and restart
```

### Test the System

```bash
python admin/test_blocking.py https://your-server.com --no-verify-ssl
```

## Performance Impact

- **Minimal**: Middleware uses in-memory tracking with async operations
- **Efficient**: Blocked IPs stored as small JSON files (~1-2KB per IP)
- **No external dependencies**: No additional services or databases required

## Security Best Practices

1. **Change API Secret**: Update `API_SECRET` in `.env`
2. **Monitor regularly**: Check `python admin/security_monitor.py summary` weekly
3. **Review statistics**: Look for attack patterns in `security/ip_stats.json`
4. **Adjust sensitivity**: Tune thresholds in `security/config.py` based on your traffic
5. **Keep logs**: Retain `log/` directory for forensics
6. **Secure `/security/`**: Limit access to `blocked_ips.json` and `ip_stats.json`

## Troubleshooting

### Legitimate IPs Getting Blocked

1. Check which IP is blocked: `python admin/security_monitor.py blocked`
2. View what triggered it: Check `security/ip_stats.json`
3. Either:
   - Increase thresholds in `security/config.py`
   - Add IP to `WHITELIST_IPS`
   - Manually unblock: `curl -X POST -H "X-API-Secret: ..." https://server.com/api/security/unblock-ip/IP`

### System Not Blocking

1. Verify middleware is in `main.py`: `grep IPBlockingMiddleware main.py`
2. Check config in `security/config.py`
3. View logs: `tail -f log/uvicorn-*.log | grep -i "blocked\|suspicious"`
4. Run test: `python admin/test_blocking.py https://server.com --no-verify-ssl`

### High False Positive Rate

1. Identify the legitimate IP from `security/ip_stats.json`
2. Increase thresholds in `security/config.py`
3. Add to whitelist if it's a trusted service
4. Remove problematic patterns from `SUSPICIOUS_PATTERNS` if needed

## Next Steps

1. **Start your server**: `python main.py`
2. **Monitor for a day**: `python admin/security_monitor.py summary` (run periodically)
3. **Adjust thresholds**: Based on your legitimate traffic patterns
4. **Test the system**: `python admin/test_blocking.py https://your-server.com --no-verify-ssl`
5. **Document changes**: Keep notes on any custom configuration

## Documentation Files

- `security/README.md` - Complete detailed documentation
- `security/QUICK_START.md` - Quick reference guide
- `security/config.py` - Configuration with comments
- Admin scripts:
  - `admin/security_monitor.py` - Monitoring dashboard
  - `admin/test_blocking.py` - Testing tool

---

**That's it!** Your server is now protected against automated attacks. 🛡️
