#!/usr/bin/env python3
"""
Basic functionality test for ROM Downloader
Tests core components without GUI.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_config():
    """Test configuration loading."""
    print("Testing configuration system...")
    try:
        from config.config import ConfigManager
        config = ConfigManager()
        
        platforms = config.get_platforms()
        print(f"✓ Loaded {len(platforms)} platforms")
        
        settings = config.get_settings()
        print(f"✓ Loaded settings: {len(settings)} items")
        
        # Test GameCube platform
        gamecube = config.get_platform("GameCube")
        if gamecube:
            print(f"✓ GameCube platform configured: {gamecube['url']}")
        else:
            print("✗ GameCube platform not found")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_scraper():
    """Test web scraper (without actually scraping)."""
    print("\nTesting web scraper...")
    try:
        from scraper.web_scraper import WebScraper, RomInfo
        
        scraper = WebScraper()
        print("✓ Web scraper initialized")
        
        # Test ROM info creation
        rom = RomInfo("Super Mario Sunshine (USA).rvz", "http://example.com/test.rvz", "1.2 GB", "RVZ")
        print(f"✓ ROM info: {rom.clean_name} ({rom.region})")
        
        return True
    except Exception as e:
        print(f"✗ Scraper test failed: {e}")
        return False

def test_rom_filter():
    """Test ROM filtering."""
    print("\nTesting ROM filter...")
    try:
        from scraper.web_scraper import RomInfo
        from rom_manager.rom_filter import RomFilter
        
        filter_obj = RomFilter()
        
        # Create test ROMs
        roms = [
            RomInfo("Super Mario Sunshine (USA).rvz", "http://example.com/test1.rvz"),
            RomInfo("Super Mario Sunshine (Europe).rvz", "http://example.com/test2.rvz"),
            RomInfo("Super Mario Sunshine (Japan).rvz", "http://example.com/test3.rvz"),
            RomInfo("Metroid Prime (USA).rvz", "http://example.com/test4.rvz"),
        ]
        
        filtered = filter_obj.filter_and_deduplicate(roms)
        print(f"✓ Filtered {len(roms)} ROMs down to {len(filtered)}")
        
        for rom in filtered:
            print(f"  - {rom.clean_name} ({rom.region})")
        
        return True
    except Exception as e:
        print(f"✗ ROM filter test failed: {e}")
        return False

def test_state_manager():
    """Test state persistence."""
    print("\nTesting state manager...")
    try:
        from state.state_manager import StateManager
        
        state = StateManager()
        print("✓ State manager initialized")
        
        # Test saving/loading selections
        test_selections = {"test_rom_1", "test_rom_2"}
        state.save_platform_selections("TestPlatform", test_selections)
        
        loaded_selections = state.load_platform_selections("TestPlatform")
        if loaded_selections == test_selections:
            print("✓ State persistence working")
        else:
            print("✗ State persistence failed")
            return False
        
        return True
    except Exception as e:
        print(f"✗ State manager test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("ROM Downloader - Basic Component Tests")
    print("=" * 40)
    
    tests = [
        test_config,
        test_scraper,
        test_rom_filter,
        test_state_manager,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("✓ All tests passed! The application should work correctly.")
        print("\nTo run the GUI application:")
        print("  python run.py")
    else:
        print("✗ Some tests failed. Check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())