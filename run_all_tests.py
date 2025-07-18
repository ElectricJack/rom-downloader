#!/usr/bin/env python3
"""
Simple test runner that runs all tests individually to avoid import issues
"""

import sys
import os
import subprocess

def run_test_file(test_file_path, description):
    """Run a single test file and return success status"""
    print(f"\n{'='*60}")
    print(f"Running {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, test_file_path], 
                              capture_output=False, 
                              cwd=os.path.dirname(__file__))
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file_path}: {e}")
        return False

def main():
    """Run all tests"""
    project_root = os.path.dirname(__file__)
    
    # Define test files to run
    test_files = [
        ("tests/filters/test_advanced_rom_filter.py", "Advanced ROM Filter Tests"),
        ("tests/integration/test_gui_integration.py", "GUI Integration Tests"),
        ("tests/unit/test_basic.py", "Basic Unit Tests"),
    ]
    
    # Track results
    total_tests = len(test_files)
    passed_tests = 0
    failed_tests = []
    
    # Run each test file
    for test_file, description in test_files:
        test_path = os.path.join(project_root, test_file)
        
        if not os.path.exists(test_path):
            print(f"Warning: Test file not found: {test_path}")
            continue
            
        success = run_test_file(test_path, description)
        
        if success:
            passed_tests += 1
            print(f"✅ {description} - PASSED")
        else:
            failed_tests.append(description)
            print(f"❌ {description} - FAILED")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\nFailed tests:")
        for test in failed_tests:
            print(f"  - {test}")
    
    success = len(failed_tests) == 0
    print(f"\nOverall result: {'✅ PASS' if success else '❌ FAIL'}")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)