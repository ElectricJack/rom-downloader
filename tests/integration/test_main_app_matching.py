#!/usr/bin/env python3
"""
Test script to verify ROM matching works correctly in the main application GUIs.
This tests both main_window.py and game_library_gui.py implementations.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rom_manager.rom_filter import RomFilter
from scraper.web_scraper import RomInfo

def test_main_window_matching():
    """Test ROM matching as used in main_window.py"""
    print("=== TESTING MAIN_WINDOW.PY MATCHING ===\n")
    
    rom_filter = RomFilter()
    
    # Simulate main_window._is_rom_installed() logic
    # Test ROMs that should match installed files
    test_roms = [
        RomInfo(
            name="Tony Hawk's Pro Skater 2 (USA).zip",
            url="http://example.com/test.zip",
            size="500MB"
        ),
        RomInfo(
            name="18 Wheeler - American Pro Trucker (Europe) (En,Fr,De,Es).zip", 
            url="http://example.com/test2.zip",
            size="1GB"
        ),
        RomInfo(
            name="Crazy Taxi (Japan).zip",
            url="http://example.com/test3.zip", 
            size="800MB"
        )
    ]
    
    # Build existing_roms cache like main_window does
    dreamcast_path = Path('/mnt/batocera/roms/dreamcast')
    rom_extensions = {'.chd', '.cdi', '.gdi', '.bin', '.cue', '.iso'}
    
    existing_roms = set()
    
    if dreamcast_path.exists():
        for file_path in dreamcast_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in rom_extensions:
                # This is how main_window builds the cache (line 984)
                normalized_name = rom_filter._normalize_name(file_path.stem)
                existing_roms.add(normalized_name)
        
        print(f"Found {len(existing_roms)} normalized installed ROMs")
        
        # Test each ROM
        for rom in test_roms:
            # This is how main_window._is_rom_installed() works (line 912)
            normalized_name = rom_filter._normalize_name(rom.clean_name)
            is_installed = normalized_name in existing_roms
            
            print(f"ROM: {rom.clean_name}")
            print(f"  Normalized: '{normalized_name}'")
            print(f"  Is Installed: {is_installed}")
            print()
    else:
        print("❌ Dreamcast directory not found")

def test_game_library_gui_matching():
    """Test ROM matching as used in game_library_gui.py"""
    print("=== TESTING GAME_LIBRARY_GUI.PY MATCHING ===\n")
    
    rom_filter = RomFilter()
    
    # Test using the scan_existing_roms method (line 1513, 1544)
    dreamcast_path = Path('/mnt/batocera/roms/dreamcast')
    
    if dreamcast_path.exists():
        print("Testing scan_existing_roms() method...")
        existing_roms = rom_filter.scan_existing_roms(dreamcast_path)
        print(f"Found {len(existing_roms)} existing ROMs in cache")
        
        # Show first few entries
        print("\nFirst 5 cached entries:")
        for i, normalized_name in enumerate(list(existing_roms)[:5]):
            print(f"  {i+1}. '{normalized_name}'")
        
        # Test is_rom_installed method (line 1328)
        print("\nTesting is_rom_installed() method:")
        test_roms = [
            RomInfo(
                name="Tony Hawk's Pro Skater 2 (USA).zip",
                url="http://example.com/test.zip", 
                size="500MB"
            ),
            RomInfo(
                name="Crazy Taxi (Europe).zip",
                url="http://example.com/test2.zip",
                size="800MB"
            )
        ]
        
        for rom in test_roms:
            is_installed = rom_filter.is_rom_installed(rom, dreamcast_path)
            print(f"ROM: {rom.clean_name}")
            print(f"  Is Installed: {is_installed}")
            print()
    else:
        print("❌ Dreamcast directory not found")

def test_specific_known_matches():
    """Test specific ROMs we know are installed"""
    print("=== TESTING SPECIFIC KNOWN MATCHES ===\n")
    
    rom_filter = RomFilter()
    dreamcast_path = Path('/mnt/batocera/roms/dreamcast')
    
    if not dreamcast_path.exists():
        print("❌ Dreamcast directory not found")
        return
        
    # Get actual installed files
    installed_files = []
    rom_extensions = {'.chd', '.cdi', '.gdi', '.bin', '.cue', '.iso'}
    
    for file_path in dreamcast_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in rom_extensions:
            installed_files.append(file_path)
    
    # Test first few installed files to make sure they match themselves
    print("Testing self-matching of installed files:")
    for i, file_path in enumerate(installed_files[:5]):
        # Create ROM object like it would come from web scraper
        test_rom = RomInfo(
            name=file_path.name,  # Full filename with extension
            url="http://example.com/test.zip",
            size="1GB"  
        )
        
        # Test both methods
        is_installed_method1 = rom_filter.is_rom_installed(test_rom, dreamcast_path)
        
        # Method 2: manual normalization check
        existing_roms = rom_filter.scan_existing_roms(dreamcast_path)
        normalized_name = rom_filter._normalize_name(test_rom.clean_name)
        is_installed_method2 = normalized_name in existing_roms
        
        print(f"{i+1}. File: {file_path.name}")
        print(f"   ROM name: {test_rom.clean_name}")
        print(f"   Normalized: '{normalized_name}'")
        print(f"   Method 1 (is_rom_installed): {is_installed_method1}")
        print(f"   Method 2 (cache lookup): {is_installed_method2}")
        print(f"   Match: {'✅' if is_installed_method1 and is_installed_method2 else '❌'}")
        print()

if __name__ == "__main__":
    print("🧪 MAIN APPLICATION ROM MATCHING TEST\n")
    
    test_main_window_matching()
    print("=" * 60)
    test_game_library_gui_matching()
    print("=" * 60) 
    test_specific_known_matches()
    
    print("🎯 If all tests show correct matching, the main app will work properly!")