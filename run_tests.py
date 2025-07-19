#!/usr/bin/env python3
"""
Master test runner for ROM Downloader - runs tests from project root
"""

import sys
import os
import unittest
import subprocess

def run_tests():
    """Run all tests using the tests directory runner"""
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    # Change to tests directory and run the test runner
    try:
        result = subprocess.run([
            sys.executable, 'run_tests.py', 'all'
        ], cwd=tests_dir, capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def run_specific_test(test_file):
    """Run a specific test file"""
    project_root = os.path.dirname(__file__)
    src_path = os.path.join(project_root, 'src')
    
    # Add src to path
    sys.path.insert(0, src_path)
    
    # Run the specific test
    try:
        if test_file.startswith('tests/'):
            test_path = os.path.join(project_root, test_file)
        else:
            test_path = os.path.join(project_root, 'tests', test_file)
            
        result = subprocess.run([sys.executable, test_path], capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running test {test_file}: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        success = run_specific_test(test_file)
    else:
        # Run all tests
        success = run_tests()
    
    sys.exit(0 if success else 1)