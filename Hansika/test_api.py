"""
test_api.py
A simple script to automatically test the core MongoDB API endpoints.
Run this while your server is running on port 5001.
"""

import requests
import json
import uuid

BASE_URL = "http://127.0.0.1:5001/api"
test_id = str(uuid.uuid4())[:8]

username = f"teacher_{test_id}"
email = f"teacher_{test_id}@test.com"
password = "password123"

def print_result(name, res):
    if res.status_code in [200, 201]:
        print(f"✅ {name} - SUCCESS")
    else:
        print(f"❌ {name} - FAILED ({res.status_code})")
        print(res.text)

print(f"Starting API Tests against {BASE_URL}...\n")

# 1. Test Registration
print("1. Testing Registration...")
res = requests.post(f"{BASE_URL}/auth/register", json={
    "username": username,
    "email": email,
    "password": password,
    "full_name": "Test Teacher"
})
print_result("Register User", res)

# 2. Test Login
print("\n2. Testing Login...")
res = requests.post(f"{BASE_URL}/auth/login", json={
    "username": username,
    "password": password
})
print_result("Login User", res)

token = None
if res.status_code == 200:
    token = res.json().get("data", {}).get("token")

if not token:
    print("Stopping tests: Could not retrieve JWT Token.")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# 3. Test Profile
print("\n3. Testing Protected Route (Profile)...")
res = requests.get(f"{BASE_URL}/auth/profile", headers=headers)
print_result("Get Profile", res)

# 4. Test Dashboard Analytics
print("\n4. Testing Dashboard Analytics...")
res = requests.get(f"{BASE_URL}/analytics/dashboard", headers=headers)
print_result("Get Dashboard", res)

# 5. Test Creating an Assignment
print("\n5. Testing Assignment Creation...")
res = requests.post(f"{BASE_URL}/assignments/create", headers=headers, json={
    "title": "Test Assignment",
    "sign_labels": ["hello", "thank you"],
    "description": "Just testing the API."
})
print_result("Create Assignment", res)

# 6. Test Ingesting Student Recording
print("\n6. Testing Student Recording Ingestion...")
res = requests.post(f"{BASE_URL}/annotations/recordings/ingest", headers=headers, json={
    "student_id": "student_001",
    "sign_label": "hello",
    "confidence": 85.5
})
print_result("Ingest Recording", res)

print("\n🎉 Basic API Workflow Test Complete!")
