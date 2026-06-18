#!/usr/bin/env python3
"""
Security Monitoring Dashboard
Monitor blocked IPs and suspicious activity in real-time
"""

import json
import os
from datetime import datetime
from pathlib import Path

BLOCKED_IPS_FILE = "./security/blocked_ips.json"
IP_STATS_FILE = "./security/ip_stats.json"


def load_blocked_ips():
    """Load blocked IPs from file"""
    if not os.path.exists(BLOCKED_IPS_FILE):
        return {}
    
    with open(BLOCKED_IPS_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def load_ip_stats():
    """Load IP statistics from file"""
    if not os.path.exists(IP_STATS_FILE):
        return {}
    
    with open(IP_STATS_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def display_blocked_ips():
    """Display currently blocked IPs"""
    blocked = load_blocked_ips()
    
    if not blocked:
        print("✓ No IPs currently blocked")
        return
    
    print("\n" + "=" * 80)
    print("CURRENTLY BLOCKED IPs")
    print("=" * 80)
    
    now = datetime.now()
    
    for ip, unblock_str in sorted(blocked.items()):
        try:
            unblock_time = datetime.fromisoformat(unblock_str)
            remaining = unblock_time - now
            hours = remaining.total_seconds() / 3600
            
            status = "🔴 BLOCKED"
            if hours > 0:
                time_str = f"{int(hours)}h {int((hours % 1) * 60)}m remaining"
            else:
                time_str = "Expired (cleanup pending)"
            
            print(f"\n{status}: {ip}")
            print(f"  Unblock time: {time_str}")
            
            # Show stats if available
            stats = load_ip_stats()
            if ip in stats:
                ip_stat = stats[ip]
                print(f"  Suspicious requests: {ip_stat.get('suspicious_count', 0)}")
                print(f"  Failed requests: {ip_stat.get('failed_count', 0)}")
        except (ValueError, TypeError):
            print(f"\nERROR: Invalid unblock time for {ip}: {unblock_str}")
    
    print("\n" + "=" * 80)


def display_suspicious_ips():
    """Display IPs with suspicious activity that aren't blocked yet"""
    stats = load_ip_stats()
    blocked = load_blocked_ips()
    
    suspicious = {
        ip: stat for ip, stat in stats.items()
        if (stat.get('suspicious_count', 0) > 0 or stat.get('failed_count', 0) > 0)
        and ip not in blocked
    }
    
    if not suspicious:
        print("\n✓ No suspicious activity detected")
        return
    
    print("\n" + "=" * 80)
    print("IPs WITH SUSPICIOUS ACTIVITY (Not Yet Blocked)")
    print("=" * 80)
    
    for ip in sorted(suspicious.keys(), key=lambda x: suspicious[x].get('suspicious_count', 0), reverse=True):
        stat = suspicious[ip]
        print(f"\n⚠️  {ip}")
        print(f"  Suspicious requests: {stat.get('suspicious_count', 0)}")
        print(f"  Failed requests: {stat.get('failed_count', 0)}")
        if stat.get('last_request'):
            print(f"  Last request: {stat['last_request']}")
    
    print("\n" + "=" * 80)


def display_summary():
    """Display summary statistics"""
    blocked = load_blocked_ips()
    stats = load_ip_stats()
    
    total_suspicious = sum(
        s.get('suspicious_count', 0) for s in stats.values()
    )
    total_failed = sum(
        s.get('failed_count', 0) for s in stats.values()
    )
    
    print("\n" + "=" * 80)
    print("SECURITY SUMMARY")
    print("=" * 80)
    print(f"Total blocked IPs: {len(blocked)}")
    print(f"Total tracked IPs: {len(stats)}")
    print(f"Total suspicious requests detected: {total_suspicious}")
    print(f"Total failed requests detected: {total_failed}")
    print(f"Last updated: {datetime.now().isoformat()}")
    print("=" * 80)


def clear_stats(ip=None):
    """Clear statistics for an IP (or all if ip is None)"""
    if ip:
        stats = load_ip_stats()
        if ip in stats:
            del stats[ip]
            with open(IP_STATS_FILE, 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"✓ Cleared stats for {ip}")
        else:
            print(f"IP {ip} not found in stats")
    else:
        # Clear all stats
        with open(IP_STATS_FILE, 'w') as f:
            json.dump({}, f)
        print("✓ Cleared all statistics")


def main():
    """Main menu"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "summary":
            display_summary()
        elif command == "blocked":
            display_blocked_ips()
        elif command == "suspicious":
            display_suspicious_ips()
        elif command == "clear-stats":
            ip = sys.argv[2] if len(sys.argv) > 2 else None
            clear_stats(ip)
        elif command == "all":
            display_summary()
            display_blocked_ips()
            display_suspicious_ips()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python security_monitor.py [summary|blocked|suspicious|clear-stats|all]")
        return
    
    # Interactive mode
    while True:
        print("\n" + "=" * 80)
        print("SECURITY MONITORING DASHBOARD")
        print("=" * 80)
        print("1. Summary")
        print("2. Show blocked IPs")
        print("3. Show suspicious IPs")
        print("4. Clear all statistics")
        print("5. Exit")
        print("-" * 80)
        
        choice = input("Select option (1-5): ").strip()
        
        if choice == "1":
            display_summary()
        elif choice == "2":
            display_blocked_ips()
        elif choice == "3":
            display_suspicious_ips()
        elif choice == "4":
            confirm = input("Clear all statistics? This cannot be undone (y/n): ").strip().lower()
            if confirm == 'y':
                clear_stats()
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
