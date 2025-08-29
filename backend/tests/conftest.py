"""
Test configuration to fix import paths and provide shared fixtures.
"""

import sys
import os
from pathlib import Path

# Get the backend directory (parent of tests directory)
backend_dir = Path(__file__).parent.parent.absolute()

# Add backend directory to Python path so tests can import 'src'
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Also add the src directory directly for convenience
src_dir = backend_dir / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Set PYTHONPATH environment variable as well
os.environ['PYTHONPATH'] = str(backend_dir)

# Import pytest for fixtures
import pytest

# Add any shared fixtures here
@pytest.fixture
def base_url():
    """Base URL for API tests."""
    return "http://localhost:8000"

@pytest.fixture
def test_headers():
    """Default headers for API tests."""
    return {"Content-Type": "application/json"}
