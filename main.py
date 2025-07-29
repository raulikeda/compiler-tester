from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import logging
from typing import Dict, Any
from db.database import db_manager
import generate_badge as sr
import time
import hashlib

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
                        # Here you would run your actual compilation tests
                        # For now, we'll simulate the test result
                        test_status = "PASS"  # This should be the actual test result
                        
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
                            # Here you would run your actual compilation tests
                            test_status = "PASS"  # This should be the actual test result
                            
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
    redirect_uri = "http://localhost:8000/auth/callback"  # Replace with your callback URL
    
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
