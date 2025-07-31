#!/usr/bin/env python3
"""
GitHub App Installation Token Generator

This script gets access tokens for all installations of your GitHub App.
It uses the App ID and private key from environment variables.

Usage: python get_installation_tokens.py

Environment variables required:
- GITHUB_APP_ID: Your GitHub App ID
- GITHUB_APP_PRIVATE_KEY: Your GitHub App private key
"""

import os
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

async def get_all_installations(jwt_token: str) -> list:
    """Get all installations for the GitHub App"""
    try:
        logger.info("Fetching all installations...")
        
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
                logger.info(f"Found {len(installations)} installations")
                return installations
            else:
                logger.error(f"Failed to get installations: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
                
    except Exception as e:
        logger.error(f"Error getting installations: {str(e)}")
        return []

async def get_installation_token(installation_id: int, jwt_token: str) -> dict:
    """Get installation access token"""
    try:
        logger.info(f"Getting access token for installation {installation_id}")
        
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
                token_data = response.json()
                return {
                    "success": True,
                    "token": token_data["token"],
                    "expires_at": token_data["expires_at"]
                }
            else:
                logger.error(f"Failed to get token for installation {installation_id}: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
    except Exception as e:
        logger.error(f"Error getting installation token for {installation_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_installation_repositories(installation_id: int, access_token: str) -> list:
    """Get repositories for an installation"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code == 200:
                repo_data = response.json()
                return repo_data.get("repositories", [])
            else:
                logger.error(f"Failed to get repositories for installation {installation_id}")
                return []
                
    except Exception as e:
        logger.error(f"Error getting repositories for installation {installation_id}: {str(e)}")
        return []

def print_separator():
    """Print a separator line"""
    print("=" * 80)

async def main():
    """Main function to get and display all installation tokens"""
    print_separator()
    print("GitHub App Installation Token Generator")
    print_separator()
    
    # Validate configuration
    if not GITHUB_APP_ID:
        logger.error("❌ GITHUB_APP_ID environment variable not set")
        return
    
    if not GITHUB_APP_PRIVATE_KEY:
        logger.error("❌ GITHUB_APP_PRIVATE_KEY environment variable not set")
        return
    
    print(f"App ID: {GITHUB_APP_ID}")
    print()
    
    try:
        # Generate JWT token
        jwt_token = generate_jwt_token()
        
        # Get all installations
        installations = await get_all_installations(jwt_token)
        
        if not installations:
            print("❌ No installations found or failed to fetch installations")
            return
        
        print(f"Found {len(installations)} installation(s):")
        print()
        
        # Process each installation
        for i, installation in enumerate(installations, 1):
            installation_id = installation.get("id")
            account = installation.get("account", {})
            account_login = account.get("login", "unknown")
            account_type = account.get("type", "unknown")
            created_at = installation.get("created_at", "unknown")
            
            print(f"Installation #{i}:")
            print(f"  ID: {installation_id}")
            print(f"  Account: {account_login} ({account_type})")
            print(f"  Created: {created_at}")
            
            # Get access token for this installation
            token_result = await get_installation_token(installation_id, jwt_token)
            
            if token_result["success"]:
                access_token = token_result["token"]
                expires_at = token_result["expires_at"]
                
                print(f"  ✅ Access Token: {access_token}")
                print(f"  Expires: {expires_at}")
                
                # Get repositories for this installation
                repositories = await get_installation_repositories(installation_id, access_token)
                if repositories:
                    print(f"  Repositories ({len(repositories)}):")
                    for repo in repositories:
                        repo_name = repo.get("full_name", "unknown")
                        private = repo.get("private", False)
                        visibility = "private" if private else "public"
                        print(f"    - {repo_name} ({visibility})")
                else:
                    print("  No repositories found")
            else:
                print(f"  ❌ Failed to get access token: {token_result['error']}")
            
            print()
        
        print_separator()
        print("✅ Token generation complete!")
        print()
        print("Note: Access tokens expire after 1 hour and should be regenerated as needed.")
        print_separator()
        
    except Exception as e:
        logger.error(f"❌ Script failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
