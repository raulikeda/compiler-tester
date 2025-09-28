"""
Webhook processing module
"""

import json
import logging
import re
from fastapi import HTTPException
from github_api import generate_jwt_token, get_installation_token, create_github_issue
from docker_ops import run_docker_container_async
from db.database import db_manager

logger = logging.getLogger(__name__)


def _parse_semver(tag: str):
    """Parse tags like vX.Y.Z into a tuple of ints (X, Y, Z). Return None if invalid."""
    if not isinstance(tag, str):
        return None
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        return None
    return tuple(int(part) for part in m.groups())


def _is_greater_semver(a: str, b: str) -> bool:
    """Return True if tag a has a strictly greater patch than tag b (vX.Y.Z)."""
    va = _parse_semver(a)
    vb = _parse_semver(b)
    if va is None or vb is None:
        return False
    a_major, a_minor, a_patch = va
    b_major, b_minor, b_patch = vb
    if a_major == b_major:
        if a_minor == b_minor:
            return a_patch > b_patch

    return True


async def process_tag_event(git_username: str, repository_name: str, tag_name: str):
    """Process tag creation/push events - validate tag then start tests"""
    try:
        # Get repository info from database
        repo_info = db_manager.get_repository_info(git_username, repository_name)
        if not repo_info:
            logger.warning(f"Repository {git_username}/{repository_name} not found in database")
            return False

        # Validate tag format vX.X.X
        if _parse_semver(tag_name) is None:
            logger.info(f"Ignoring tag with invalid format: {tag_name} (expected vX.X.X)")
            issue_url = None
            try:
                if repo_info.get('installation_id'):
                    title = f"Invalid tag: {tag_name}"
                    body = (
                        f"An invalid tag was created: `{tag_name}`.\n\n"
                        f"The expected pattern is `vX.X.X` (e.g., `v1.2.3`).\n\n"
                        f"Please create a new tag following the semantic version pattern."
                    )
                    issue_url = await create_github_issue(
                        git_username, repository_name, repo_info['installation_id'], title, body
                    )
            except Exception as _:
                pass
            return {
                "status": "ignored",
                "reason": "invalid_format",
                "message": "Tag must follow vX.X.X",
                "tag": tag_name,
                "issue_url": issue_url,
            }

        # Ensure tag has not been processed before
        if db_manager.has_release_tag(git_username, repository_name, tag_name):
            logger.info(f"Ignoring duplicate tag already released: {tag_name}")
            issue_url = None
            try:
                if repo_info.get('installation_id'):
                    title = f"Duplicate tag: {tag_name}"
                    body = (
                        f"The tag `{tag_name}` was already used before for this repository.\n\n"
                        f"Please create a new tag with a higher version (e.g., `v1.2.4`)."
                    )
                    issue_url = await create_github_issue(
                        git_username, repository_name, repo_info['installation_id'], title, body
                    )
            except Exception as _:
                pass
            return {
                "status": "ignored",
                "reason": "duplicate",
                "message": "Tag was already processed before",
                "tag": tag_name,
                "issue_url": issue_url,
            }

        # Ensure tag is greater than the last processed semantic tag, if any
        prev_tags = [t for t in db_manager.get_release_tags(git_username, repository_name) if _parse_semver(t)]
        if prev_tags:
            # Determine the last tag based on the highest MINOR value
            last_tag = max(prev_tags, key=lambda t: _parse_semver(t)[1])
            if not _is_greater_semver(tag_name, last_tag):
                logger.info(f"Ignoring non-incremental tag: {tag_name} <= {last_tag}")
                issue_url = None
                try:
                    if repo_info.get('installation_id'):
                        title = f"Non-incremental tag: {tag_name}"
                        body = (
                            f"The new tag `{tag_name}` is not greater than the last valid tag `{last_tag}`.\n\n"
                            f"Please create a tag with a higher version (e.g., if the last was `{last_tag}`, use a higher one like `vX.Y.Z`)."
                        )
                        issue_url = await create_github_issue(
                            git_username, repository_name, repo_info['installation_id'], title, body
                        )
                except Exception as _:
                    pass
                return {
                    "status": "ignored",
                    "reason": "not_greater",
                    "message": f"Tag must be greater than last tag {last_tag}",
                    "tag": tag_name,
                    "last_tag": last_tag,
                    "issue_url": issue_url,
                }

        # Validate that the vMAJOR.MINOR version exists for the repository's semester
        major_minor = None
        parsed = _parse_semver(tag_name)
        if parsed:
            major_minor = f"v{parsed[0]}.{parsed[1]}"
        if not major_minor:
            # Should not happen due to earlier validation
            return {
                "status": "ignored",
                "reason": "invalid_format",
                "message": "Tag must follow vX.X.X",
                "tag": tag_name,
            }

        version_info = db_manager.get_version_info(repo_info['semester_name'], major_minor)
        if not version_info:
            logger.info(f"Ignoring tag with non-existent version in Semester: {major_minor} not found for {repo_info['semester_name']}")
            issue_url = None
            try:
                if repo_info.get('installation_id'):
                    title = f"Version not found: {major_minor}"
                    body = (
                        f"The tag `{tag_name}` maps to version `{major_minor}`, which is not a valid Version.\n\n"
                        f"Please check the version calendar in handouts website."
                    )
                    issue_url = await create_github_issue(
                        git_username, repository_name, repo_info['installation_id'], title, body
                    )
            except Exception as _:
                pass
            return {
                "status": "ignored",
                "reason": "version_not_found",
                "message": f"Version {major_minor} not found for semester {repo_info['semester_name']}",
                "tag": tag_name,
                "version": major_minor,
                "issue_url": issue_url,
            }
            
        # Get semester info for language and file extension
        semester_info = db_manager.get_semester_info(repo_info['semester_name'])
        
        if not semester_info or not repo_info.get('installation_id'):
            logger.warning(f"Missing semester info or installation_id for repository {git_username}/{repository_name}")
            return False
            
        # Generate access token
        jwt_token = generate_jwt_token()
        access_token = await get_installation_token(repo_info['installation_id'], jwt_token)
        
        # Run Docker container asynchronously (use vMAJOR.MINOR in 'version')
        await run_docker_container_async(
            git_username=git_username,
            repository_name=repository_name,
            repo_language=repo_info['language'],
            language=semester_info['language'],
            version=major_minor,
            file_extension=semester_info['extension'],
            command_template=repo_info['program_call'],
            access_token=access_token,
            release=tag_name
        )
        
        logger.info(f"Started Docker container for {git_username}/{repository_name}:{tag_name}")
        return {
            "status": "started",
            "message": "Tests started for valid tag",
            "tag": tag_name,
        }
        
    except Exception as e:
        logger.error(f"Error processing tag event for {git_username}/{repository_name}:{tag_name} - {e}")
        return {
            "status": "error",
            "message": f"{e}",
            "tag": tag_name,
        }


async def process_installation_event(action: str, payload: dict):
    """Process GitHub App installation events"""
    installation = payload.get("installation", {})
    installation_id = installation.get("id")
    account = installation.get("account", {})
    account_login = account.get("login", "unknown")
    
    logger.info(f"Installation event: {action} for installation {installation_id} (account: {account_login})")
    
    if action == "deleted":
        # App was uninstalled - clean up database
        try:
            # Get repositories that will be removed for logging
            repos_to_remove = db_manager.get_installation_repositories(installation_id)
            
            # Remove repositories associated with this installation
            repo_success = db_manager.remove_repositories_by_installation(installation_id)
            
            # Remove users who no longer have any repositories
            user_success = db_manager.remove_orphaned_users()
            
            if repo_success and user_success:
                logger.info(f"Successfully cleaned up data for uninstalled app (installation {installation_id})")
                removed_repos = [f"{repo['git_username']}/{repo['repository_name']}" for repo in repos_to_remove]
                
                return {
                    "status": "success",
                    "message": f"App uninstallation processed",
                    "installation_id": installation_id,
                    "account": account_login,
                    "removed_repositories": removed_repos
                }
            else:
                logger.error(f"Failed to clean up data for uninstalled app (installation {installation_id})")
                return {
                    "status": "error", 
                    "message": "Failed to clean up database",
                    "installation_id": installation_id
                }
                
        except Exception as e:
            logger.error(f"Error handling app uninstallation: {e}")
            return {
                "status": "error",
                "message": f"Error processing uninstallation: {str(e)}",
                "installation_id": installation_id
            }
    
    elif action == "created":
        # App was newly installed
        repositories = payload.get("repositories", [])
        repo_names = [repo.get("full_name", "") for repo in repositories]
        
        logger.info(f"App installed on {len(repositories)} repositories: {repo_names}")
        
        return {
            "status": "success",
            "message": "App installation detected",
            "installation_id": installation_id,
            "account": account_login,
            "repositories": repo_names,
            "next_step": "User should complete setup form"
        }
    
    elif action in ["added", "removed"]:
        # Repositories were added or removed from existing installation
        repositories_added = payload.get("repositories_added", [])
        repositories_removed = payload.get("repositories_removed", [])
        
        added_names = [repo.get("full_name", "") for repo in repositories_added]
        removed_names = [repo.get("full_name", "") for repo in repositories_removed]
        
        # Handle removed repositories
        if repositories_removed:
            try:
                for repo in repositories_removed:
                    repo_full_name = repo.get("full_name", "")
                    if "/" in repo_full_name:
                        git_username, repository_name = repo_full_name.split("/", 1)
                        
                        # Remove test results first
                        db_manager.remove_test_results_for_repo(git_username, repository_name)
                        
                        # Remove repository
                        db_manager.remove_repository(git_username, repository_name)
                
                # Clean up orphaned users
                db_manager.remove_orphaned_users()
                
                logger.info(f"Removed repositories: {removed_names}")
            except Exception as e:
                logger.error(f"Error removing repositories: {e}")
        
        return {
            "status": "success",
            "message": f"Repository access updated",
            "installation_id": installation_id,
            "repositories_added": added_names,
            "repositories_removed": removed_names
        }
    
    return {
        "status": "acknowledged",
        "message": f"Installation action '{action}' acknowledged"
    }


async def process_webhook_payload(event_type: str, payload: dict):
    """Main webhook processing function"""
    try:
        # Handle tag events specifically  
        if event_type == "create" and payload.get("ref_type") == "tag":
            tag_name = payload.get("ref")
            repository = payload.get("repository", {})
            repo_name = repository.get("full_name", "unknown")
            
            # Extract username and repository name
            if "/" in repo_name:
                git_username, repository_name = repo_name.split("/", 1)
                result = await process_tag_event(git_username, repository_name, tag_name)
                if isinstance(result, dict):
                    return {**result, "repository": repo_name}
                # Backward compatibility fallback
                return {
                    "status": "success" if result else "error",
                    "message": (f"Tag event processed: {tag_name}" if result else f"Failed to process tag event: {tag_name}"),
                    "repository": repo_name,
                }
        
        elif event_type == "push":
            # Handle push events for tags
            ref = payload.get("ref", "")
            if ref.startswith("refs/tags/"):
                tag_name = ref.replace("refs/tags/", "")
                repository = payload.get("repository", {})
                repo_name = repository.get("full_name", "unknown")
                
                # Extract username and repository name
                if "/" in repo_name:
                    git_username, repository_name = repo_name.split("/", 1)
                    result = await process_tag_event(git_username, repository_name, tag_name)
                    if isinstance(result, dict):
                        return {**result, "repository": repo_name}
                    return {
                        "status": "success" if result else "error",
                        "message": (f"Tag push processed: {tag_name}" if result else f"Failed to process tag push: {tag_name}"),
                        "repository": repo_name,
                    }
        
        elif event_type == "installation":
            # Handle GitHub App installation/uninstallation events
            action = payload.get("action")
            return await process_installation_event(action, payload)
        
        # For other event types, just acknowledge receipt
        return {
            "status": "acknowledged",
            "event_type": event_type,
            "message": "Webhook received but not processed"
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook payload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
