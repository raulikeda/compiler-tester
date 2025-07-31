#!/usr/bin/env python3
"""
GitHub App Installation Removal Script

This script removes a GitHub App installation using an access token.
The access token identifies which installation to remove.

Usage: python remove_installation.py <access_token>

Environment variables required:
- GITHUB_APP_ID: Your GitHub App ID
- GITHUB_APP_PRIVATE_KEY: Your GitHub App private key

Arguments:
- access_token: The installation access token for the installation to remove
"""

import os
import sys
import asyncio
import httpx
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GitHub App configuration
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")

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
        
        logger.info(f"Generating JWT for App ID: {GITHUB_APP_ID}")
        
        token = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm='RS256')
        logger.info("JWT token generated successfully")
        return token
        
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise Exception(f"Failed to generate JWT token: {e}")

async def get_installation_info(access_token: str) -> dict:
    """Get installation information from access token"""
    try:
        logger.info("Getting installation information...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 200:
                # The response doesn't directly give us installation ID, 
                # but we can get it from the installation field in repositories
                data = response.json()
                repositories = data.get("repositories", [])
                
                if repositories:
                    # Get installation info from any repository
                    installation = repositories[0].get("owner", {})
                    
                    # Try to get more detailed installation info
                    installation_response = await client.get(
                        "https://api.github.com/user/installations",
                        headers={
                            "Authorization": f"token {access_token}",
                            "Accept": "application/vnd.github.v3+json",
                            "X-GitHub-Api-Version": "2022-11-28"
                        }
                    )
                    
                    if installation_response.status_code == 200:
                        installations_data = installation_response.json()
                        installations = installations_data.get("installations", [])
                        
                        # Find our app's installation
                        for inst in installations:
                            if str(inst.get("app_id")) == str(GITHUB_APP_ID):
                                return {
                                    "success": True,
                                    "installation_id": inst.get("id"),
                                    "account": inst.get("account", {}),
                                    "repositories": repositories
                                }
                
                # Fallback: try to extract from repository data
                if repositories:
                    return {
                        "success": True,
                        "installation_id": None,  # We'll need to find this differently
                        "account": repositories[0].get("owner", {}),
                        "repositories": repositories
                    }
                else:
                    return {
                        "success": False,
                        "error": "No repositories found for this installation"
                    }
            else:
                logger.error(f"Failed to get installation info: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
    except Exception as e:
        logger.error(f"Error getting installation info: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def find_installation_id_by_account(jwt_token: str, account_login: str) -> int:
    """Find installation ID by account login"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 200:
                installations = response.json()
                for installation in installations:
                    account = installation.get("account", {})
                    if account.get("login") == account_login:
                        return installation.get("id")
                return None
            else:
                logger.error(f"Failed to get installations: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Error finding installation ID: {str(e)}")
        return None

async def remove_installation(installation_id: int, jwt_token: str) -> dict:
    """Remove the GitHub App installation"""
    try:
        logger.info(f"Removing installation {installation_id}...")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 204:
                logger.info("✅ Installation removed successfully")
                return {
                    "success": True,
                    "message": "Installation removed successfully"
                }
            else:
                logger.error(f"Failed to remove installation: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
    except Exception as e:
        logger.error(f"Error removing installation: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def print_separator():
    """Print a separator line"""
    print("=" * 80)

def print_usage():
    """Print usage information"""
    print("Usage: python remove_installation.py <access_token>")
    print()
    print("Arguments:")
    print("  access_token    The installation access token for the installation to remove")
    print()
    print("Environment variables required:")
    print("  GITHUB_APP_ID         Your GitHub App ID")
    print("  GITHUB_APP_PRIVATE_KEY Your GitHub App private key")

async def main():
    """Main function to remove a GitHub App installation"""
    print_separator()
    print("GitHub App Installation Removal Script")
    print_separator()
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("❌ Error: Missing access token argument")
        print()
        print_usage()
        return
    
    access_token = sys.argv[1]
    
    # Validate configuration
    if not GITHUB_APP_ID:
        logger.error("❌ GITHUB_APP_ID environment variable not set")
        return
    
    if not GITHUB_APP_PRIVATE_KEY:
        logger.error("❌ GITHUB_APP_PRIVATE_KEY environment variable not set")
        return
    
    print(f"App ID: {GITHUB_APP_ID}")
    print(f"Access Token: {access_token[:20]}...")
    print()
    
    try:
        # Get installation information
        install_info = await get_installation_info(access_token)
        
        if not install_info["success"]:
            print(f"❌ Failed to get installation info: {install_info['error']}")
            return
        
        installation_id = install_info.get("installation_id")
        account = install_info.get("account", {})
        repositories = install_info.get("repositories", [])
        
        account_login = account.get("login", "unknown")
        account_type = account.get("type", "unknown")
        
        print(f"Installation Information:")
        print(f"  Account: {account_login} ({account_type})")
        print(f"  Repositories: {len(repositories)}")
        
        if repositories:
            for repo in repositories[:5]:  # Show first 5 repositories
                repo_name = repo.get("full_name", "unknown")
                private = repo.get("private", False)
                visibility = "private" if private else "public"
                print(f"    - {repo_name} ({visibility})")
            if len(repositories) > 5:
                print(f"    ... and {len(repositories) - 5} more")
        
        # If we don't have installation_id, try to find it
        if not installation_id:
            logger.info("Installation ID not found in token response, searching...")
            jwt_token = generate_jwt_token()
            installation_id = await find_installation_id_by_account(jwt_token, account_login)
            
            if not installation_id:
                print(f"❌ Could not find installation ID for account {account_login}")
                return
        
        print(f"  Installation ID: {installation_id}")
        print()
        
        # Confirm removal
        confirmation = input(f"⚠️  Are you sure you want to remove the installation for {account_login}? (yes/no): ")
        if confirmation.lower() not in ['yes', 'y']:
            print("❌ Installation removal cancelled")
            return
        
        # Generate JWT token for removal
        jwt_token = generate_jwt_token()
        
        # Remove the installation
        result = await remove_installation(installation_id, jwt_token)
        
        if result["success"]:
            print_separator()
            print("✅ Installation removed successfully!")
            print()
            print(f"The GitHub App has been uninstalled from {account_login}")
            print("All associated access tokens are now invalid")
            print_separator()
        else:
            print(f"❌ Failed to remove installation: {result['error']}")
        
    except Exception as e:
        logger.error(f"❌ Script failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
