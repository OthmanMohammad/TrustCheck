# Save as test_debug.py
import requests

base_url = "http://localhost:8000"

# Test each failing endpoint
endpoints = [
    ("GET", "/api/v1/entities/search?name=John"),
    ("GET", "/api/v1/changes?days=7"),
    ("GET", "/api/v1/changes/critical?hours=24"),
    ("GET", "/api/v1/statistics"),
    ("GET", "/api/v1/scraping/status?hours=24"),
]

for method, path in endpoints:
    url = f"{base_url}{path}"
    try:
        response = requests.request(method, url)
        print(f"\n{path}")
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text[:200]}")
    except Exception as e:
        print(f"\n{path}")
        print(f"Failed: {e}")