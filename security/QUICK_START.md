# IP Blocking System - Quick Start Guide

## What Was Installed

Your web server now has **automatic IP blocking** to protect against the attacks seen in your logs. Three suspicious IPs from your logs would have been automatically blocked:

- `3.39.243.117` - 90+ requests scanning for `.env`, `.git`, configs
- `35.227.17.75` - 20+ requests scanning for `.git`, `.env`, configs  
- `199.45.155.88` - 5+ requests probing `/mcp`, `/jsonrpc`

## Quick Start

### 1. Start Your Server

```bash
python main.py
```

The IP blocking system is **already enabled** - no configuration needed!

### 2. Monitor Activity (Pick One)

**Option A: CLI Dashboard**
```bash
# View summary
python admin/security_monitor.py summary

# View blocked IPs
python admin/security_monitor.py blocked

# Interactive mode
python admin/security_monitor.py
```

**Option B: Check Logs**
```bash
tail -f log/uvicorn-*.log | grep -i "blocked"
```

**Option C: API Endpoint**
```bash
curl -H "X-API-Secret: YOUR_API_SECRET" \
  https://your-server.com/api/security/blocked-ips
```

### 3. Unblock an IP (if needed)

```bash
# Via API
curl -X POST -H "X-API-Secret: YOUR_API_SECRET" \
  https://your-server.com/api/security/unblock-ip/BLOCKED_IP

# Or manually edit security/blocked_ips.json
```

## How It Works

The system automatically blocks IPs that:

1. **Scan for sensitive files** (`.env`, `.git`, `.aws`, config files) - blocks after 5 attempts
2. **Make too many failed requests** (404, 403, 500, etc.) - blocks after 20 in 5 minutes
3. **Probe for RPC endpoints** (`/mcp`, `/jsonrpc`, `/actuator`) - blocks after 5 attempts

Blocks last **24 hours** by default.

## Customize (Optional)

Edit `security/config.py` to adjust:

```python
# Block faster (stricter)
SUSPICIOUS_REQUESTS_THRESHOLD = 2
FAILED_REQUESTS_THRESHOLD = 10

# Block slower (more lenient)
SUSPICIOUS_REQUESTS_THRESHOLD = 10
FAILED_REQUESTS_THRESHOLD = 50

# Change block duration (hours)
BLOCK_DURATION_HOURS = 48

# Whitelist trusted IPs
WHITELIST_IPS = [
    "192.168.1.1",  # Your monitoring service
]

# Add custom suspicious patterns
SUSPICIOUS_PATTERNS = [
    "/.env",
    "/admin",
]
```

## Files Created

```
security/
├── __init__.py                 # Module init
├── config.py                   # Configuration (EDIT THIS)
├── ip_blocker.py              # Core blocking logic
├── middleware.py              # FastAPI middleware
├── README.md                  # Full documentation
├── blocked_ips.json           # Currently blocked IPs (auto-created)
└── ip_stats.json              # IP statistics (auto-created)

admin/
└── security_monitor.py        # Monitoring dashboard
```

## Common Tasks

**View all blocked IPs:**
```bash
python admin/security_monitor.py blocked
```

**Clear statistics:**
```bash
python admin/security_monitor.py clear-stats
```

**Check stats for specific IP:**
```bash
curl -H "X-API-Secret: $API_SECRET" \
  https://server.com/api/security/ip-stats/192.168.1.100
```

## Testing

To test the blocking system (simulate attack):

```bash
# From another machine
for i in {1..10}; do 
  curl -s https://your-server.com/.env
  curl -s https://your-server.com/.git
done

# Check if IP got blocked
python admin/security_monitor.py blocked
```

## Support

For detailed documentation:
```bash
cat security/README.md
```

For issues:
1. Check logs: `tail -f log/uvicorn-*.log`
2. Check stats: `python admin/security_monitor.py`
3. Review `security/ip_stats.json` for details

## Security Notes

⚠️ **IMPORTANT:**

1. Change your `API_SECRET` in `.env` file
2. Regularly monitor blocked IPs to detect attack patterns
3. Review `/security/ip_stats.json` for threats
4. Adjust thresholds if you get false positives
5. Keep the `security/` directory secure

That's it! Your server is now protected. 🛡️
