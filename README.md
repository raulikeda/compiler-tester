# Compiler Tester

A FastAPI-based service for testing compilation on GitHub repositories with webhook integration, badge generation, and GitHub App authentication.

## Features

- **GitHub Webhook Integration**: Automatically triggered on tag creation events
- **Build Status Badges**: SVG badges showing compilation status for repositories
- **GitHub App Authentication**: Secure login and authorization flow
- **REST API**: Clean API endpoints for webhook handling and badge generation

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
# Option 1: Using Python directly
python main.py

# Option 2: Using uvicorn directly (recommended for development)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

## API Endpoints

### POST /webhook
Handles GitHub webhook events, specifically tag creation events.

**Headers:**
- `X-GitHub-Event`: The type of GitHub event

**Example tag event payload:**
```json
{
  "ref": "v1.0.0",
  "ref_type": "tag",
  "repository": {
    "full_name": "user/repo"
  }
}
```

### GET /badge/{user}/{repo}
Returns an SVG badge showing the compilation status for the specified repository.

**Example:**
```
GET /badge/raulikeda/compiler-tester
```

Returns an SVG badge with compilation status (passing, failing, or unknown).

### GET /login
GitHub App login landing page with OAuth integration.

## Configuration

Before using the GitHub App integration, update the following in `main.py`:

- `github_app_client_id`: Your GitHub App's client ID
- `redirect_uri`: Your OAuth callback URL
- Implement token exchange logic in `/auth/callback`

## Development

The server runs with auto-reload enabled for development. Any changes to the code will automatically restart the server.