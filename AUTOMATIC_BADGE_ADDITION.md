# Automatic Badge Addition Feature

## Overview

The Compiler Tester GitHub App can automatically add compilation status badges to your repository's README.md file when the app is installed and configured.

## How It Works

### 1. During Installation Setup

When you install the GitHub App and complete the setup form, you'll see an option:

```
☑️ Automatically add compilation status badges to README.md files
```

This option is **checked by default**.

### 2. Badge Format

The badge that gets added looks like this:

```markdown
[![Compilation Status](https://yourdomain.com/svg/username/repository)](https://yourdomain.com/svg/username/repository)
```

Which renders as: ![Compilation Status](https://img.shields.io/badge/status-example-blue)

### 3. README.md Placement

The badge is intelligently placed in your README.md:

- **If README.md exists**: The badge is added after the main title
- **If README.md doesn't exist**: A new README.md is created with the badge
- **If badge already exists**: No duplicate badge is added

Example placement:

```markdown
# My Project

[![Compilation Status](https://yourdomain.com/svg/username/repository)](https://yourdomain.com/svg/username/repository)

This is my project description...
```

## Badge Status Indicators

The badge shows real-time compilation status:

- 🟢 **PASS** - All tests compiled successfully
- 🔴 **FAILED** - Compilation errors found  
- ⚫ **ERROR** - System error during testing
- ⚪ **NOT_FOUND** - No tests found for this version
- 🟡 **ON_TIME** - Submitted on time
- 🟠 **DELAYED** - Submitted after deadline

## Requirements

For automatic badge addition to work, your GitHub App needs:

### 1. Repository Permissions

- **Contents: Write** - Required to modify README.md files
- **Metadata: Read** - Required to access repository information

### 2. Repository Access

The app must be installed with access to the repositories where you want badges added.

## Manual Badge Addition

If you opted out of automatic badge addition during setup, you can manually add the badge to any repository:

```markdown
[![Compilation Status](https://yourdomain.com/svg/YOUR_USERNAME/YOUR_REPOSITORY)](https://yourdomain.com/svg/YOUR_USERNAME/YOUR_REPOSITORY)
```

Replace:
- `yourdomain.com` with your actual domain
- `YOUR_USERNAME` with your GitHub username  
- `YOUR_REPOSITORY` with your repository name

## Customization Options

### Badge URL Customization

You can customize the badge URL by modifying the `base_url` parameter in the `add_badges_to_installation_repos` function:

```python
base_url = "https://your-custom-domain.com"
```

### Badge Text Customization

To customize the badge text, modify the `badge_markdown` in the `add_badge_to_readme` function:

```python
badge_markdown = f"[![Custom Text]({badge_url})]({badge_url})"
```

### Commit Message Customization

The commit message when adding badges can be customized:

```python
update_data = {
    "message": "Add compilation status badge",  # Customize this
    "committer": {
        "name": "Compiler Tester Bot",         # Customize this
        "email": "compiler-tester@insper.edu.br"  # Customize this
    }
}
```

## Troubleshooting

### Badge Not Added

**Possible causes:**

1. **Missing permissions**: App doesn't have Contents write permission
2. **Repository protection**: Branch protection rules prevent commits
3. **Large README**: README.md is too large (GitHub API limit: 1MB)
4. **Network issues**: Temporary connectivity problems

**Check the logs for:**
```
Failed to add badge to username/repository: [error details]
```

### Badge Not Updating

**Possible causes:**

1. **Webhook not configured**: Tag events not reaching your server
2. **Database issues**: Repository not properly registered
3. **Test failures**: Compilation tests not running
4. **Cache issues**: Browser or CDN caching old badge

**Solutions:**

1. Check webhook delivery in GitHub App settings
2. Verify repository exists in database
3. Create a new tag to trigger tests
4. Add cache-busting parameters to badge URL

### Duplicate Badges

The system prevents duplicate badges by checking if the badge URL already exists in the README. If you see duplicates:

1. Manually remove extra badges from README.md
2. The system will detect the existing badge on future updates

## API Reference

### Badge Endpoint

```
GET /svg/{username}/{repository}
```

**Parameters:**
- `username`: GitHub username
- `repository`: Repository name

**Response:**
- Content-Type: `image/svg+xml`
- SVG badge image

**Example:**
```
GET /svg/johndoe/my-project
```

### Cache Headers

The badge endpoint includes cache control headers:

```http
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
ETag: [computed-hash]
```

This ensures badges always show current status.

## Security Considerations

### Webhook Verification

For production deployments, implement webhook signature verification:

```python
def verify_webhook_signature(payload_body, signature, secret):
    """Verify webhook signature from GitHub"""
    if not signature:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(secret.encode(), payload_body, hashlib.sha256)
    expected_signature = mac.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)
```

### Token Security

- Installation tokens are temporary (1 hour expiry)
- JWT tokens are short-lived (10 minutes)
- Private keys should be stored securely
- Never commit tokens to version control

## Best Practices

### 1. README Structure

Maintain clean README structure:

```markdown
# Project Title

[![Compilation Status](badge-url)](badge-url)

## Description
...
```

### 2. Badge Placement

- Place badges near the top for visibility
- Group multiple badges together
- Ensure badges don't break on mobile

### 3. Fallback Handling

Always provide meaningful fallback content if badges fail to load:

```markdown
[![Compilation Status](badge-url "Compilation Status")](badge-url)
```

The alt text "Compilation Status" will show if the image fails to load.

## Monitoring

Monitor badge addition success rates:

```python
# In your logs, track:
logger.info(f"Badge addition results: {successful_badges}/{total_badges} successful")

# Track failure reasons:
logger.error(f"Badge addition failed for {repo_name}: {error_details}")
```

Set up alerts for:
- High badge addition failure rates
- Repeated permission errors
- API rate limit issues

## Future Enhancements

Potential improvements:

1. **Custom badge styles**: Allow users to choose badge colors/styles
2. **Multiple badge types**: Add badges for different metrics
3. **Badge positioning**: Let users choose where badges are placed
4. **Branch-specific badges**: Different badges for different branches
5. **Badge analytics**: Track badge view statistics
