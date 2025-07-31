#!/usr/bin/env python3
"""
Simple test to debug the 422 error on /api/test-result endpoint
"""

import requests
import json
from dotenv import load_dotenv

load_dotenv()

# API configuration
API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")

# Test with a simple request
url = "http://3.129.230.99/api/test-result"  # Using your actual IP
headers = {
    "X-API-Secret": API_SECRET,  # Actual secret from .env
    "Content-Type": "application/json"
}

data = {
    "version_name": "v1.0",
    "release_name": "v1.0.0", 
    "git_username": "testuser",
    "repository_name": "test-repo",
    "test_status": "PASS",
    "issue_text": "abcd"  # Uncomment to test with issue_text
}

print("Testing /api/test-result endpoint...")
print(f"URL: {url}")
print(f"Headers: {headers}")
print(f"Data: {json.dumps(data, indent=2)}")
print()

try:
    response = requests.post(url, json=data, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 422:
        try:
            error_detail = response.json()
            print("\nDetailed Error Information:")
            print(json.dumps(error_detail, indent=2))
        except:
            print("Could not parse error response as JSON")
            
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
