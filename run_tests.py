#!/usr/bin/env python3
"""
Test runner for ROM Downloader components
"""

import sys
import os
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_basic_tests():
    """Run basic unit tests"""
    print("Running basic unit tests...")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.test_basic_functionality')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_integration_tests():
    """Run integration tests"""
    print("Running integration tests...")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('tests.test_integration')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_all_tests():
    """Run all tests and return success status"""
    print("Running all tests...")
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nResult: {'PASS' if success else 'FAIL'}")
    
    return success

if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "basic":
            success = run_basic_tests()
        elif test_type == "integration":
            success = run_integration_tests()
        elif test_type == "all":
            success = run_all_tests()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python run_tests.py [basic|integration|all]")
            sys.exit(1)
    else:
        success = run_all_tests()
    
    sys.exit(0 if success else 1)