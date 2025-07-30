# GitHub App Setup Guide

This guide will help you set up a GitHub App for the Compiler Tester application.

## Step 1: Create a GitHub App

1. Go to [GitHub Developer Settings](https://github.com/settings/apps)
2. Click "New GitHub App"
3. Fill in the required information:

### Basic Information
- **GitHub App name**: `compiler-tester` (or your preferred name)
- **Description**: `Academic compiler testing platform for Insper courses`
- **Homepage URL**: `https://yourdomain.com` (replace with your actual domain)

### Setup URL (Important!)
- **Setup URL**: `https://yourdomain.com/setup`
- ✅ Check "Request user authorization (OAuth) during installation"

### Webhook (Optional for now)
- **Webhook URL**: `https://yourdomain.com/webhook` (optional)
- **Webhook secret**: Leave empty for now

### Repository Permissions
Set these permissions for your app:
- **Contents**: Read (to clone repositories)
- **Metadata**: Read (to access repository information)
- **Pull requests**: Read (optional, for future features)

### User Permissions
- **Email addresses**: Read (to get user email for academic validation)

### Subscribe to Events (Optional)
You can enable these later:
- Installation
- Installation repositories

## Step 2: Configure App Settings

After creating the app:

1. **Note your App ID** - you'll need this in your code
2. **Generate a private key**:
   - Scroll down to "Private keys" section
   - Click "Generate a private key"
   - Download the `.pem` file
3. **Generate a public key** (Important!):
   - In the same "Private keys" section
   - Click "Generate a public key" 
   - This step is crucial - without it you'll get "Integration must generate a public key" errors

## Step 3: Configure Your Application

### Update main.py

Replace these values in your `main.py`:

```python
# GitHub App configuration
GITHUB_APP_ID = "123456"  # Replace with your actual App ID
GITHUB_APP_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
...your actual private key content...
-----END PRIVATE KEY-----"""
```

### Private Key Format

The private key must:
- Include the `-----BEGIN PRIVATE KEY-----` header
- Include the `-----END PRIVATE KEY-----` footer  
- Use actual newlines (not `\n` characters)
- Be the complete key from the downloaded `.pem` file

### Common Issues and Solutions

#### Error: "Integration must generate a public key"
**Solution**: Go to your GitHub App settings and click "Generate a public key" in the Private keys section.

#### Error: "Bad credentials"
**Solution**: Check that your App ID and private key are correct. Make sure the private key format is exactly as shown above.

#### Error: "Not Found"
**Solution**: Make sure your App ID is correct and the app exists.

## Step 4: Test Your Configuration

Run the test script to verify everything is working:

```bash
python test_github_auth.py
```

This will test:
- Private key format
- JWT token generation
- GitHub API connectivity
- App authentication

## Step 5: Install Your App

1. Go to your app's page: `https://github.com/apps/YOUR_APP_NAME`
2. Click "Install"
3. Choose which repositories to give access to
4. The installation will redirect to your Setup URL with parameters:
   - `installation_id`: Unique ID for this installation
   - `setup_action`: Usually "install"

## Step 6: Test the Flow

1. Install your app on a test repository
2. You should be redirected to: `https://yourdomain.com/setup?installation_id=12345&setup_action=install`
3. Fill out the academic form
4. Check that the repository is saved in your database

## Troubleshooting

### Common HTTP Status Codes

- **401 Unauthorized**: Usually app configuration issues (App ID, private key, or missing public key)
- **403 Forbidden**: Insufficient permissions 
- **404 Not Found**: Wrong App ID or installation ID
- **422 Unprocessable Entity**: Invalid data format

### Debug Mode

Enable debug logging in your application to see detailed API responses:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test API Calls

You can test API calls manually:

```bash
# Generate JWT token (use your app)
# Then test getting installation details:
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/app/installations/INSTALLATION_ID
```

## Security Notes

- Never commit your private key to version control
- Use environment variables in production:
  ```python
  GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
  GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
  ```
- Regenerate keys if compromised
- Use HTTPS for all URLs

## Next Steps

Once your GitHub App is working:

1. Deploy your application to a server with HTTPS
2. Update the URLs in your GitHub App settings
3. Test the complete flow with real users
4. Add webhook handling for installation events
5. Implement repository cloning and analysis features
