"""
Setup operations module for GitHub App installation setup
"""

import os
import logging
from datetime import datetime
from fastapi import HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from github_api import get_installation_details
from badge_ops import add_badges_to_installation_repos
from db.database import db_manager

logger = logging.getLogger(__name__)


def get_current_semester() -> str:
    """Get current semester based on current month"""
    month = datetime.now().month
    if month in [1, 2, 3, 4, 5, 6]:
        return "1"
    elif month in [7, 8, 9, 10, 11, 12]:
        return "2"
    else:
        return "unknown"


async def process_setup_save(request: Request):
    """
    Process the setup form submission and save repository configurations
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
                base_url = os.getenv("BASE_URL")
                badge_results = await add_badges_to_installation_repos(installation_id, repos_to_badge, base_url)
                
                # Update success/failed lists based on badge results
                for repo_name, badge_success in badge_results.items():
                    if not badge_success:
                        logger.warning(f"Failed to add badge to {repo_name}")
                        
            except Exception as e:
                logger.error(f"Error adding badges: {e}")
        
        return generate_setup_success_page(
            success_repos, failed_repos, badge_results, add_badges
        )
        
    except Exception as e:
        logger.error(f"Error saving setup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")


def generate_setup_success_page(
    success_repos: list, 
    failed_repos: list, 
    badge_results: dict, 
    add_badges: bool
) -> HTMLResponse:
    """Generate HTML success page for setup completion"""
    
    # Generate success list
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
                {''.join([f'<a href="https://github.com/{repo.split("/")[0]}/{repo.split("/")[1]}" class="repo-link">{repo}</a>' for repo in success_repos])}
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
