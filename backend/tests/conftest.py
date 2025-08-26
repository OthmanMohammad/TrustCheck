"""
Test configuration to fix import paths.
"""

import sys
import os

# Add the backend directory to Python path so tests can find 'src' module
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)