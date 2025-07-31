#!/usr/bin/env python3
"""
GitHub App Authentication Test Script

This script helps debug GitHub App authentication issues by testing:
1. Private key format
2. JWT token generation 
3. GitHub API connectivity

Usage: python test_github_auth.py
"""

import jwt
import requests
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitHub App configuration (these need to be set)
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
print("GITHUB_APP_ID:", GITHUB_APP_ID)  # Debugging line to check if ID is set
print("GITHUB_APP_PRIVATE_KEY:", GITHUB_APP_PRIVATE_KEY)  # Debugging line to check if private key is set

def test_private_key_format():
    """Test if private key is in correct format"""
    logger.info("Testing private key format...")
    
    if not GITHUB_APP_PRIVATE_KEY or "Replace with" in GITHUB_APP_PRIVATE_KEY:
        logger.error("❌ Private key not configured")
        return False
    
    if not GITHUB_APP_PRIVATE_KEY.startswith("-----BEGIN"):
        logger.error("❌ Private key should start with -----BEGIN")
        return False
        
    if not GITHUB_APP_PRIVATE_KEY.strip().endswith("-----"):
        logger.error("❌ Private key should end with -----")
        return False
    
    # Check for common formatting issues
    if "\\n" in GITHUB_APP_PRIVATE_KEY:
        logger.warning("⚠️  Private key contains \\n - should be actual newlines")
        return False
    
    logger.info("✅ Private key format looks correct")
    return True

def test_jwt_generation():
    """Test JWT token generation"""
    logger.info("Testing JWT token generation...")
    
    try:
        payload = {
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(minutes=10),
            'iss': GITHUB_APP_ID
        }
        
        token = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm='RS256')
        logger.info("✅ JWT token generated successfully")
        logger.info(f"Token preview: {token[:50]}...")
        return token
        
    except Exception as e:
        logger.error(f"❌ JWT generation failed: {e}")
        return None

def test_github_api_connectivity():
    """Test basic GitHub API connectivity"""
    logger.info("Testing GitHub API connectivity...")
    
    try:
        response = requests.get("https://api.github.com/zen", timeout=10)
        if response.status_code == 200:
            logger.info("✅ GitHub API is reachable")
            return True
        else:
            logger.error(f"❌ GitHub API returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Cannot reach GitHub API: {e}")
        return False

def test_app_authentication(jwt_token):
    """Test GitHub App authentication"""
    logger.info("Testing GitHub App authentication...")
    
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    try:
        # Test getting app info
        response = requests.get(
            'https://api.github.com/app', 
            headers=headers,
            timeout=10
        )
        
        logger.info(f"App authentication response: {response.status_code}")
        
        if response.status_code == 200:
            app_data = response.json()
            logger.info(f"✅ App authenticated successfully!")
            logger.info(f"App name: {app_data.get('name')}")
            logger.info(f"App owner: {app_data.get('owner', {}).get('login')}")
            return True
        else:
            logger.error(f"❌ App authentication failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            
            if response.status_code == 401:
                if "Integration must generate a public key" in response.text:
                    logger.error("💡 Solution: Go to your GitHub App settings and generate a public key")
                elif "Bad credentials" in response.text:
                    logger.error("💡 Solution: Check your App ID and private key format")
            
            return False
            
    except Exception as e:
        logger.error(f"❌ App authentication test failed: {e}")
        return False

def print_configuration_help():
    """Print help for configuring GitHub App"""
    print("\n" + "="*60)
    print("GITHUB APP CONFIGURATION HELP")
    print("="*60)
    print()
    print("1. Create a GitHub App at: https://github.com/settings/apps")
    print("2. Set the App ID in this script")
    print("3. Generate a private key and copy it to this script")
    print("4. Make sure the private key includes header/footer lines:")
    print("   -----BEGIN PRIVATE KEY-----")
    print("   -----END PRIVATE KEY-----")
    print()
    print("5. In your GitHub App settings:")
    print("   - Set Homepage URL to your domain")
    print("   - Set Setup URL to: https://yourdomain.com/setup")
    print("   - Enable 'Request user authorization (OAuth) during installation'")
    print("   - Set Repository permissions: Contents (Read), Metadata (Read)")
    print()
    print("6. After creating the app, generate a public key in the settings")
    print("="*60)

def main():
    """Run all tests"""
    print("GitHub App Authentication Test")
    print("="*40)
    
    # Check configuration
    if not GITHUB_APP_ID or "Replace with" in GITHUB_APP_ID:
        logger.error("❌ GitHub App ID not configured")
        print_configuration_help()
        return
    
    logger.info(f"Testing with App ID: {GITHUB_APP_ID}")
    
    # Run tests
    tests_passed = 0
    total_tests = 4
    
    if test_private_key_format():
        tests_passed += 1
    
    if test_github_api_connectivity():
        tests_passed += 1
    
    jwt_token = test_jwt_generation()
    if jwt_token:
        tests_passed += 1
        
        if test_app_authentication(jwt_token):
            tests_passed += 1
    
    # Results
    print("\n" + "="*40)
    print(f"RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your GitHub App should work correctly.")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        if tests_passed < 2:
            print_configuration_help()

if __name__ == "__main__":
    main()
