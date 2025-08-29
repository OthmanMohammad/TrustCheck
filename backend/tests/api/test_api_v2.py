"""
API v2 Tests - With DTO Validation

Test the production API with proper validation.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json

from src.main_v2 import app
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel

client = TestClient(app)

# ======================== ENTITY ENDPOINT TESTS ========================

def test_list_entities_with_validation():
    """Test entity listing with DTO validation."""
    response = client.get("/api/v2/entities?limit=10&offset=0")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    assert "data" in data
    assert "pagination" in data
    assert "metadata" in data
    
    # Validate pagination structure
    pagination = data["pagination"]
    assert "limit" in pagination
    assert "offset" in pagination
    assert "has_more" in pagination

def test_list_entities_invalid_params():
    """Test validation rejects invalid parameters."""
    # Invalid limit (too high)
    response = client.get("/api/v2/entities?limit=5000")
    assert response.status_code == 422  # Validation error
    
    # Invalid offset (negative)
    response = client.get("/api/v2/entities?offset=-1")
    assert response.status_code == 422
    
    # Invalid enum value
    response = client.get("/api/v2/entities?source=INVALID_SOURCE")
    assert response.status_code == 422

def test_search_entities_validation():
    """Test entity search with validation."""
    response = client.get("/api/v2/entities/search?query=test&fuzzy=true")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    assert "query" in data
    assert data["fuzzy_matching"] == True

def test_search_entities_query_too_short():
    """Test search query minimum length validation."""
    response = client.get("/api/v2/entities/search?query=a")
    assert response.status_code == 422
    
    errors = response.json()
    # Should contain validation error about query length

# ======================== CHANGE DETECTION TESTS ========================

def test_list_changes_with_dto():
    """Test change listing with proper DTO response."""
    response = client.get("/api/v2/changes?days=7")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    assert "summary" in data
    assert "filters" in data
    
    # Validate summary structure
    if data.get("summary"):
        summary = data["summary"]
        assert "period" in summary
        assert "totals" in summary
        assert "by_type" in summary
        assert "by_risk_level" in summary

def test_critical_changes_validation():
    """Test critical changes endpoint with validation."""
    response = client.get("/api/v2/changes/critical?hours=24")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    assert "count" in data
    assert "period" in data
    
    # Validate period structure
    period = data["period"]
    assert "hours" in period
    assert "since" in period
    assert "until" in period

def test_invalid_lookback_period():
    """Test validation of time period constraints."""
    # Too many hours (>168)
    response = client.get("/api/v2/changes/critical?hours=200")
    assert response.status_code == 422
    
    # Negative hours
    response = client.get("/api/v2/changes/critical?hours=-1")
    assert response.status_code == 422

# ======================== SCRAPER RUN TESTS ========================

def test_start_scraper_run():
    """Test starting scraper with request validation."""
    request_data = {
        "source": "OFAC",
        "force_update": False,
        "timeout_seconds": 120
    }
    
    response = client.post("/api/v2/scraping/run", json=request_data)
    assert response.status_code == 202  # Accepted
    
    data = response.json()
    assert data["success"] == True
    assert "data" in data
    
    run_data = data["data"]
    assert run_data["source"] == "OFAC"
    assert "run_id" in run_data

def test_invalid_scraper_request():
    """Test scraper request validation."""
    # Invalid source
    response = client.post("/api/v2/scraping/run", json={
        "source": "INVALID_SOURCE",
        "timeout_seconds": 120
    })
    assert response.status_code == 422
    
    # Invalid timeout
    response = client.post("/api/v2/scraping/run", json={
        "source": "OFAC",
        "timeout_seconds": -10
    })
    assert response.status_code == 422

# ======================== ERROR RESPONSE TESTS ========================

def test_error_response_format():
    """Test standardized error response format."""
    response = client.get("/api/v2/entities/invalid-uid-format")
    assert response.status_code == 404
    
    data = response.json()
    assert data["success"] == False
    assert "error" in data
    
    error = data["error"]
    assert "code" in error
    assert "message" in error
    assert "category" in error

# ======================== SCHEMA VALIDATION TESTS ========================

def test_response_schema_validation():
    """Test that responses match defined schemas."""
    from src.api.schemas.entity import EntityListResponse
    
    response = client.get("/api/v2/entities?limit=5")
    assert response.status_code == 200
    
    # Validate response matches schema
    data = response.json()
    validated = EntityListResponse(**data)  # Should not raise validation error
    assert validated.success == True

def test_request_parameter_coercion():
    """Test that parameters are properly coerced to correct types."""
    # String "true" should be coerced to boolean
    response = client.get("/api/v2/entities?active_only=true")
    assert response.status_code == 200
    
    # String number should be coerced to integer
    response = client.get("/api/v2/entities?limit=10")
    assert response.status_code == 200
    
    data = response.json()
    assert data["pagination"]["limit"] == 10  # Should be integer, not string

# ======================== PERFORMANCE TESTS ========================

def test_dto_performance():
    """Test that DTOs don't significantly impact performance."""
    import time
    
    # Test v1 API (no DTOs)
    start = time.time()
    for _ in range(10):
        client.get("/api/v1/entities?limit=10")
    v1_time = time.time() - start
    
    # Test v2 API (with DTOs)
    start = time.time()
    for _ in range(10):
        client.get("/api/v2/entities?limit=10")
    v2_time = time.time() - start
    
    # DTOs shouldn't add more than 50% overhead
    assert v2_time < v1_time * 1.5
    
    print(f"v1 time: {v1_time:.3f}s, v2 time: {v2_time:.3f}s")