"""
IP Blocking Configuration
Adjust these settings to control threat detection and response behavior
"""

# File paths for persistent storage
BLOCKED_IPS_FILE = "security/blocked_ips.json"
IP_STATS_FILE = "security/ip_stats.json"

# Thresholds for suspicious pattern detection
SUSPICIOUS_REQUESTS_THRESHOLD = 1  # Block after N suspicious requests
FAILED_REQUESTS_THRESHOLD = 5      # Block after N failed requests in short period
TIME_WINDOW_SECONDS = 300          # Time window for rate limiting (5 minutes)
BLOCK_DURATION_HOURS = 24*365      # How long to block an IP (hours)

# Suspicious request patterns to detect
SUSPICIOUS_PATTERNS = [
    # Sensitive configuration files
    "/.env", "/.venv.", "/.env.", "/.git", "/.aws", "/.ssh", "/.npmrc", "/.netrc",
    "/wp-config", "/config.php", "/web.config", "/appsettings.json",
    "/database.yml", "/database.php", "application.properties", "application.yml",
    "/terraform.tfstate", "/backup.sql", "/dump.sql", "/.kube/config",
    
    # RPC/Admin endpoints
    "/mcp", "/jsonrpc", "/actuator", "/___proxy", "/ecp/",
    
    # PHP/Webserver info disclosure
    "/phpinfo.php", "/info.php", "/index.php.bak",
    
    # Credentials and secrets
    "/credentials", "/.git-credentials", "/.htpasswd", "/proc/self",
    
    # Git exposure
    "/.git/", "/config.php"
]

# HTTP status codes indicating failed/error responses
FAILED_STATUS_CODES = {400, 401, 403, 404, 405, 500, 502, 503}

# Whitelist IPs that should never be blocked (optional, for trusted services)
WHITELIST_IPS = [    
    # Example: "192.168.1.1",
    "186.232.61.6" # Insper
]

# Logging configuration
LOG_BLOCKED_IP_ATTEMPTS = True  # Log each attempt to block an IP
LOG_UNBLOCK_EVENTS = True        # Log when IPs are unblocked (expired)

print("IP Blocker configuration loaded successfully")
