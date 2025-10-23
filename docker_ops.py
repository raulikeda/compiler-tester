"""
Docker container operations module
"""

import os
import asyncio
import logging
from typing import Optional
from db.database import db_manager

logger = logging.getLogger(__name__)

# Callback URL for Docker container
CALLBACK_URL = os.getenv("CALLBACK_URL", "https://compiler-tester.insper-comp.com.br/api/test-result")
API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")


async def run_docker_container_async(
    git_username: str,
    repository_name: str,
    repo_language: str,
    language: str,
    version: str,
    file_extension: str,
    command_template: str,
    access_token: str,
    release: str
) -> None:
    """
    Run Docker container asynchronously for compilation testing
    """
    CALLBACK_URL = os.getenv("CALLBACK_URL", "https://compiler-tester.insper-comp.com.br/api/test-result")
    API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")

    try:
        # Extract version from release (first 4 characters)
        version_short = release[:4] if len(release) >= 4 else release
        
        # Build Docker command
        docker_cmd = [
            "docker", "run", "--rm", "-it",
            "-e", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1",
            "-e", "DOTNET_NOLOGO=1",
            "-e", "DOTNET_CLI_TELEMETRY_OPTOUT=1",
            f"compiler-testing-lib-{repo_language.lower().replace("#","s").replace("++","pp")}",
            "--git_username", git_username,
            "--git_repository", repository_name,
            "--language", language,
            "--version", version_short,
            "--file_extension", file_extension,
            "--max_errors", "5",
            "--timeout", "30",
            "--command_template", command_template,
            "--token", access_token,
            "--release", release,
            "--callback_url", CALLBACK_URL,
            "--api_secret", API_SECRET
        ]
        
        logger.info(f"Starting Docker container for {git_username}/{repository_name}:{release}")
        logger.info(f"Docker command: {' '.join(docker_cmd[:4])} ... (args hidden for security)")
        
        # Run Docker container asynchronously
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Don't wait for completion - let it run in background
        logger.info(f"Docker container started with PID: {process.pid}")
        
        # Optionally log the process completion in background
        asyncio.create_task(_monitor_docker_process(process, git_username, repository_name, release))
        
    except Exception as e:
        logger.error(f"Error starting Docker container for {git_username}/{repository_name}:{release} - {e}")


async def _monitor_docker_process(process, git_username: str, repository_name: str, release: str):
    """Monitor Docker process completion and log results"""
    try:
        CALLBACK_URL = os.getenv("CALLBACK_URL", "https://compiler-tester.insper-comp.com.br/api/test-result")
        API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")
        #stdout, stderr = await process.communicate()
        # Wait for process to complete, but enforce timeout
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=180)
        except asyncio.TimeoutError:
            logger.warning(f"Docker timeout after {timeout}s for {git_username}/{repository_name}:{release}")
            process.kill()
            await process.wait()
            repo_info = db_manager.get_repository_info(git_username, repository_name)
            installation_id = repo_info['installation_id']
            url = await create_github_issue(
                git_username=git_username,
                repository_name=repository_name,
                installation_id=installation_id,
                title="Docker container - FAILED",
                body="Your submission failed the automated tests. Something in your submission is crashing the container."
            )

            if url:
                logger.info(f"Issue created: {url}")
            else:
                logger.warning("Issue creation failed")

            return  # You can also send a timeout result to CALLBACK_URL here
        
        if process.returncode == 0:
            logger.info(f"Docker container completed successfully for {git_username}/{repository_name}:{release}")
            if stdout:
                logger.debug(f"Docker stdout: {stdout.decode()}")
        else:
            logger.warning(f"Docker container failed for {git_username}/{repository_name}:{release} with code {process.returncode}")
            if stderr:
                logger.error(f"Docker stderr: {stderr.decode()}")
                
    except Exception as e:
        logger.error(f"Error monitoring Docker process for {git_username}/{repository_name}:{release} - {e}")
