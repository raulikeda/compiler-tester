#!/usr/bin/env python3
"""
Test script for GitHub issue creation

This script tests issue creation with hardcoded repository data
to help debug the 403 permission error.
"""

import os
import asyncio
import httpx
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub App configuration
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")

# Hardcoded test data - replace with your actual values
TEST_REPO_USERNAME = "logcomptester"
TEST_REPO_NAME = "teste"
TEST_INSTALLATION_ID = 78526212  # From your logs

def generate_jwt_token() -> str:
    """Generate JWT token for GitHub App authentication"""
    if not GITHUB_APP_PRIVATE_KEY or "Replace with" in GITHUB_APP_PRIVATE_KEY:
        raise Exception("GitHub App private key not configured")
    
    try:
        payload = {
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(minutes=10),
            'iss': GITHUB_APP_ID
        }
        
        token = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm='RS256')
        print("✅ JWT token generated successfully")
        return token
        
    except Exception as e:
        print(f"❌ Error generating JWT token: {e}")
        raise

async def get_installation_token(installation_id: int, jwt_token: str) -> str:
    """Get installation access token"""
    try:
        print(f"🔑 Requesting access token for installation {installation_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 201:
                data = response.json()
                print("✅ Successfully obtained installation access token")
                return data["token"]
            else:
                print(f"❌ Failed to get installation token: {response.status_code}")
                print(f"Response: {response.text}")
                raise Exception(f"Failed to get installation token: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Error getting installation access token: {e}")
        raise

async def check_app_permissions(installation_id: int, jwt_token: str):
    """Check what permissions the app has"""
    try:
        print("🔍 Checking app permissions...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 200:
                installation_data = response.json()
                permissions = installation_data.get("permissions", {})
                print("📋 App permissions:")
                for perm, level in permissions.items():
                    print(f"  - {perm}: {level}")
                return permissions
            else:
                print(f"❌ Failed to get installation info: {response.status_code}")
                return {}
                
    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
        return {}

async def test_repository_access(git_username: str, repository_name: str, access_token: str):
    """Test if we can access the repository"""
    try:
        print(f"🔍 Testing repository access for {git_username}/{repository_name}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{git_username}/{repository_name}",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 200:
                repo_data = response.json()
                permissions = repo_data.get("permissions", {})
                print("✅ Repository accessible")
                print("📋 Repository permissions:")
                for perm, value in permissions.items():
                    print(f"  - {perm}: {value}")
                return True
            else:
                print(f"❌ Repository not accessible: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error accessing repository: {e}")
        return False

async def test_issue_creation(git_username: str, repository_name: str, access_token: str):
    """Test creating a GitHub issue"""
    try:
        print(f"🐛 Testing issue creation for {git_username}/{repository_name}")
        
        issue_data = {
            "title": "Test Issue - Compiler Tester Debug",
            "body": "This is a test issue created by the Compiler Tester debug script.\n\n**Test Details:**\n- Created at: " + datetime.now().isoformat() + "\n- Purpose: Testing GitHub App permissions\n\nThis issue can be safely closed."
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{git_username}/{repository_name}/issues",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                json=issue_data
            )
            
            print(f"📊 Issue creation response: {response.status_code}")
            
            if response.status_code == 201:
                issue_response = response.json()
                issue_url = issue_response.get("html_url")
                print(f"✅ Successfully created test issue: {issue_url}")
                return issue_url
            else:
                print(f"❌ Failed to create issue: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")
                print(f"Response body: {response.text}")
                
                # Parse error details
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        print(f"💡 Error message: {error_data['message']}")
                    if "documentation_url" in error_data:
                        print(f"📖 Documentation: {error_data['documentation_url']}")
                except:
                    pass
                
                return None
                
    except Exception as e:
        print(f"❌ Error creating issue: {e}")
        return None

async def main():
    """Main test function"""
    print("=" * 60)
    print("GitHub Issue Creation Debug Script")
    print("=" * 60)
    print()
    
    # Validate configuration
    if not GITHUB_APP_ID:
        print("❌ GITHUB_APP_ID not configured")
        return
    
    if not GITHUB_APP_PRIVATE_KEY:
        print("❌ GITHUB_APP_PRIVATE_KEY not configured")
        return
    
    print(f"🔧 Configuration:")
    print(f"  App ID: {GITHUB_APP_ID}")
    print(f"  Installation ID: {TEST_INSTALLATION_ID}")
    print(f"  Test Repository: {TEST_REPO_USERNAME}/{TEST_REPO_NAME}")
    print()
    
    try:
        # Step 1: Generate JWT token
        jwt_token = generate_jwt_token()
        
        # Step 2: Check app permissions
        await check_app_permissions(TEST_INSTALLATION_ID, jwt_token)
        print()
        
        # Step 3: Get installation access token
        access_token = await get_installation_token(TEST_INSTALLATION_ID, jwt_token)
        print()
        
        # Step 4: Test repository access
        repo_accessible = await test_repository_access(TEST_REPO_USERNAME, TEST_REPO_NAME, access_token)
        print()
        
        if not repo_accessible:
            print("❌ Cannot proceed with issue creation - repository not accessible")
            return
        
        # Step 5: Test issue creation
        issue_url = await test_issue_creation(TEST_REPO_USERNAME, TEST_REPO_NAME, access_token)
        print()
        
        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        if issue_url:
            print("✅ All tests passed! Issue creation works.")
            print(f"🔗 Test issue: {issue_url}")
        else:
            print("❌ Issue creation failed. Check the errors above.")
            print()
            print("💡 Common solutions:")
            print("  1. Ensure the GitHub App has 'Issues: Write' permission")
            print("  2. Reinstall the GitHub App with correct permissions")
            print("  3. Check if the repository allows issue creation")
            print("  4. Verify the app is installed on the correct repository")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Script failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
