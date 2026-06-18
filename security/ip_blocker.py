"""
IP blocking and rate limiting middleware for security
Detects and blocks suspicious request patterns and rate limiting violations
"""

import json
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Set, Dict, Tuple
import asyncio
from security.config import (
    BLOCKED_IPS_FILE,
    IP_STATS_FILE,
    SUSPICIOUS_PATTERNS,
    SUSPICIOUS_REQUESTS_THRESHOLD,
    FAILED_REQUESTS_THRESHOLD,
    TIME_WINDOW_SECONDS,
    BLOCK_DURATION_HOURS,
    WHITELIST_IPS,
    FAILED_STATUS_CODES,
    LOG_BLOCKED_IP_ATTEMPTS,
    LOG_UNBLOCK_EVENTS
)

logger = logging.getLogger(__name__)


class IPBlocker:
    """Manages IP blocking and tracking suspicious request patterns"""
    
    def __init__(self):
        self.blocked_ips: Dict[str, datetime] = {}  # IP -> unblock_time
        self.ip_stats: Dict[str, Dict] = defaultdict(lambda: {
            "suspicious_count": 0,
            "failed_count": 0,
            "last_request": None,
            "blocked": False
        })
        self._lock = asyncio.Lock()
        self._load_blocked_ips()
        self._cleanup_expired_blocks()
    
    def _ensure_security_dir(self):
        """Ensure security directory exists"""
        os.makedirs("security", exist_ok=True)
    
    def _load_blocked_ips(self):
        """Load blocked IPs from persistent storage"""
        self._ensure_security_dir()
        try:
            if os.path.exists(BLOCKED_IPS_FILE):
                with open(BLOCKED_IPS_FILE, 'r') as f:
                    data = json.load(f)
                    for ip, unblock_str in data.items():
                        try:
                            self.blocked_ips[ip] = datetime.fromisoformat(unblock_str)
                        except (ValueError, TypeError):
                            pass
                logger.info(f"Loaded {len(self.blocked_ips)} blocked IPs")
        except Exception as e:
            logger.error(f"Error loading blocked IPs: {e}")
    
    def _save_blocked_ips(self):
        """Persist blocked IPs to storage"""
        self._ensure_security_dir()
        try:
            data = {ip: unblock_time.isoformat() for ip, unblock_time in self.blocked_ips.items()}
            with open(BLOCKED_IPS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving blocked IPs: {e}")
    
    def _save_stats(self):
        """Persist IP statistics"""
        self._ensure_security_dir()
        try:
            # Convert for JSON serialization
            data = {}
            for ip, stats in self.ip_stats.items():
                data[ip] = {
                    "suspicious_count": stats["suspicious_count"],
                    "failed_count": stats["failed_count"],
                    "last_request": stats["last_request"].isoformat() if stats["last_request"] else None,
                    "blocked": stats["blocked"]
                }
            with open(IP_STATS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving IP stats: {e}")
    
    def _cleanup_expired_blocks(self):
        """Remove expired blocks"""
        now = datetime.now()
        expired = [ip for ip, unblock_time in self.blocked_ips.items() if unblock_time < now]
        for ip in expired:
            del self.blocked_ips[ip]
            if ip in self.ip_stats:
                self.ip_stats[ip]["blocked"] = False
            if LOG_UNBLOCK_EVENTS:
                logger.info(f"Unblocked IP: {ip}")
        if expired:
            self._save_blocked_ips()
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked"""
        # Check whitelist first
        if ip in WHITELIST_IPS:
            return False
        
        self._cleanup_expired_blocks()
        return ip in self.blocked_ips
    
    def is_request_suspicious(self, path: str) -> bool:
        """Check if request path matches suspicious patterns"""
        path_lower = path.lower()
        return any(pattern.lower() in path_lower for pattern in SUSPICIOUS_PATTERNS)
    
    async def track_request(self, ip: str, path: str, status_code: int) -> Tuple[bool, str]:
        """
        Track request and determine if IP should be blocked.
        Returns (should_block, reason)
        """
        async with self._lock:
            # Check if already blocked
            if self.is_ip_blocked(ip):
                return True, "IP is blocked"
            
            stats = self.ip_stats[ip]
            stats["last_request"] = datetime.now()
            
            # Track suspicious patterns
            if self.is_request_suspicious(path):
                stats["suspicious_count"] += 1
                logger.warning(f"Suspicious request from {ip}: {path} (count: {stats['suspicious_count']})")
                
                if stats["suspicious_count"] >= SUSPICIOUS_REQUESTS_THRESHOLD:
                    self._block_ip(ip, f"Suspicious scanning pattern detected ({stats['suspicious_count']} attempts)")
                    return True, f"Blocked: Suspicious activity detected"
            
            # Track failed requests
            if status_code in FAILED_STATUS_CODES:
                stats["failed_count"] += 1
                
                # Reset counter if outside time window
                if (stats["last_request"] - datetime.now()).total_seconds() > TIME_WINDOW_SECONDS:
                    stats["failed_count"] = 1
                
                logger.warning(f"Failed request from {ip}: {path} -> {status_code} (count: {stats['failed_count']})")
                
                if stats["failed_count"] >= FAILED_REQUESTS_THRESHOLD:
                    self._block_ip(ip, f"Too many failed requests ({stats['failed_count']} in {TIME_WINDOW_SECONDS}s)")
                    return True, f"Blocked: Rate limit exceeded"
            else:
                # Reset failed count on successful request
                stats["failed_count"] = 0
            
            self._save_stats()
            return False, ""
    
    def _block_ip(self, ip: str, reason: str):
        """Block an IP address"""
        unblock_time = datetime.now() + timedelta(hours=BLOCK_DURATION_HOURS)
        self.blocked_ips[ip] = unblock_time
        self.ip_stats[ip]["blocked"] = True
        
        if LOG_BLOCKED_IP_ATTEMPTS:
            logger.warning(f"BLOCKED IP: {ip} - Reason: {reason} - Duration: {BLOCK_DURATION_HOURS}h")
        self._save_blocked_ips()
    
    def unblock_ip(self, ip: str):
        """Manually unblock an IP"""
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            self.ip_stats[ip]["blocked"] = False
            self._save_blocked_ips()
            if LOG_UNBLOCK_EVENTS:
                logger.info(f"Manually unblocked IP: {ip}")
    
    def get_blocked_ips(self) -> Dict[str, str]:
        """Get all currently blocked IPs with unblock times"""
        self._cleanup_expired_blocks()
        return {ip: unblock_time.isoformat() for ip, unblock_time in self.blocked_ips.items()}
    
    def get_ip_stats(self, ip: str) -> Dict:
        """Get statistics for a specific IP"""
        return dict(self.ip_stats.get(ip, {}))


# Global instance
ip_blocker = IPBlocker()
