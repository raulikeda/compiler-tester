from fastapi import FastAPI, Request, HTTPException, Form, Depends, Header
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import json
import logging
from typing import Dict, Any, List, Optional, Annotated
from db.database import db_manager
import generate_badge as sr
import time
import hashlib
import httpx
import jwt
from datetime import datetime, timedelta
import subprocess
import tempfile
import os
from dotenv import load_dotenv
import base64

load_dotenv()

# GitHub App configuration
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "1578480")  # Your GitHub App ID

# Try to load private key from environment first, then from file
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")

# API Secret for secure endpoints
API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Compiler Tester API",
    description="API for handling GitHub webhooks, badges, and authentication",
    version="1.0.0"
)

# Templates for rendering HTML pages
templates = Jinja2Templates(directory="templates")

# Pydantic models for API endpoints
class TestResultData(BaseModel):
    version_name: str = Field(..., description="Version name for the test")
    release_name: str = Field(..., description="Release/tag name")
    git_username: str = Field(..., description="GitHub username")
    repository_name: str = Field(..., description="Repository name")
    test_status: str = Field(..., pattern="^(PASS|ERROR|FAILED)$", description="Test status: PASS, ERROR, or FAILED")
    issue_text: Optional[str] = Field(None, description="Optional issue description for failed tests")

class TestResultResponse(BaseModel):
    success: bool
    message: str
    issue_url: Optional[str] = Field(None, description="GitHub issue URL if created")
    
# Security dependency
async def verify_api_secret(x_api_secret: Annotated[str, Header()]) -> str:
    """Verify API secret from header"""
    if x_api_secret != API_SECRET:
        raise HTTPException(
            status_code=401,
            detail="Invalid API secret"
        )
    return x_api_secret

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Compiler Tester API is running"}

@app.post("/webhook")
async def webhook(request: Request):
    """
    Handle GitHub webhook events, specifically tag events
    """
    try:
        # Get the event type from headers
        event_type = request.headers.get("X-GitHub-Event")
        
        if not event_type:
            raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
        
        # Parse the JSON payload
        payload = await request.json()
        
        # Log the webhook event
        logger.info(f"Received GitHub webhook: {event_type}")
        
        # Handle tag events specifically
        if event_type == "create" and payload.get("ref_type") == "tag":
            tag_name = payload.get("ref")
            repository = payload.get("repository", {})
            repo_name = repository.get("full_name", "unknown")
            
            # Extract username and repository name
            if "/" in repo_name:
                git_username, repository_name = repo_name.split("/", 1)
                
                # Get repository info from database
                repo_info = db_manager.get_repository_info(git_username, repository_name)
                if repo_info:
                    # Get active versions for this semester
                    active_versions = db_manager.get_active_versions(repo_info['semester_name'])
                    
                    # Record test results for each active version
                    for version in active_versions:
                        # Run actual compilation tests
                        test_status = await run_actual_compilation_test(
                            git_username, repository_name, tag_name, version
                        )
                        
                        success = db_manager.record_test_result(
                            version['version_name'], 
                            tag_name, 
                            git_username, 
                            repository_name, 
                            test_status
                        )
                        
                        if success:
                            logger.info(f"Recorded test result for {repo_name}, version {version['version_name']}: {test_status}")
                else:
                    logger.warning(f"Repository {repo_name} not found in database")
            
            logger.info(f"New tag created: {tag_name} in repository: {repo_name}")
            
            return {
                "status": "success",
                "message": f"Tag event processed: {tag_name}",
                "repository": repo_name
            }
        
        elif event_type == "push":
            # Handle push events if needed
            ref = payload.get("ref", "")
            if ref.startswith("refs/tags/"):
                tag_name = ref.replace("refs/tags/", "")
                repository = payload.get("repository", {})
                repo_name = repository.get("full_name", "unknown")
                
                # Extract username and repository name
                if "/" in repo_name:
                    git_username, repository_name = repo_name.split("/", 1)
                    
                    # Get repository info from database
                    repo_info = db_manager.get_repository_info(git_username, repository_name)
                    if repo_info:
                        # Get active versions for this semester
                        active_versions = db_manager.get_active_versions(repo_info['semester_name'])
                        
                        # Record test results for each active version
                        for version in active_versions:
                            # Run actual compilation tests
                            test_status = await run_actual_compilation_test(
                                git_username, repository_name, tag_name, version
                            )
                            
                            success = db_manager.record_test_result(
                                version['version_name'], 
                                tag_name, 
                                git_username, 
                                repository_name, 
                                test_status
                            )
                            
                            if success:
                                logger.info(f"Recorded test result for {repo_name}, version {version['version_name']}: {test_status}")
                    else:
                        logger.warning(f"Repository {repo_name} not found in database")
                
                logger.info(f"Tag push detected: {tag_name} in repository: {repo_name}")
                
                return {
                    "status": "success",
                    "message": f"Tag push processed: {tag_name}",
                    "repository": repo_name
                }
        
        elif event_type == "installation":
            # Handle GitHub App installation/uninstallation events
            action = payload.get("action")
            installation = payload.get("installation", {})
            installation_id = installation.get("id")
            account = installation.get("account", {})
            account_login = account.get("login", "unknown")
            
            logger.info(f"Installation event: {action} for installation {installation_id} (account: {account_login})")
            
            if action == "deleted" and True: # Temporarily disabled
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
        
        # For other event types, just acknowledge receipt
        return {
            "status": "acknowledged",
            "event_type": event_type,
            "message": "Webhook received but not processed"
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/test-result", response_model=TestResultResponse)
async def save_test_result(
    test_data: TestResultData,
    api_secret: str = Depends(verify_api_secret)
) -> TestResultResponse:
    """
    Save a test result to the database.
    Requires a valid API secret in the X-API-Secret header.
    """
    try:
        logger.info(f"Received test result for {test_data.git_username}/{test_data.repository_name}")
        
        # Verify that the repository exists
        repo_info = db_manager.get_repository_info(test_data.git_username, test_data.repository_name)
        if not repo_info:
            logger.warning(f"Repository {test_data.git_username}/{test_data.repository_name} not found")
            raise HTTPException(
                status_code=404, 
                detail=f"Repository {test_data.git_username}/{test_data.repository_name} not found"
            )
        
        # Record the test result
        success = db_manager.record_test_result(
            version_name=test_data.version_name,
            release_name=test_data.release_name,
            git_username=test_data.git_username,
            repository_name=test_data.repository_name,
            test_status=test_data.test_status,
            issue_text=test_data.issue_text,
            semester_name=repo_info['semester_name']
        )
        
        if success:
            logger.info(f"Successfully recorded test result: {test_data.version_name}/{test_data.release_name} - {test_data.test_status}")
            
            # Create GitHub issue if test failed and there's issue text
            issue_url = None
            if test_data.test_status in ['ERROR', 'FAILED'] and test_data.issue_text and repo_info.get('installation_id'):
                issue_title = f"Errors in release {test_data.release_name}"
                try:
                    issue_url = await create_github_issue(
                        git_username=test_data.git_username,
                        repository_name=test_data.repository_name,
                        installation_id=repo_info['installation_id'],
                        title=issue_title,
                        body=test_data.issue_text
                    )
                    if issue_url:
                        logger.info(f"Created GitHub issue: {issue_url}")
                    else:
                        logger.warning(f"Failed to create GitHub issue for {test_data.git_username}/{test_data.repository_name}")
                except Exception as issue_error:
                    logger.error(f"Error creating GitHub issue: {str(issue_error)}")
                    # Don't fail the whole request if issue creation fails
            
            response_message = "Test result saved successfully"
            if issue_url:
                response_message += f". GitHub issue created: {issue_url}"
            
            return TestResultResponse(
                success=True,
                message=response_message,
                issue_url=issue_url
            )
        else:
            logger.error(f"Failed to record test result for {test_data.git_username}/{test_data.repository_name}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save test result to database"
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving test result: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
    
@app.get('/svg/{user}/{repo}')
async def svg(user, repo):
    report = sr.RepoReport(git_username = user, repository_name = repo)
    svg = report.compile()
    #resp = Response(response=svg, status=200, mimetype="image/svg+xml")
    logger.info(f"Generated badge for {user}/{repo}")

    now = time.strftime("%Y %m %d %H %M")
    txt = '{} {} {}'.format(user, repo, now).encode('utf-8')
    etag = hashlib.sha1(txt).hexdigest()
        
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "ETag": etag,
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    GitHub App login landing page
    """
    # GitHub App configuration (you'll need to replace these with your actual values)
    github_app_client_id = "1578480"  # Replace with your GitHub App client ID
    redirect_uri = "http://3.129.230.99/auth/callback"  # Replace with your callback URL
    
    # Scopes needed for your app
    scopes = "read:user,repo"
    
    # GitHub OAuth URL
    #github_oauth_url = f"https://github.com/login/oauth/authorize?client_id={github_app_client_id}&redirect_uri={redirect_uri}&scope={scopes}&state=random_state_string"
    github_oauth_url = f"https://github.com/apps/compiler-tester/installations/new"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Compiler Tester - GitHub Login</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f6f8fa;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }}
            .logo {{
                width: 80px;
                height: 80px;
                background: #24292e;
                border-radius: 50%;
                margin: 0 auto 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                font-weight: bold;
            }}
            h1 {{
                color: #24292e;
                margin-bottom: 10px;
                font-size: 24px;
            }}
            p {{
                color: #586069;
                margin-bottom: 30px;
                line-height: 1.5;
            }}
            .login-btn {{
                background-color: #24292e;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                text-decoration: none;
                display: inline-block;
                transition: background-color 0.2s;
                cursor: pointer;
            }}
            .login-btn:hover {{
                background-color: #1b1f23;
            }}
            .features {{
                margin-top: 30px;
                text-align: left;
            }}
            .feature {{
                margin-bottom: 10px;
                color: #586069;
            }}
            .feature::before {{
                content: "✓";
                color: #28a745;
                font-weight: bold;
                margin-right: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">CT</div>
            <h1>Compiler Tester</h1>
            <p>Connect your GitHub repositories to automatically test compilation on new releases.</p>
            
            <a href="{github_oauth_url}" class="login-btn">
                Login with GitHub
            </a>
            
            <div class="features">
                <div class="feature">Automatic compilation testing on tag creation</div>
                <div class="feature">Real-time build status badges</div>
                <div class="feature">GitHub webhook integration</div>
                <div class="feature">Secure GitHub App authentication</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/setup")
async def setup_callback(installation_id: int = None, setup_action: str = None):
    """
    Handle GitHub App installation setup callback
    """
    if not installation_id:
        raise HTTPException(status_code=400, detail="Missing installation_id")
    
    logger.info(f"App installed with installation_id: {installation_id}, action: {setup_action}")
    
    # Get installation details from GitHub API
    try:
        installation_data = await get_installation_details(installation_id)
        if not installation_data:
            raise HTTPException(status_code=400, detail="Could not fetch installation details")
        
        account_login = installation_data.get("account", {}).get("login", "unknown")
        repositories = installation_data.get("repositories", [])
        if len(repositories) != 1:
            # Show a HTML page to user that only single repository installations are supported
            # Remove the installation using the token
            try:
                jwt_token = generate_jwt_token()
                async with httpx.AsyncClient() as client:
                    delete_response = await client.delete(
                        f"https://api.github.com/app/installations/{installation_id}",
                        headers={
                            "Authorization": f"Bearer {jwt_token}",
                            "Accept": "application/vnd.github.v3+json",
                            "X-GitHub-Api-Version": "2022-11-28"
                        }
                    )
                    logger.info(f"Installation deletion response: {delete_response.status_code}")
            except Exception as e:
                logger.error(f"Failed to delete installation {installation_id}: {e}")
            
            # Return HTML page explaining the restriction
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Installation Error - Compiler Tester</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                        margin: 0;
                        padding: 0;
                        background-color: #f6f8fa;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
                        text-align: center;
                        max-width: 500px;
                        width: 100%;
                    }}
                    .error-icon {{
                        width: 80px;
                        height: 80px;
                        background: #dc3545;
                        border-radius: 50%;
                        margin: 0 auto 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 32px;
                        font-weight: bold;
                    }}
                    h1 {{
                        color: #dc3545;
                        margin-bottom: 10px;
                        font-size: 24px;
                    }}
                    p {{
                        color: #586069;
                        margin-bottom: 20px;
                        line-height: 1.5;
                    }}
                    .warning-box {{
                        background-color: #fff3cd;
                        border: 1px solid #ffeaa7;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 20px 0;
                        text-align: left;
                    }}
                    .warning-box h3 {{
                        color: #856404;
                        margin-top: 0;
                        margin-bottom: 10px;
                    }}
                    .warning-box p {{
                        color: #856404;
                        margin-bottom: 0;
                    }}
                    .btn {{
                        background-color: #2da44e;
                        color: white;
                        padding: 12px 24px;
                        border: none;
                        border-radius: 6px;
                        font-size: 16px;
                        text-decoration: none;
                        display: inline-block;
                        margin: 10px;
                        cursor: pointer;
                        transition: background-color 0.2s;
                    }}
                    .btn:hover {{
                        background-color: #2c974b;
                    }}
                    .btn-secondary {{
                        background-color: #6c757d;
                    }}
                    .btn-secondary:hover {{
                        background-color: #5a6268;
                    }}
                    .steps {{
                        text-align: left;
                        margin: 20px 0;
                    }}
                    .step {{
                        margin: 10px 0;
                        padding: 10px 0;
                    }}
                    .step-number {{
                        background-color: #0366d6;
                        color: white;
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 14px;
                        font-weight: bold;
                        margin-right: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">⚠️</div>
                    <h1>Installation Not Allowed</h1>
                    <p>We detected that you tried to install the Compiler Tester app on <strong>{len(repositories)} repositories</strong>.</p>
                    
                    <div class="warning-box">
                        <h3>⚠️ Single Repository Policy</h3>
                        <p>For optimal performance and focused testing, Compiler Tester only supports installations on <strong>exactly one repository at a time</strong>.</p>
                    </div>
                    
                    <div class="steps">
                        <h3>How to Install Correctly:</h3>
                        <div class="step">
                            <span class="step-number">1</span>
                            Click "Try Again" below to return to the login page
                        </div>
                        <div class="step">
                            <span class="step-number">2</span>
                            Choose <strong>"Only select repositories"</strong> (not "All repositories")
                        </div>
                        <div class="step">
                            <span class="step-number">3</span>
                            Select <strong>only ONE repository</strong> that you want to monitor
                        </div>
                        <div class="step">
                            <span class="step-number">4</span>
                            Complete the installation
                        </div>
                    </div>
                    
                    <p><strong>Why only one repository?</strong></p>
                    <ul style="text-align: left; color: #586069;">
                        <li>Better performance and faster compilation testing</li>
                        <li>Focused monitoring for specific projects</li>
                        <li>Easier management and debugging</li>
                        <li>More efficient resource usage</li>
                    </ul>
                    
                    <div style="margin-top: 30px;">
                        <a href="/login" class="btn">🔄 Try Again</a>
                        <a href="https://github.com/settings/installations" class="btn btn-secondary">⚙️ Manage Installations</a>
                    </div>
                    
                    <p style="margin-top: 20px; color: #656d76; font-size: 14px;">
                        The installation has been automatically removed. You can install the app again following the single repository guidelines.
                    </p>
                </div>
            </body>
            </html>
            """
            
            return HTMLResponse(content=html_content, status_code=400)


        # Save each repository with installation_id and empty values for other fields
        for repo in repositories:
            repo_full_name = repo.get("full_name", "")
            if "/" in repo_full_name:
                git_username, repository_name = repo_full_name.split("/", 1)
                db_manager.save_repository_with_installation(git_username, repository_name, installation_id)
        
        # Generate repository form sections
        repo_forms = ""
        for repo in repositories:
            repo_full_name = repo.get("full_name", "")
            if "/" in repo_full_name:
                git_username, repository_name = repo_full_name.split("/", 1)
                repo_forms += f"""
                <div class="repo-section">
                    <h3>Repository: {repo_full_name}</h3>
                    <input type="hidden" name="git_username[]" value="{git_username}">
                    <input type="hidden" name="repository_name[]" value="{repository_name}">
                    
                    <div class="form-group">
                        <label>Git Username:</label>
                        <input type="text" value="{git_username}" readonly class="readonly-field">
                    </div>
                    
                    <div class="form-group">
                        <label>Git Repository:</label>
                        <input type="text" value="{repository_name}" readonly class="readonly-field">
                    </div>
                    
                    <div class="form-group">
                        <label for="email_{repository_name}">Insper E-mail:</label>
                        <input type="email" name="email[]" id="email_{repository_name}" 
                               pattern=".*@al\.insper\.edu\.br$" 
                               placeholder="your.name@al.insper.edu.br" required>
                        <small style="color: #656d76;">Must be an @al.insper.edu.br email</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="name_{repository_name}">Name:</label>
                        <input type="text" name="name[]" id="name_{repository_name}" 
                               placeholder="Your full name" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Course:</label>
                        <div class="radio-group">
                            <label class="radio-label">
                                <input type="radio" name="course_{repository_name}" value="CieComp" required>
                                CieComp
                            </label>
                            <label class="radio-label">
                                <input type="radio" name="course_{repository_name}" value="EngComp" required>
                                EngComp
                            </label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="language_{repository_name}">Language:</label>
                        <select name="language[]" id="language_{repository_name}" required>
                            <option value="Python" selected>Python</option>
                            <option value="JavaScript">JavaScript</option>
                            <option value="TypeScript">TypeScript</option>
                            <option value="C++">C++</option>
                            <option value="C#">C#</option>
                        </select>
                    </div>
                </div>
                """
        
    except Exception as e:
        logger.error(f"Error in setup: {e}")
        raise HTTPException(status_code=500, detail="Setup failed")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Compiler Tester - Setup</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f6f8fa;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
            }}
            h1 {{
                color: #24292e;
                margin-bottom: 20px;
            }}
            h3 {{
                color: #0366d6;
                margin-top: 30px;
                margin-bottom: 15px;
                padding-bottom: 8px;
                border-bottom: 2px solid #e1e4e8;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: 600;
                color: #24292e;
            }}
            input, select {{
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                font-size: 14px;
                box-sizing: border-box;
            }}
            .readonly-field {{
                background-color: #f6f8fa;
                color: #656d76;
            }}
            .radio-group {{
                display: flex;
                gap: 20px;
            }}
            .radio-label {{
                display: flex;
                align-items: center;
                gap: 5px;
                font-weight: normal;
            }}
            .radio-label input[type="radio"] {{
                width: auto;
                margin: 0;
            }}
            .checkbox-label {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: normal;
                cursor: pointer;
            }}
            .checkbox-label input[type="checkbox"] {{
                width: auto;
                margin: 0;
            }}
            .global-options {{
                background-color: #f0f8ff;
                border: 1px solid #b8daff;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}
            .submit-btn {{
                background-color: #2da44e;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                margin-top: 20px;
            }}
            .submit-btn:hover {{
                background-color: #2c974b;
            }}
            .repo-section {{
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                background-color: #fafbfc;
            }}
            small {{
                display: block;
                margin-top: 3px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 App Installed Successfully!</h1>
            <p>Please complete the setup for each repository:</p>
            
            <form action="/setup/save" method="post">
                <input type="hidden" name="installation_id" value="{installation_id}">
                
                <div class="global-options">
                    <h3>Global Options</h3>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" name="add_badges" value="true" checked>
                            Automatically add compilation status badges to README.md files
                        </label>
                        <small style="color: #656d76;">This will add a badge showing compilation status at the top of each repository's README.md</small>
                    </div>
                </div>
                
                {repo_forms}
                
                <button type="submit" class="submit-btn">Save All Repositories</button>
            </form>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

async def get_installation_details(installation_id: int) -> Dict[str, Any]:
    """
    Fetch installation details from GitHub API
    """
    try:
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
                        raise Exception("GitHub App needs a public key generated. Please check App settings in GitHub.")
                    elif "Bad credentials" in error_text:
                        raise Exception("Invalid JWT token or App ID. Please check private key format and App ID.")
                    else:
                        try:
                            error_data = response.json()
                            raise Exception(f"Authentication failed: {error_data.get('message', 'Unknown error')}")
                        except:
                            raise Exception(f"Authentication failed: {error_text}")
                elif response.status_code == 404:
                    raise Exception(f"Installation {installation_id} not found. App may not be installed.")
                else:
                    raise Exception(f"GitHub API error {response.status_code}: {response.text}")
                    
    except Exception as e:
        logger.error(f"Error getting installation access token: {e}")
        raise

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
        # Generate JWT token
        jwt_token = generate_jwt_token()
        
        # Get installation access token
        access_token = await get_installation_token(installation_id, jwt_token)
        
        # Create the issue
        async with httpx.AsyncClient() as client:
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

async def clone_repository(repo_full_name: str, installation_token: str, local_path: str = None) -> str:
    """Clone repository using installation token"""
    if local_path is None:
        local_path = f"/tmp/{repo_full_name.replace('/', '_')}"
    
    # Create clone URL with token
    clone_url = f"https://x-access-token:{installation_token}@github.com/{repo_full_name}.git"
    
    try:
        # Remove existing directory if it exists
        if os.path.exists(local_path):
            import shutil
            shutil.rmtree(local_path)
        
        # Clone the repository
        result = subprocess.run([
            "git", "clone", clone_url, local_path
        ], capture_output=True, text=True, check=True)
        
        logger.info(f"Successfully cloned {repo_full_name} to {local_path}")
        return local_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed for {repo_full_name}: {e.stderr}")
        raise Exception(f"Failed to clone repository: {e.stderr}")

async def checkout_tag(repo_path: str, tag_name: str) -> bool:
    """Checkout specific tag in cloned repository"""
    try:
        result = subprocess.run([
            "git", "checkout", f"tags/{tag_name}"
        ], cwd=repo_path, capture_output=True, text=True, check=True)
        
        logger.info(f"Successfully checked out tag {tag_name}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git checkout failed for tag {tag_name}: {e.stderr}")
        return False

async def run_compilation_test(repo_path: str, version_info: Dict[str, Any]) -> str:
    """Run compilation test on the repository"""
    try:
        # Get semester info for compilation details
        semester_name = version_info.get('semester_name')
        semester_info = db_manager.get_semester_info(semester_name)
        
        if not semester_info:
            return "ERROR"
        
        language = semester_info['language']
        extension = semester_info['extension']
        
        # Find source files
        source_files = []
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith(extension):
                    source_files.append(os.path.join(root, file))
        
        if not source_files:
            logger.warning(f"No {extension} files found in {repo_path}")
            return "ERROR"
        
        # Run compilation based on language
        if language.lower() == "java":
            # Compile Java files
            for source_file in source_files:
                result = subprocess.run([
                    "javac", source_file
                ], cwd=repo_path, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Java compilation failed: {result.stderr}")
                    return "FAILED"
        
        elif language.lower() == "c":
            # Compile C files
            for source_file in source_files:
                output_file = source_file.replace('.c', '')
                result = subprocess.run([
                    "gcc", source_file, "-o", output_file
                ], cwd=repo_path, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"C compilation failed: {result.stderr}")
                    return "FAILED"
        
        elif language.lower() == "python":
            # Check Python syntax
            for source_file in source_files:
                result = subprocess.run([
                    "python3", "-m", "py_compile", source_file
                ], cwd=repo_path, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Python syntax check failed: {result.stderr}")
                    return "FAILED"
        
        logger.info("Compilation test passed")
        return "PASS"
        
    except Exception as e:
        logger.error(f"Compilation test error: {e}")
        return "ERROR"

async def run_actual_compilation_test(git_username: str, repository_name: str, 
                                    tag_name: str, version_info: Dict[str, Any]) -> str:
    """
    Run actual compilation test by cloning repository and testing the specific tag
    """
    repo_full_name = f"{git_username}/{repository_name}"
    temp_dir = None
    
    try:
        # Get repository info which includes installation_id
        repo_info = db_manager.get_repository_info(git_username, repository_name)
        
        if not repo_info or not repo_info.get('installation_id'):
            logger.error(f"No installation_id found for repository {repo_full_name}")
            return "ERROR"
        
        installation_id = repo_info['installation_id']
        
        # Generate tokens
        jwt_token = generate_jwt_token()
        installation_token = await get_installation_token(installation_id, jwt_token)
        
        # Clone repository
        temp_dir = await clone_repository(repo_full_name, installation_token)
        
        # Checkout specific tag
        if not await checkout_tag(temp_dir, tag_name):
            return "ERROR"
        
        # Run compilation test
        result = await run_compilation_test(temp_dir, version_info)
        return result
        
    except Exception as e:
        logger.error(f"Error in compilation test for {repo_full_name}:{tag_name} - {e}")
        return "ERROR"
        
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

async def get_installation_id_for_repo(repo_full_name: str) -> Optional[int]:
    """
    Find installation ID for a given repository
    """
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT installation_id 
                FROM InstallationRepository 
                WHERE repository_full_name = ?
            """, (repo_full_name,))
            
            row = cursor.fetchone()
            return row[0] if row else None
            
    except Exception as e:
        logger.error(f"Error finding installation for repo {repo_full_name}: {e}")
        return None

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

@app.post("/setup/save")
async def save_setup(request: Request):
    """
    Save the setup information for all repositories
    """
    form_data = await request.form()
    installation_id = form_data.get("installation_id")
    
    # Get arrays of form data
    git_usernames = form_data.getlist("git_username[]")
    repository_names = form_data.getlist("repository_name[]") 
    emails = form_data.getlist("email[]")
    names = form_data.getlist("name[]")
    languages = form_data.getlist("language[]")
    
    logger.info(f"Saving setup for installation {installation_id}")
    
    try:
        # Get current semester from datetime
        def get_current_semester():
            month = datetime.now().month
            if month in [1, 2, 3, 4, 5, 6]:
                return "1"
            elif month in [7, 8, 9, 10, 11, 12]:
                return "2"
            else:
                return "unknown"
                
        current_semester = datetime.now().strftime("%Y") + '-' + get_current_semester()
        
        success_repos = []
        failed_repos = []
        
        for i in range(len(git_usernames)):
            git_username = git_usernames[i]
            repository_name = repository_names[i]
            email = emails[i]
            name = names[i]
            language = languages[i]
            
            # Get course from radio button (different name for each repo)
            course_key = f"course_{repository_name}"
            course = form_data.get(course_key)
            
            if not course:
                failed_repos.append(f"{git_username}/{repository_name} - Missing course")
                continue
            
            # Generate semester name based on course
            if course == "EngComp":
                semester_name = f"ENG-{current_semester}"
            elif course == "CieComp":
                semester_name = f"BCC-{current_semester}"
            else:
                failed_repos.append(f"{git_username}/{repository_name} - Invalid course")
                continue
            
            # Generate program_call based on language
            compiled = 0
            program_call_map = {
                "Python": "python3 main.py",
                "JavaScript": "node main.js", 
                "TypeScript": "node main.js",
                "C++": "g++ main.cpp -o main && ./main",
                "C#": "dotnet run main.csproj"
            }
            program_call = program_call_map.get(language, "")
            if language in ["Java", "C++", "C#"]:
                compiled = 1
            
            # Save/update user
            user_success = db_manager.save_or_update_user(git_username, name, email)
            
            # Update repository with complete details
            repo_success = db_manager.update_repository_details(
                git_username, repository_name, semester_name, program_call, language, compiled
            )
            
            if user_success and repo_success:
                success_repos.append(f"{git_username}/{repository_name}")
            else:
                failed_repos.append(f"{git_username}/{repository_name} - Database error")
        
        # Handle badge addition if requested
        add_badges = form_data.get("add_badges") == "true"
        badge_results = {}
        
        if add_badges and success_repos:
            logger.info("Adding badges to repositories...")
            
            try:
                # Get installation details to get repository list with permissions
                installation_data = await get_installation_details(installation_id)
                repositories = installation_data.get("repositories", [])
                
                # Filter to only successful repositories
                successful_repo_names = set(success_repos)
                repos_to_badge = [
                    repo for repo in repositories 
                    if repo.get("full_name") in successful_repo_names
                ]
                
                # Add badges
                base_url = os.getenv("BASE_URL")  # Replace with your actual domain
                badge_results = await add_badges_to_installation_repos(installation_id, repos_to_badge, base_url)
                
                # Update success/failed lists based on badge results
                for repo_name, badge_success in badge_results.items():
                    if not badge_success:
                        logger.warning(f"Failed to add badge to {repo_name}")
                        
            except Exception as e:
                logger.error(f"Error adding badges: {e}")
        
        # Generate success page
        if success_repos:
            success_list = "<br>".join([f"✅ {repo}" for repo in success_repos])
        else:
            success_list = "No repositories were successfully configured."
            
        if failed_repos:
            failure_list = "<br>".join([f"❌ {repo}" for repo in failed_repos])
        else:
            failure_list = ""
        
        # Generate badge status message
        badge_message = ""
        if add_badges:
            successful_badges = sum(1 for success in badge_results.values() if success)
            total_badges = len(badge_results)
            
            if total_badges > 0:
                badge_message = f"<br><br><strong>Badge Addition:</strong> {successful_badges}/{total_badges} badges added successfully"
                if successful_badges < total_badges:
                    failed_badge_repos = [repo for repo, success in badge_results.items() if not success]
                    badge_message += f"<br>Failed to add badges to: {', '.join(failed_badge_repos)}"
            else:
                badge_message = "<br><br><strong>Badge Addition:</strong> No badges were processed"
        
        success_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Setup Complete</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f6f8fa;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
                    text-align: center;
                }}
                .success {{
                    color: #2da44e;
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #24292e;
                    margin-bottom: 20px;
                }}
                .info {{
                    background-color: #f6f8fa;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .repo-link {{
                    display: inline-block;
                    margin: 10px;
                    padding: 8px 16px;
                    background-color: #0366d6;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-size: 14px;
                }}
                .repo-link:hover {{
                    background-color: #0256cc;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Setup Complete!</h1>
                <p>Your repositories have been configured for automatic compilation testing.</p>
                
                <div class="info">
                    <strong>Successfully Configured:</strong><br>
                    {success_list}
                    {f'<br><br><strong>Failed:</strong><br>{failure_list}' if failure_list else ''}
                    {badge_message}
                </div>
                
                <p><strong>Repository Links:</strong></p>
                <div>
                    {''.join([f'<a href="/svg/{repo.split("/")[0]}/{repo.split("/")[1]}" class="repo-link">{repo} Badge</a>' for repo in success_repos])}
                </div>
                
                <p><strong>Next Steps:</strong></p>
                <ul style="text-align: left;">
                    <li>Create tags in your repositories to trigger compilation tests</li>
                    <li>View build status using the badge links above</li>
                    <li>Check webhook events in your repository settings</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=success_html)
        
    except Exception as e:
        logger.error(f"Error saving setup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

@app.post("/setup/complete")
async def complete_setup(
    installation_id: int = Form(...),
    account_login: str = Form(...),
    account_type: str = Form(...),
    semester: str = Form(...),
    course: str = Form(...),
    description: str = Form("")
):
    """
    Complete the setup process by saving all information to database
    """
    logger.info(f"Completing setup for installation {installation_id}")
    
    try:
        # Get installation repositories from GitHub API
        installation_data = await get_installation_details(installation_id)
        repositories = installation_data.get("repositories", [])
        
        # Save installation to database
        success = db_manager.save_installation(
            installation_id=installation_id,
            account_type=account_type,
            account_login=account_login,
            semester_name=semester,
            course=course,
            description=description
        )
        
        if not success:
            raise Exception("Failed to save installation")
        
        # Process each repository
        repo_names = []
        for repo in repositories:
            repo_full_name = repo.get("full_name", "")
            if "/" in repo_full_name:
                git_username, repository_name = repo_full_name.split("/", 1)
                
                # Ensure user exists
                db_manager.ensure_user_exists(git_username)
                
                # Ensure repository exists
                db_manager.ensure_repository_exists(git_username, repository_name, semester)
                
                repo_names.append(repo_full_name)
        
        # Save repository associations
        if repo_names:
            db_manager.save_installation_repositories(installation_id, repo_names)
        
        logger.info(f"Setup completed successfully for installation {installation_id}")
        
        success_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Setup Complete</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f6f8fa;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 8px 24px rgba(140, 149, 159, 0.2);
                    text-align: center;
                }}
                .success {{
                    color: #2da44e;
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #24292e;
                    margin-bottom: 20px;
                }}
                .info {{
                    background-color: #f6f8fa;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .repo-list {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 6px;
                    text-align: left;
                    margin: 15px 0;
                }}
                .repo-item {{
                    padding: 5px 0;
                    font-family: monospace;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Setup Complete!</h1>
                <p>Your repositories are now configured for automatic compilation testing.</p>
                
                <div class="info">
                    <strong>Configuration:</strong><br>
                    Account: {account_login}<br>
                    Semester: {semester}<br>
                    Course: {course}<br>
                    {f'Description: {description}<br>' if description else ''}
                    Installation ID: {installation_id}
                </div>
                
                <div class="repo-list">
                    <strong>Configured Repositories:</strong><br>
                    {'<br>'.join([f'<div class="repo-item">• {repo}</div>' for repo in repo_names]) if repo_names else 'No repositories found'}
                </div>
                
                <p><strong>Next Steps:</strong></p>
                <ul style="text-align: left;">
                    <li>Create tags in your repositories to trigger compilation tests</li>
                    <li>View build status at <code>/svg/{{username}}/{{repo}}</code></li>
                    <li>Check webhook events in your repository settings</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=success_html)
        
    except Exception as e:
        logger.error(f"Error completing setup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

@app.get("/auth/callback")
async def auth_callback(code: str = None, state: str = None, error: str = None):
    """
    Handle GitHub OAuth callback
    """
    if error:
        return {"error": error, "message": "Authentication failed"}
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    # Here you would exchange the code for an access token
    # This is a simplified example - in production, you'd want to:
    # 1. Exchange the code for an access token
    # 2. Get user information
    # 3. Store the token securely
    # 4. Create a session or JWT
    
    logger.info(f"Received auth callback with code: {code[:10]}...")
    
    return {
        "message": "Authentication successful",
        "next_steps": "Token exchange and user session creation would happen here"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)
