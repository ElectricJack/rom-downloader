#!/usr/bin/env python3
"""
ROM Downloader - Refactored Main Entry Point
Uses the new architecture with tool pipelines and game library management.
"""

import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui.game_library_gui import GameLibraryGUI
from config.enhanced_config_manager import EnhancedConfigManager


def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('rom_downloader.log'),
            logging.StreamHandler()
        ]
    )


def ensure_config_exists():
    """Ensure configuration file exists"""
    # Config manager now handles creating config in appropriate OS directory
    config_manager = EnhancedConfigManager()
    
    if not config_manager.config_file.exists():
        print("No configuration file found. Creating default configuration...")
        
        if not config_manager.initialize_default_config():
            print("Failed to create default configuration")
            return False
        
        print(f"Default configuration created at {config_manager.config_file}")
        print("You can edit this file to add more platforms or modify settings.")
    
    return True


def main():
    """Main entry point for the refactored ROM downloader"""
    print("ROM Downloader - Refactored Version Starting...")
    
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Ensure configuration exists
        if not ensure_config_exists():
            return 1
        
        
        # Test configuration loading
        config_manager = EnhancedConfigManager()
        if not config_manager.get_platforms():
            logger.error("No platforms configured. Please check config/platforms.json")
            return 1
        
        logger.info("Configuration loaded successfully")
        
        # Create and run GUI
        logger.info("Starting GUI...")
        gui = GameLibraryGUI()
        gui.run()
        
        logger.info("Application closed")
        return 0
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please ensure all dependencies are installed: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"Error starting application: {e}")
        logger.error(f"Application error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())