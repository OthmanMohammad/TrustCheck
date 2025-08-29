#!/usr/bin/env python3
"""
Automated Test Migration Script

This script will organize all your test files into a proper structure.
Run this from your backend directory.
"""

import os
import shutil
from pathlib import Path

def migrate_tests():
    """Migrate all test files to organized structure."""
    
    backend_dir = Path.cwd()
    tests_dir = backend_dir / 'tests'
    
    # Color codes for output
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    
    print(f"{GREEN}Starting test migration...{RESET}\n")
    
    # 1. Create directory structure
    directories = [
        'tests/api',
        'tests/integration',
        'tests/unit',
        'tests/diagnostic',
        'tests/fixtures'
    ]
    
    for dir_path in directories:
        path = backend_dir / dir_path
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {dir_path}")
    
    # 2. Define file mappings
    file_mappings = {
        # API tests
        'test_api.py': 'tests/api/test_api.py',
        'test_api_v1_async.py': 'tests/api/test_api_v1_async.py',
        'test_api_v2.py': 'tests/api/test_api_v2.py',
        'test_api_integration.py': 'tests/api/test_api_integration.py',
        'test_async_api.py': 'tests/api/test_async_api.py',
        'test_async_verification.py': 'tests/api/test_async_verification.py',
        'test_fixes.py': 'tests/api/test_fixes.py',
        'test_phase3.py': 'tests/api/test_phase3.py',
        
        # Integration tests
        'test_integration.py': 'tests/integration/test_integration.py',
        'test_integration_2.py': 'tests/integration/test_integration_2.py',
        'test_scraper.py': 'tests/integration/test_scraper.py',
        'test_change_detection.py': 'tests/integration/test_change_detection.py',
        'test_async.py': 'tests/integration/test_async.py',
        
        # Diagnostic tests
        'diagnose_api.py': 'tests/diagnostic/diagnose_api.py',
        'diagnose_phase3.py': 'tests/diagnostic/diagnose_phase3.py',
        'diagnose_validation.py': 'tests/diagnostic/diagnose_validation.py',
        'test_debug.py': 'tests/diagnostic/test_debug.py',
        'test_db_connection.py': 'tests/diagnostic/test_db_connection.py',
    }
    
    # 3. Move files
    print(f"\n{YELLOW}Moving test files...{RESET}")
    moved_count = 0
    skipped_count = 0
    
    for source, destination in file_mappings.items():
        source_path = backend_dir / source
        dest_path = backend_dir / destination
        
        if source_path.exists():
            try:
                # Create backup if destination exists
                if dest_path.exists():
                    backup_path = dest_path.with_suffix('.backup')
                    shutil.copy2(dest_path, backup_path)
                    print(f"  📋 Backed up existing {destination}")
                
                # Move the file
                shutil.move(str(source_path), str(dest_path))
                print(f"  ✅ Moved {source} → {destination}")
                moved_count += 1
            except Exception as e:
                print(f"  ❌ Error moving {source}: {e}")
        else:
            print(f"  ⏭️  Skipped {source} (not found)")
            skipped_count += 1
    
    # 4. Handle special files in tests directory
    if (tests_dir / 'fakes.py').exists():
        shutil.move(str(tests_dir / 'fakes.py'), str(tests_dir / 'fixtures' / 'fakes.py'))
        print(f"  ✅ Moved tests/fakes.py → tests/fixtures/fakes.py")
        moved_count += 1
    
    # Remove empty test_api_v2.py if it exists
    empty_file = tests_dir / 'test_api_v2.py'
    if empty_file.exists() and empty_file.stat().st_size == 0:
        empty_file.unlink()
        print(f"  🗑️  Removed empty tests/test_api_v2.py")
    
    # 5. Create __init__.py files
    print(f"\n{YELLOW}Creating __init__.py files...{RESET}")
    for dir_path in directories:
        init_file = backend_dir / dir_path / '__init__.py'
        if not init_file.exists():
            init_file.write_text('"""Test package."""\n')
            print(f"  ✅ Created {dir_path}/__init__.py")
    
    # 6. Create/update conftest.py
    conftest_content = '''"""
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
'''
    
    conftest_path = tests_dir / 'conftest.py'
    conftest_path.write_text(conftest_content)
    print(f"  ✅ Updated tests/conftest.py")
    
    # 7. Summary
    print(f"\n{GREEN}{'='*50}{RESET}")
    print(f"{GREEN}Migration Complete!{RESET}")
    print(f"{GREEN}{'='*50}{RESET}")
    print(f"📊 Summary:")
    print(f"  • Files moved: {moved_count}")
    print(f"  • Files skipped: {skipped_count}")
    print(f"  • Directories created: {len(directories)}")
    
    print(f"\n📝 Next steps:")
    print(f"  1. Run tests with: python run_tests.py")
    print(f"  2. Or specific suite: python run_tests.py api")
    print(f"  3. Or with pytest: python -m pytest tests/")
    
    return moved_count > 0

if __name__ == "__main__":
    import sys
    
    # Check if we're in the backend directory
    if not Path('src').exists() or not Path('tests').exists():
        print("❌ Error: Please run this script from the backend directory!")
        print("   cd backend && python migrate_tests.py")
        sys.exit(1)
    
    # Confirm with user
    print("This script will organize all test files into a proper structure.")
    print("Current directory:", Path.cwd())
    response = input("\nProceed with migration? (y/n): ").lower()
    
    if response == 'y':
        success = migrate_tests()
        sys.exit(0 if success else 1)
    else:
        print("Migration cancelled.")
        sys.exit(0)