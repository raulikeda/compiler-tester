# GitHub App Webhook Configuration for Uninstall Events

## Step 1: Configure Webhook URL in GitHub App Settings

1. Go to your GitHub App settings: `https://github.com/settings/apps/YOUR_APP_NAME`
2. In the "Webhook" section:
   - **Webhook URL**: `https://yourdomain.com/webhook`
   - **Webhook secret**: (optional, but recommended for security)
3. Make sure "Active" is checked

## Step 2: Subscribe to Installation Events

In the "Subscribe to events" section, check these boxes:
- ✅ **Installation** - This will send events when the app is installed/uninstalled
- ✅ **Installation repositories** - This will send events when repositories are added/removed from existing installations

## Step 3: Test the Webhook

### Testing Uninstall Event

1. Install your app on a test repository
2. Complete the setup form (this adds data to your database)
3. Go to the repository settings → Applications → Installed GitHub Apps
4. Click "Uninstall" next to your app
5. Check your server logs - you should see:
   ```
   Installation event: deleted for installation 12345 (account: username)
   Successfully cleaned up data for uninstalled app (installation 12345)
   ```

### Testing Repository Removal

1. Install your app on multiple repositories
2. Go to GitHub App settings and remove some repositories from the installation
3. This triggers an "installation_repositories" event with action "removed"

## Webhook Event Examples

### App Uninstallation Event
```json
{
  "action": "deleted",
  "installation": {
    "id": 12345,
    "account": {
      "login": "username",
      "type": "User"
    }
  }
}
```

### Repository Removal Event
```json
{
  "action": "removed", 
  "installation": {
    "id": 12345
  },
  "repositories_removed": [
    {
      "full_name": "username/repo1"
    }
  ]
}
```

## Database Cleanup Process

When an uninstall event is received, the system will:

1. **Find all repositories** associated with the installation_id
2. **Remove test results** for those repositories (to avoid foreign key constraints)
3. **Remove the repositories** from the Repository table
4. **Remove orphaned users** who no longer have any repositories
5. **Log the cleanup** for debugging purposes

## Security Considerations

### Webhook Secret (Recommended)

Add a webhook secret to verify requests are from GitHub:

```python
import hmac
import hashlib

def verify_webhook_signature(payload_body, signature, secret):
    """Verify webhook signature from GitHub"""
    if not signature:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    # Create hash using secret
    mac = hmac.new(secret.encode(), payload_body, hashlib.sha256)
    expected_signature = mac.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# In your webhook handler:
@app.post("/webhook")
async def webhook(request: Request):
    payload_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    
    if not verify_webhook_signature(payload_body, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Continue with webhook processing...
```

### Rate Limiting

GitHub may send multiple webhook events. Consider implementing rate limiting or deduplication if needed.

## Monitoring

Add monitoring to track:
- Successful uninstalls
- Failed cleanup operations
- Orphaned data

```python
# In your webhook handler, add metrics/logging:
logger.info(f"Webhook event: {event_type}, action: {action}")
logger.info(f"Removed {len(removed_repos)} repositories")
logger.info(f"Cleaned up {orphaned_users} orphaned users")
```

## Testing Checklist

- [ ] App installation creates repository records
- [ ] Setup form populates user and repository details
- [ ] App uninstallation removes all related data
- [ ] Repository removal from installation removes specific repositories
- [ ] Orphaned users are cleaned up
- [ ] Webhook logs show successful processing
- [ ] No foreign key constraint errors
- [ ] Badge generation handles missing repositories gracefully
