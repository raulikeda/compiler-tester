# IP Blocking & Security System

Automatic IP blocking system to protect your web server from reconnaissance, scanning attempts, and abuse.

## Features

- **Automatic Detection**: Detects suspicious request patterns (scanning for `.env`, `.git`, config files, RPC endpoints, etc.)
- **Rate Limiting**: Blocks IPs after too many failed requests in a short time window
- **Persistent Storage**: Blocked IPs are saved to disk and survive server restarts
- **Admin APIs**: REST endpoints to view and manage blocked IPs
- **Monitoring Dashboard**: CLI tool to monitor blocking activity
- **Configurable Thresholds**: Easy to adjust detection sensitivity

## How It Works

### Detection Methods

1. **Suspicious Pattern Detection**
   - Monitors requests to sensitive files (`.env`, `.git`, `.aws`, etc.)
   - Detects RPC/admin endpoint probing (`/mcp`, `/jsonrpc`, `/actuator`)
   - Identifies config file scanning attempts
   - Blocks IP after **5 suspicious requests** (configurable)

2. **Rate Limiting**
   - Tracks failed HTTP responses (400, 401, 403, 404, 405, 500, 502, 503)
   - Blocks IP after **20 failed requests** in 5 minutes (configurable)
   - Resets counter on successful responses

### Blocking Behavior

When an IP is blocked:
- All requests from that IP receive HTTP 403 (Forbidden)
- Block persists for **24 hours** (configurable in config.py)
- Blocks are stored in `security/blocked_ips.json`
- Statistics tracked in `security/ip_stats.json`
- Expired blocks are automatically cleaned up

## Usage

### 1. Automatic Mode (Default)

The middleware is automatically enabled when you start the server. No configuration needed!

```bash
# Start your server normally
python main.py
```

The system will:
- Monitor all incoming requests
- Detect suspicious patterns
- Block offending IPs automatically
- Log all actions to the application logs

### 2. Monitoring Activity

#### CLI Dashboard

```bash
# Summary view
python admin/security_monitor.py summary

# View currently blocked IPs
python admin/security_monitor.py blocked

# View IPs with suspicious activity (not yet blocked)
python admin/security_monitor.py suspicious

# View all information
python admin/security_monitor.py all

# Interactive mode
python admin/security_monitor.py
```

#### API Endpoints

Get blocked IPs:
```bash
curl -H "X-API-Secret: your-api-secret" \
  https://your-server.com/api/security/blocked-ips
```

Get statistics for a specific IP:
```bash
curl -H "X-API-Secret: your-api-secret" \
  https://your-server.com/api/security/ip-stats/192.168.1.100
```

Manually unblock an IP:
```bash
curl -X POST -H "X-API-Secret: your-api-secret" \
  https://your-server.com/api/security/unblock-ip/192.168.1.100
```

### 3. Configuration

Edit `security/config.py` to adjust detection behavior:

```python
# Number of suspicious requests before blocking
SUSPICIOUS_REQUESTS_THRESHOLD = 5

# Number of failed requests before blocking (in time window)
FAILED_REQUESTS_THRESHOLD = 20

# Time window for failed request counting (seconds)
TIME_WINDOW_SECONDS = 300  # 5 minutes

# How long to block an IP (hours)
BLOCK_DURATION_HOURS = 24

# Add trusted IPs that should never be blocked
WHITELIST_IPS = [
    "192.168.1.1",  # Your trusted monitoring service
]

# Add additional patterns to detect
SUSPICIOUS_PATTERNS = [
    "/.env",
    "/admin",
    # ... etc
]
```

## Log Files

Blocked IPs and statistics are stored in:

- **`security/blocked_ips.json`** - Currently blocked IPs with unblock times
- **`security/ip_stats.json`** - Statistics for all tracked IPs

Example `blocked_ips.json`:
```json
{
  "192.168.1.100": "2026-06-18T19:34:58.227000",
  "203.0.113.45": "2026-06-19T12:15:30.123000"
}
```

Example `ip_stats.json`:
```json
{
  "192.168.1.100": {
    "suspicious_count": 12,
    "failed_count": 25,
    "last_request": "2026-06-17T19:34:58.227000",
    "blocked": true
  }
}
```

## Examples from Your Logs

The system would automatically block these IPs based on their activity:

- **`3.39.243.117`**: 90+ requests scanning for `.env`, `.git`, config files, credentials → **BLOCKED**
- **`35.227.17.75`**: 20+ requests scanning for `.git`, `.env`, config files → **BLOCKED**
- **`199.45.155.88`**: 5+ requests probing `/mcp`, `/jsonrpc`, suspicious endpoints → **BLOCKED**
- **`66.132.172.137`**: Similar probing pattern → **BLOCKED**

## Manual Unblocking

### Via API

```bash
curl -X POST -H "X-API-Secret: your-secret" \
  https://server.com/api/security/unblock-ip/192.168.1.100
```

### Editing JSON

Edit `security/blocked_ips.json` and remove the IP entry, then restart the app.

## Advanced Configuration

### Whitelist Trusted IPs

If you have monitoring services or trusted clients that trigger false positives:

```python
# In security/config.py
WHITELIST_IPS = [
    "203.0.113.0/24",  # Your monitoring service
    "192.168.1.50",    # Internal trusted IP
]
```

### Custom Patterns

Add specific patterns for your application:

```python
# In security/config.py
SUSPICIOUS_PATTERNS = [
    # ... existing patterns ...
    "/admin-panel",      # Your custom endpoints
    "/internal-api",
]
```

### Adjust Sensitivity

For stricter security:
```python
SUSPICIOUS_REQUESTS_THRESHOLD = 2  # Block faster
FAILED_REQUESTS_THRESHOLD = 10     # Lower threshold
```

For more lenient (if you have false positives):
```python
SUSPICIOUS_REQUESTS_THRESHOLD = 10
FAILED_REQUESTS_THRESHOLD = 50
```

## Monitoring & Alerts

### View Live Logs

```bash
# Watch application logs
tail -f log/uvicorn-*.log | grep -E "BLOCKED|Suspicious"

# Check security statistics
python admin/security_monitor.py summary
```

### Integration with Your Monitoring

You can periodically check the API to integrate with your monitoring system:

```bash
#!/bin/bash
# Check number of blocked IPs
BLOCKED_COUNT=$(curl -s -H "X-API-Secret: $API_SECRET" \
  https://server.com/api/security/blocked-ips | jq '.count')

if [ $BLOCKED_COUNT -gt 10 ]; then
  echo "Alert: $BLOCKED_COUNT IPs are blocked"
  # Send alert to your monitoring system
fi
```

## Troubleshooting

### False Positives

If legitimate requests are being blocked:

1. **Identify the IP**: Check `security/ip_stats.json` for the blocked IP
2. **Review patterns**: See what requests triggered the block
3. **Whitelist or adjust**: 
   - Add to `WHITELIST_IPS` in `config.py`, or
   - Increase thresholds in `config.py`
4. **Unblock manually**: Use the API or CLI to unblock

### Checking What Blocked an IP

```bash
# View specific IP stats
python admin/security_monitor.py
# Select option 3 to see details
```

## Performance Impact

- **Minimal overhead**: Middleware uses in-memory tracking with async operations
- **Efficient storage**: Blocked IPs stored as JSON (small file size)
- **No external dependencies**: No additional services needed

## Security Notes

1. **Keep API Secret safe** - Change `API_SECRET` in `.env`
2. **Monitor `blocked_ips.json`** - Indicates attack patterns against your server
3. **Review logs regularly** - Helps identify attack sources and patterns
4. **Adjust sensitivity** - Balance security with false positive rate

## Support & Issues

For issues or questions:
1. Check logs in `log/` directory
2. Review statistics in `security/ip_stats.json`
3. Run the monitoring dashboard: `python admin/security_monitor.py`
