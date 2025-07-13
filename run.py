#!/usr/bin/env python3
"""
ROM Downloader - Easy Run Script
Alternative entry point that handles dependency installation.
"""

import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import requests
        import bs4
        return True
    except ImportError:
        return False

def install_dependencies():
    """Install required dependencies."""
    print("Installing required dependencies...")
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if requirements_file.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
    else:
        # Fallback to manual installation
        packages = ["requests>=2.31.0", "beautifulsoup4>=4.12.0", "lxml>=4.9.0"]
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)

def main():
    """Main entry point."""
    print("ROM Downloader - Starting...")
    
    # Check and install dependencies if needed
    if not check_dependencies():
        print("Missing dependencies. Installing...")
        try:
            install_dependencies()
            print("Dependencies installed successfully!")
        except Exception as e:
            print(f"Error installing dependencies: {e}")
            print("Please run: pip install -r requirements.txt")
            return 1
    
    # Import and run the main application
    try:
        from main import main as app_main
        app_main()
    except Exception as e:
        print(f"Error starting application: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())