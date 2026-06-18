#!/usr/bin/env python3
"""
Test script to verify IP blocking system functionality
Simulates attack patterns from the log file
"""

import httpx
import asyncio
import sys
from typing import List

class IPBlockTester:
    def __init__(self, base_url: str, verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        
    async def test_suspicious_paths(self, count: int = 10):
        """Test detection of suspicious path scanning"""
        paths = [
            "/.env",
            "/.git/HEAD",
            "/.git/config",
            "/.aws/credentials",
            "/config.php",
            "/.ssh/id_rsa",
            "/terraform.tfstate",
            "/.env.backup",
            "/backup.sql",
            "/.git/index",
        ]
        
        print(f"\n[TEST 1] Scanning suspicious paths ({count} requests)...")
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for i, path in enumerate(paths[:count]):
                try:
                    response = await client.get(f"{self.base_url}{path}", timeout=5)
                    status = "✓" if response.status_code in [404, 403] else "✗"
                    print(f"  {status} {path} -> {response.status_code}")
                except Exception as e:
                    print(f"  ✗ {path} -> ERROR: {e}")
                
                # Check if blocked
                if response.status_code == 403:
                    print(f"\n⚠️  IP WAS BLOCKED! (After {i+1} suspicious requests)")
                    return True
        
        return False
    
    async def test_rpc_endpoints(self):
        """Test detection of RPC endpoint probing"""
        endpoints = [
            "/mcp",
            "/jsonrpc",
            "/actuator",
            "/jsonrpc",
            "/mcp",
        ]
        
        print(f"\n[TEST 2] Probing RPC endpoints ({len(endpoints)} requests)...")
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for i, endpoint in enumerate(endpoints):
                try:
                    response = await client.post(f"{self.base_url}{endpoint}", timeout=5)
                    status = "✓" if response.status_code in [404, 403] else "✗"
                    print(f"  {status} POST {endpoint} -> {response.status_code}")
                except Exception as e:
                    print(f"  ✗ POST {endpoint} -> ERROR: {e}")
                
                if response.status_code == 403:
                    print(f"\n⚠️  IP WAS BLOCKED! (After {i+1} RPC probes)")
                    return True
        
        return False
    
    async def test_failed_requests(self, count: int = 25):
        """Test detection of excessive failed requests"""
        print(f"\n[TEST 3] Making failed requests ({count} requests)...")
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for i in range(count):
                try:
                    response = await client.get(
                        f"{self.base_url}/nonexistent-path-{i}",
                        timeout=5
                    )
                    status = "✓" if response.status_code == 404 else "✗"
                    print(f"  {status} Request {i+1} -> {response.status_code}", end="")
                    
                    if (i + 1) % 5 == 0:
                        print()
                    else:
                        print(" ", end="")
                except Exception as e:
                    print(f"  ✗ Request {i+1} -> ERROR: {e}")
                
                if response.status_code == 403:
                    print(f"\n\n⚠️  IP WAS BLOCKED! (After {i+1} failed requests)")
                    return True
        
        print()
        return False
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("=" * 60)
        print("IP BLOCKING SYSTEM - TEST SUITE")
        print("=" * 60)
        print(f"Target: {self.base_url}")
        
        blocked = False
        
        # Test 1: Suspicious paths
        blocked = await self.test_suspicious_paths(10)
        
        if not blocked:
            # Test 2: RPC endpoints
            blocked = await self.test_rpc_endpoints()
        
        if not blocked:
            # Test 3: Failed requests
            blocked = await self.test_failed_requests(25)
        
        print("\n" + "=" * 60)
        if blocked:
            print("✅ BLOCKING SYSTEM WORKING - IP was successfully blocked!")
        else:
            print("❌ IP was NOT blocked - system may not be working")
            print("   Check:")
            print("   1. Middleware is enabled in main.py")
            print("   2. Thresholds in security/config.py")
            print("   3. Check logs: tail -f log/uvicorn-*.log")
        print("=" * 60)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_blocking.py <server_url> [--no-verify-ssl]")
        print("Example: python test_blocking.py https://localhost:443 --no-verify-ssl")
        sys.exit(1)
    
    server_url = sys.argv[1]
    verify_ssl = "--no-verify-ssl" not in sys.argv
    
    tester = IPBlockTester(server_url, verify_ssl=verify_ssl)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
