# Admin Scripts

This directory contains testing, debugging, and administrative scripts that are not part of the main application but are useful for development and maintenance.

## Scripts

### Testing Scripts
- **`test_api_endpoint.py`** - Test the `/api/test-result` endpoint with various payloads
- **`test_github_auth.py`** - Test GitHub App authentication and token generation
- **`test_issue_creation.py`** - Debug GitHub issue creation with hardcoded repository data
- **`debug_422.py`** - Debug HTTP 422 validation errors

### Administrative Scripts
- **`get_installation_tokens.py`** - Generate and print access tokens for all GitHub App installations
- **`remove_installation.py`** - Remove a GitHub App installation using an access token

## Usage

These scripts are designed to be run from the root directory of the project:

```bash
# From the project root
cd /path/to/compiler-tester
python admin/test_api_endpoint.py
python admin/get_installation_tokens.py
```

## Environment

Make sure you have the `.env` file configured with the necessary environment variables before running these scripts:

- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`
- `API_SECRET`

## Notes

- These scripts are for development and administrative purposes only
- They should not be deployed to production environments
- Some scripts may require additional dependencies or manual configuration
