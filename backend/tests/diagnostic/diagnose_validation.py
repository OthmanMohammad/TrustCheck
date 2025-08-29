# diagnose_validation.py
import requests

# Test specific failing endpoints and print full error
response = requests.get("http://localhost:8000/api/v2/entities?limit=5")
print("Entity endpoint response:")
print(f"Status: {response.status_code}")
print(f"Body: {response.text}\n")

# Test validation that should fail
response = requests.get("http://localhost:8000/api/v2/entities?limit=5000")
print("Validation test response:")
print(f"Status: {response.status_code}")
print(f"Body: {response.text}")