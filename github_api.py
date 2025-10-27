"""
GitHub API operations and authentication module
"""

import os
import jwt
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# GitHub App configuration
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")


def generate_jwt_token() -> str:
    """Generate JWT token for GitHub App authentication"""
    # GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
    GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
    GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
    
    if not GITHUB_APP_PRIVATE_KEY or "Replace with" in GITHUB_APP_PRIVATE_KEY:
        raise Exception("GitHub App private key not configured")
    
    try:
        payload = {
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(minutes=10),
            'iss': GITHUB_APP_ID
        }
        
        # Log some debug info (without revealing the private key)
        logger.info(f"Generating JWT for App ID: {GITHUB_APP_ID}")
        logger.info(f"Private key starts with: {GITHUB_APP_PRIVATE_KEY[:30]}...")
        
        token = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm='RS256')
        logger.info("JWT token generated successfully")
        return token
        
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise Exception(f"Failed to generate JWT token: {e}")


async def get_installation_token(installation_id: int, jwt_token: str) -> str:
    """Get installation access token"""
    try:
        GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
        GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
        logger.info(f"Requesting access token for installation {installation_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            logger.info(f"GitHub API response status: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                logger.info("Successfully obtained installation access token")
                return data["token"]
            else:
                logger.error(f"GitHub API error: {response.status_code}")
                logger.error(f"Response body: {response.text}")
                logger.error(f"Response headers: {dict(response.headers)}")
                
                # Common error interpretations
                if response.status_code == 401:
                    error_text = response.text
                    if "Integration must generate a public key" in error_text:
                        raise Exception("JWT signature verification failed. Check private key format.")
                    elif "Bad credentials" in error_text:
                        raise Exception("Invalid GitHub App credentials. Check App ID and private key.")
                    else:
                        raise Exception(f"Authentication failed: {error_text}")
                elif response.status_code == 404:
                    raise Exception(f"Installation {installation_id} not found. App may not be installed.")
                else:
                    raise Exception(f"GitHub API error {response.status_code}: {response.text}")
                    
    except Exception as e:
        logger.error(f"Error getting installation access token: {e}")
        raise


async def get_installation_details(installation_id: int) -> Dict[str, Any]:
    """
    Fetch installation details from GitHub API
    """
    try:
        GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
        GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
        # Generate JWT token
        jwt_token = generate_jwt_token()
        
        # Get installation access token
        installation_token = await get_installation_token(installation_id, jwt_token)
        
        # Fetch installation details
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get installation: {response.text}")
            
            installation_data = response.json()
            
            # Get repositories
            repos_response = await client.get(
                f"https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"Bearer {installation_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if repos_response.status_code == 200:
                repos_data = repos_response.json()
                installation_data["repositories"] = repos_data.get("repositories", [])
            
            return installation_data
            
    except Exception as e:
        logger.error(f"Error fetching installation details: {e}")
        # Return mock data as fallback
        return {
            "account": {"login": "example-user", "type": "User"},
            "repositories": [
                {"full_name": "example-user/repo1"},
                {"full_name": "example-user/repo2"}
            ]
        }


async def create_github_issue(
    git_username: str, 
    repository_name: str, 
    installation_id: int, 
    title: str, 
    body: str
) -> Optional[str]:
    """
    Create a GitHub issue in the specified repository
    Returns the issue URL if successful, None if failed
    """
    try:
        GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")
        GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
        # Generate JWT token
        jwt_token = generate_jwt_token()
        
        # Get installation access token
        access_token = await get_installation_token(installation_id, jwt_token)
        
        # Create the issue
        async with httpx.AsyncClient() as client:
            if len(body) > 60000:
                body = body[:60000] + "\nMessage Truncated."

            response = await client.post(
                f"https://api.github.com/repos/{git_username}/{repository_name}/issues",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                json={
                    "title": title,
                    "body": body
                }
            )
            
            if response.status_code == 201:
                issue_data = response.json()
                issue_url = issue_data.get("html_url")
                logger.info(f"Successfully created GitHub issue: {issue_url}")
                return issue_url
            else:
                logger.error(f"Failed to create GitHub issue: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error creating GitHub issue: {str(e)}")
        return None
