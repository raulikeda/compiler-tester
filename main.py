from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import logging
from typing import Dict, Any, List
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

# GitHub App configuration (set these as environment variables in production)
GITHUB_APP_ID = "1578480"  # Your GitHub App ID
with open("id_rsa", "r") as f:
    GITHUB_APP_PRIVATE_KEY = f.read()

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
    
    payload = {
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=10),
        'iss': GITHUB_APP_ID
    }
    
    return jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm='RS256')

async def get_installation_token(installation_id: int, jwt_token: str) -> str:
    """Get installation access token"""
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
            return data["token"]
        else:
            raise Exception(f"Failed to get installation token: {response.text}")

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
        # Get current semester (you may want to make this configurable)
        current_semester = "2025-1"  # This should be dynamic based on your needs
        
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
            program_call_map = {
                "Python": "python3",
                "JavaScript": "node", 
                "TypeScript": "node",
                "C++": "g++",
                "C#": "dotnet"
            }
            program_call = program_call_map.get(language, "")
            
            # Save/update user
            user_success = db_manager.save_or_update_user(git_username, name, email)
            
            # Update repository with complete details
            repo_success = db_manager.update_repository_details(
                git_username, repository_name, semester_name, program_call
            )
            
            if user_success and repo_success:
                success_repos.append(f"{git_username}/{repository_name}")
            else:
                failed_repos.append(f"{git_username}/{repository_name} - Database error")
        
        # Generate success page
        if success_repos:
            success_list = "<br>".join([f"✅ {repo}" for repo in success_repos])
        else:
            success_list = "No repositories were successfully configured."
            
        if failed_repos:
            failure_list = "<br>".join([f"❌ {repo}" for repo in failed_repos])
        else:
            failure_list = ""
        
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
