"""
Badge operations module for README.md badge management
"""

import os
import base64
import httpx
import logging
from typing import Dict, Any, List, Optional
from github_api import generate_jwt_token, get_installation_token

logger = logging.getLogger(__name__)


async def add_badge_to_readme(git_username: str, repository_name: str, installation_token: str, base_url: str = None) -> bool:
    """
    Automatically add a compilation status badge to the repository's README.md
    """
    if not base_url:
        base_url = "https://yourdomain.com"  # Replace with your actual domain
    
    badge_url = f"{base_url}/svg/{git_username}/{repository_name}"
    badge_markdown = f"[![Compilation Status]({badge_url})]({badge_url})"
    
    try:
        async with httpx.AsyncClient() as client:
            # Get current README.md content
            readme_response = await client.get(
                f"https://api.github.com/repos/{git_username}/{repository_name}/readme",
                headers={
                    "Authorization": f"Bearer {installation_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
                        
            if readme_response.status_code == 200:
                readme_data = readme_response.json()                
                current_content = base64.b64decode(readme_data["content"]).decode('utf-8')
                sha = readme_data["sha"]
                
                # Check if badge already exists
                if badge_url in current_content:
                    logger.info(f"Badge already exists in {git_username}/{repository_name}")
                    return True
                
                # Add badge at the top of README
                new_content = f"# {repository_name}\n\n{badge_markdown}\n\n" + current_content.lstrip()
                
                # If README starts with a title, add badge after it
                lines = current_content.split('\n')
                if lines and lines[0].startswith('#'):
                    # Find the first non-title line
                    insert_index = 1
                    while insert_index < len(lines) and (lines[insert_index].startswith('#') or lines[insert_index].strip() == ''):
                        insert_index += 1
                    
                    lines.insert(insert_index, f"\n{badge_markdown}\n")
                    new_content = '\n'.join(lines)
                
            elif readme_response.status_code == 404:
                # README doesn't exist, create one with the badge
                new_content = f"# {repository_name}\n\n{badge_markdown}\n\nThis repository is monitored by Compiler Tester for automatic compilation status.\n"
                sha = None
            else:
                logger.error(f"Failed to get README for {git_username}/{repository_name}: {readme_response.status_code}")
                return False
            
            # Update README.md
            update_data = {
                "message": "Add compilation status badge",
                "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                "committer": {
                    "name": "Compiler Tester Bot",
                    "email": "compiler-tester@insper.edu.br"
                }
            }
            
            if sha:
                update_data["sha"] = sha
            
            update_response = await client.put(
                f"https://api.github.com/repos/{git_username}/{repository_name}/contents/README.md",
                headers={
                    "Authorization": f"Bearer {installation_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                json=update_data
            )
            
            if update_response.status_code in [200, 201]:
                logger.info(f"Successfully added badge to {git_username}/{repository_name}")
                return True
            else:
                logger.error(f"Failed to update README for {git_username}/{repository_name}: {update_response.status_code} - {update_response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error adding badge to {git_username}/{repository_name}: {e}")
        return False


async def add_badges_to_installation_repos(installation_id: int, repositories: List[Dict[str, Any]], base_url: str = None) -> Dict[str, bool]:
    """
    Add badges to all repositories in an installation
    """
    results = {}
    
    try:
        # Generate tokens
        jwt_token = generate_jwt_token()
        installation_token = await get_installation_token(installation_id, jwt_token)
        
        for repo in repositories:
            repo_full_name = repo.get("full_name", "")
            if "/" in repo_full_name:
                git_username, repository_name = repo_full_name.split("/", 1)
                
                # Check if repository has Contents write permission
                repo_permissions = repo.get("permissions", {})
                logger.info(f"Checking permissions for {repo_full_name}: {repo_permissions}")
                has_contents_permission = (
                    repo_permissions.get("contents", False) or 
                    repo_permissions.get("push", False) or  # Alternative permission name
                    repo_permissions.get("admin", False)    # Admin includes all permissions
                )
                
                if False and not has_contents_permission:
                    logger.warning(f"No contents/push permission for {repo_full_name} (permissions: {repo_permissions}), skipping badge addition")
                    results[repo_full_name] = False
                    continue
                
                success = await add_badge_to_readme(git_username, repository_name, installation_token, base_url)
                results[repo_full_name] = success
                
    except Exception as e:
        logger.error(f"Error adding badges to installation {installation_id}: {e}")
    
    return results
