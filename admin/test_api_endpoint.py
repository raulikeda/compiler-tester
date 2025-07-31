#!/usr/bin/env python3
"""
Test script for the /api/test-result endpoint

This script demonstrates how to properly use the API endpoint and 
shows what causes 422 validation errors.

Usage: python test_api_endpoint.py
"""

import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# API configuration
API_SECRET = os.getenv("API_SECRET", "your-default-secret-change-me")
BASE_URL = "http://localhost:8000"  # Change to your API URL

def test_valid_request():
    """Test a valid request that should work"""
    print("Testing VALID request...")
    
    headers = {
        "X-API-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    
    data = {
        "version_name": "v1.0",
        "release_name": "v1.0.0",
        "git_username": "testuser",
        "repository_name": "test-repo",
        "test_status": "PASS",
        "issue_text": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/test-result", json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_invalid_test_status():
    """Test with invalid test_status - should cause 422"""
    print("Testing INVALID test_status (should cause 422)...")
    
    headers = {
        "X-API-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    
    data = {
        "version_name": "v1.0",
        "release_name": "v1.0.0",
        "git_username": "testuser",
        "repository_name": "test-repo",
        "test_status": "INVALID_STATUS",  # This will cause 422
        "issue_text": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/test-result", json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_missing_required_field():
    """Test with missing required field - should cause 422"""
    print("Testing MISSING required field (should cause 422)...")
    
    headers = {
        "X-API-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    
    data = {
        "version_name": "v1.0",
        "release_name": "v1.0.0",
        "git_username": "testuser",
        # Missing repository_name - this will cause 422
        "test_status": "PASS",
        "issue_text": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/test-result", json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_wrong_data_type():
    """Test with wrong data type - should cause 422"""
    print("Testing WRONG data type (should cause 422)...")
    
    headers = {
        "X-API-Secret": API_SECRET,
        "Content-Type": "application/json"
    }
    
    data = {
        "version_name": 123,  # Should be string, not number - this will cause 422
        "release_name": "v1.0.0",
        "git_username": "testuser",
        "repository_name": "test-repo",
        "test_status": "PASS",
        "issue_text": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/test-result", json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def test_missing_api_secret():
    """Test with missing API secret - should cause 401"""
    print("Testing MISSING API secret (should cause 401)...")
    
    headers = {
        # Missing X-API-Secret header
        "Content-Type": "application/json"
    }
    
    data = {
        "version_name": "v1.0",
        "release_name": "v1.0.0",
        "git_username": "testuser",
        "repository_name": "test-repo",
        "test_status": "PASS",
        "issue_text": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/test-result", json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()

def print_usage_info():
    """Print information about the API endpoint"""
    print("=" * 60)
    print("API Endpoint Usage Information")
    print("=" * 60)
    print()
    print("Endpoint: POST /api/test-result")
    print()
    print("Required Headers:")
    print("  X-API-Secret: <your-api-secret>")
    print("  Content-Type: application/json")
    print()
    print("Required JSON Fields:")
    print("  version_name: string (e.g., 'v1.0')")
    print("  release_name: string (e.g., 'v1.0.0')")
    print("  git_username: string (e.g., 'johndoe')")
    print("  repository_name: string (e.g., 'my-repo')")
    print("  test_status: string (must be 'PASS', 'ERROR', or 'FAILED')")
    print()
    print("Optional JSON Fields:")
    print("  issue_text: string or null (error description for failed tests)")
    print()
    print("Common HTTP Status Codes:")
    print("  200 - Success")
    print("  401 - Unauthorized (invalid or missing API secret)")
    print("  404 - Repository not found in database")
    print("  422 - Unprocessable Entity (validation error)")
    print("  500 - Internal server error")
    print()
    print("422 Validation Errors occur when:")
    print("  - test_status is not 'PASS', 'ERROR', or 'FAILED'")
    print("  - Required fields are missing")
    print("  - Field data types are incorrect (e.g., number instead of string)")
    print("  - Field values are empty when they shouldn't be")
    print()
    print("=" * 60)

def main():
    """Run all tests"""
    print_usage_info()
    
    print("Running API endpoint tests...")
    print(f"API Secret: {API_SECRET}")
    print(f"Base URL: {BASE_URL}")
    print()
    
    # Note: These tests will likely fail because the repository doesn't exist
    # but they demonstrate the validation behavior
    
    test_valid_request()
    test_invalid_test_status()
    test_missing_required_field()
    test_wrong_data_type()
    test_missing_api_secret()
    
    print("=" * 60)
    print("Test Summary:")
    print("- The first test might fail with 404 (repository not found)")
    print("- Tests 2-4 should fail with 422 (validation errors)")
    print("- Test 5 should fail with 401 (missing API secret)")
    print("=" * 60)

if __name__ == "__main__":
    main()
