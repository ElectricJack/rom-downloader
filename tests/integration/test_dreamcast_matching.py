#!/usr/bin/env python3
"""
Test script to debug Dreamcast ROM matching issues.
This script compares installed ROMs with the game library to find mismatches.
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rom_manager.rom_filter import RomFilter
from state.distributed_state_manager import DistributedStateManager
from config.config import ConfigManager

def get_installed_roms():
    """Get all ROMs currently installed in Dreamcast folder"""
    dreamcast_path = Path('/mnt/batocera/roms/dreamcast')
    
    if not dreamcast_path.exists():
        print(f"❌ Dreamcast folder not found: {dreamcast_path}")
        return []
    
    # Get all ROM files (not images or other metadata)
    rom_extensions = {'.chd', '.cdi', '.gdi', '.bin', '.cue', '.iso'}
    installed_files = []
    
    for file_path in dreamcast_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in rom_extensions:
            installed_files.append(file_path)
    
    return sorted(installed_files)

def get_library_roms():
    """Get all ROMs from the game library"""
    state_manager = DistributedStateManager()
    success = state_manager.load_platform_library('Dreamcast')
    
    if not success or not state_manager.platform_library:
        print("❌ Failed to load Dreamcast library")
        return []
    
    library_roms = []
    for game in state_manager.platform_library.games.values():
        for rom in game.variants.values():
            if rom.platform == 'Dreamcast':
                library_roms.append(rom)
    
    return library_roms

def test_normalization_matching():
    """Test the ROM matching logic"""
    print("=== DREAMCAST ROM MATCHING TEST ===\n")
    
    # Get installed and library ROMs
    installed_files = get_installed_roms()
    library_roms = get_library_roms()
    
    print(f"📁 Found {len(installed_files)} installed ROM files")
    print(f"📚 Found {len(library_roms)} ROMs in library")
    print()
    
    # Initialize ROM filter
    rom_filter = RomFilter()
    
    # Build normalized lookup for installed ROMs
    print("=== INSTALLED ROM NORMALIZATION ===")
    installed_normalized = {}
    for file_path in installed_files:
        stem = file_path.stem  # Remove extension
        normalized = rom_filter.rom_utils.normalize_rom_name(stem)
        installed_normalized[normalized] = file_path
        print(f"File: {file_path.name}")
        print(f"  Stem: {stem}")
        print(f"  Normalized: '{normalized}'")
        print()
    
    # Test library ROM matching
    print("=== LIBRARY ROM MATCHING TEST ===")
    matched_count = 0
    unmatched_roms = []
    
    for rom in library_roms:
        normalized = rom_filter.rom_utils.normalize_rom_name(rom.filename)
        is_match = normalized in installed_normalized
        
        if is_match:
            matched_count += 1
            print(f"✅ MATCH: {rom.filename}")
            print(f"   Normalized: '{normalized}'")
            print(f"   Matches file: {installed_normalized[normalized].name}")
        else:
            unmatched_roms.append((rom.filename, normalized))
            print(f"❌ NO MATCH: {rom.filename}")
            print(f"   Normalized: '{normalized}'")
        print()
    
    # Summary
    print("=== SUMMARY ===")
    print(f"Installed files: {len(installed_files)}")
    print(f"Library ROMs: {len(library_roms)}")
    print(f"Matched ROMs: {matched_count}")
    print(f"Unmatched ROMs: {len(unmatched_roms)}")
    print(f"Match rate: {matched_count/len(library_roms)*100:.1f}%")
    print()
    
    # Show unmatched files
    if installed_files:
        print("=== INSTALLED BUT NOT IN LIBRARY ===")
        library_normalized = {rom_filter.rom_utils.normalize_rom_name(rom.filename) for rom in library_roms}
        
        for file_path in installed_files:
            stem = file_path.stem
            normalized = rom_filter.rom_utils.normalize_rom_name(stem)
            if normalized not in library_normalized:
                print(f"📁 {file_path.name} (normalized: '{normalized}')")
    
    print()
    
    # Show first few unmatched library ROMs for analysis
    if unmatched_roms:
        print("=== FIRST 10 UNMATCHED LIBRARY ROMS ===")
        for i, (filename, normalized) in enumerate(unmatched_roms[:10]):
            print(f"{i+1}. {filename} → '{normalized}'")
            
            # Try to find similar installed files
            similar_files = []
            for inst_normalized, inst_file in installed_normalized.items():
                if inst_normalized in normalized or normalized in inst_normalized:
                    similar_files.append((inst_file.name, inst_normalized))
            
            if similar_files:
                print(f"   Similar installed files:")
                for sim_file, sim_norm in similar_files:
                    print(f"     - {sim_file} → '{sim_norm}'")
            print()
    
    return matched_count, len(library_roms), len(installed_files)

def analyze_normalization_patterns():
    """Analyze common patterns in ROM names to improve normalization"""
    print("=== NORMALIZATION PATTERN ANALYSIS ===\n")
    
    installed_files = get_installed_roms()
    rom_filter = RomFilter()
    
    # Analyze installed file patterns
    patterns = defaultdict(list)
    
    for file_path in installed_files:
        stem = file_path.stem
        
        # Look for common patterns
        if '(' in stem and ')' in stem:
            # Extract region/info in parentheses
            import re
            matches = re.findall(r'\([^)]+\)', stem)
            for match in matches:
                patterns['parentheses'].append(match)
        
        if '[' in stem and ']' in stem:
            # Extract info in brackets
            matches = re.findall(r'\[[^\]]+\]', stem)
            for match in matches:
                patterns['brackets'].append(match)
        
        # Check for version info
        if 'v' in stem.lower():
            patterns['version_info'].append(stem)
        
        # Check for special characters
        special_chars = set(stem) - set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')
        if special_chars:
            if 'special_chars' not in patterns:
                patterns['special_chars'] = set()
            patterns['special_chars'].update(special_chars)
    
    # Print pattern analysis
    for pattern_type, items in patterns.items():
        if pattern_type == 'special_chars':
            print(f"{pattern_type}: {sorted(items)}")
        else:
            unique_items = list(set(items))
            print(f"{pattern_type} ({len(unique_items)} unique):")
            for item in sorted(unique_items)[:20]:  # Show first 20
                print(f"  {item}")
            if len(unique_items) > 20:
                print(f"  ... and {len(unique_items) - 20} more")
        print()

if __name__ == "__main__":
    print("🎮 DREAMCAST ROM MATCHING DIAGNOSTIC TOOL\n")
    
    # Run the tests
    matched, total_library, total_installed = test_normalization_matching()
    
    print("="*50)
    analyze_normalization_patterns()
    
    print("="*50)
    print("🎯 NEXT STEPS:")
    if matched < total_library:
        print(f"- Fix normalization for {total_library - matched} unmatched library ROMs")
        print("- Look for patterns in unmatched ROMs above")
        print("- Update normalize_rom_name() method in ROM utilities as needed")
    else:
        print("- All library ROMs are matching! ✅")
    
    if total_installed > matched:
        print(f"- {total_installed - matched} installed files not found in library")
        print("- Consider updating ROM database or checking file naming")