from fastapi import FastAPI, Request, HTTPException, Form, Depends, Header
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel, Field, field_validator
import json
import logging
from typing import Dict, Any, List, Optional, Annotated
from db.database import db_manager
import generate_badge as sr
import time
import hashlib
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv
from github_api import generate_jwt_token, get_installation_token, get_installation_details, create_github_issue
from docker_ops import run_docker_container_async
from webhook_handler import process_webhook_payload
from badge_ops import add_badge_to_readme, add_badges_to_installation_repos
from setup_ops import process_setup_save

load_dotenv()

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

app = FastAPI(
    title="Compiler Tester API",
    description="API for handling GitHub webhooks, badges, and authentication",
    version="1.0.0"
)

# Pydantic models for API endpoints
class TestResultData(BaseModel):
    version_name: str = Field(..., description="Version name for the test")
    release_name: str = Field(..., description="Release/tag name")
    git_username: str = Field(..., description="GitHub username")
    repository_name: str = Field(..., description="Repository name")
    test_status: str = Field(..., description="Test status: PASS, ERROR, or FAILED")
    issue_text: Optional[str] = Field(None, description="Optional issue description for failed tests")
    
    @field_validator('test_status')
    @classmethod
    def validate_test_status(cls, v):
        if v not in ['PASS', 'ERROR', 'FAILED']:
            raise ValueError('test_status must be one of: PASS, ERROR, FAILED')
        return v

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
        
        # Process the webhook using our modular handler
        return await process_webhook_payload(event_type, payload)
        
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
    redirect_uri = "https://compiler-tester.insper-comp.com.br/auth/callback"  # Replace with your callback URL
    
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
                               pattern=".*@al[.]insper[.]edu[.]br$" 
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
                            <option value="OCaml">OCaml</option>
                            <option value="Kotlin">Kotlin</option>
                            <option value="Go">Go</option>
                            <option value="C#">C#</option>
                            <option value="PHP">PHP</option>
                            <option value="Swift">Swift</option>
                            <option value="Rust">Rust</option>
                            <option value="Zig">Zig</option>
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

@app.post("/setup/save")
async def save_setup(request: Request):
    """
    Save the setup information for all repositories
    """
    return await process_setup_save(request)

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
    uvicorn.run("main:app", host="0.0.0.0", port=443, reload=True,
    ssl_certfile="/etc/letsencrypt/live/compiler-tester.insper-comp.com.br/fullchain.pem",
    ssl_keyfile="/etc/letsencrypt/live/compiler-tester.insper-comp.com.br/privkey.pem"
    )
