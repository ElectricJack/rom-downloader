"""
ROM Filter and Management
Handles filtering, deduplication, and organization of ROM files.
"""

import re
import logging
from typing import List, Dict, Set
from collections import defaultdict
from pathlib import Path

# Import RomInfo from scraper module
import sys
sys.path.append(str(Path(__file__).parent.parent))
from scraper.web_scraper import RomInfo

logger = logging.getLogger(__name__)

class RomFilter:
    """Handles filtering and deduplication of ROM collections."""
    
    def __init__(self, preferred_regions: List[str] = None):
        """Initialize the ROM filter.
        
        Args:
            preferred_regions: List of preferred regions in order of preference.
        """
        self.preferred_regions = preferred_regions or ["USA", "US", "English", "En", "World", "Europe", "Japan"]
    
    def filter_and_deduplicate(self, roms: List[RomInfo]) -> List[RomInfo]:
        """Filter ROMs by removing duplicates and applying region preferences.
        
        Args:
            roms: List of ROM information objects.
            
        Returns:
            Filtered list of ROMs with duplicates removed.
        """
        logger.info(f"Filtering {len(roms)} ROMs...")
        
        # Group ROMs by their clean name
        rom_groups = defaultdict(list)
        for rom in roms:
            clean_name = self._normalize_name(rom.clean_name)
            rom_groups[clean_name].append(rom)
        
        filtered_roms = []
        
        for game_name, game_roms in rom_groups.items():
            if len(game_roms) == 1:
                # No duplicates, add the single ROM
                filtered_roms.append(game_roms[0])
            else:
                # Multiple ROMs for the same game, pick the best one
                best_rom = self._select_best_rom(game_roms)
                if best_rom:
                    filtered_roms.append(best_rom)
                    logger.debug(f"Selected {best_rom.name} from {len(game_roms)} duplicates for '{game_name}'")
        
        logger.info(f"Filtered down to {len(filtered_roms)} unique ROMs")
        return sorted(filtered_roms, key=lambda x: x.clean_name.lower())
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a ROM name for comparison purposes.
        
        Args:
            name: Original ROM name.
            
        Returns:
            Normalized name for grouping.
        """
        # Convert to lowercase
        normalized = name.lower()
        
        # Remove common variations
        normalized = re.sub(r'\s*[-_]\s*', ' ', normalized)  # Normalize separators
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove special chars
        normalized = normalized.strip()
        
        # Remove common suffixes that indicate versions
        version_patterns = [
            r'\s+v\d+(\.\d+)*$',  # Version numbers
            r'\s+rev\s*\d+$',     # Revision numbers
            r'\s+final$',         # Final versions
            r'\s+repack$',        # Repacks
            r'\s+proper$',        # Proper releases
        ]
        
        for pattern in version_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def _select_best_rom(self, roms: List[RomInfo]) -> RomInfo:
        """Select the best ROM from a list of duplicates.
        
        Args:
            roms: List of ROM duplicates.
            
        Returns:
            The best ROM based on region preference and other criteria.
        """
        if not roms:
            return None
        
        if len(roms) == 1:
            return roms[0]
        
        # Score each ROM
        scored_roms = []
        for rom in roms:
            score = self._calculate_rom_score(rom)
            scored_roms.append((score, rom))
        
        # Sort by score (higher is better) and return the best
        scored_roms.sort(key=lambda x: x[0], reverse=True)
        return scored_roms[0][1]
    
    def _calculate_rom_score(self, rom: RomInfo) -> int:
        """Calculate a score for ROM selection.
        
        Args:
            rom: ROM to score.
            
        Returns:
            Score (higher is better).
        """
        score = 0
        
        # Region preference scoring
        for i, preferred_region in enumerate(self.preferred_regions):
            if preferred_region.lower() in rom.region.lower():
                score += (len(self.preferred_regions) - i) * 100
                break
        
        # File type preference (RVZ > ZIP > 7Z for GameCube)
        file_type_scores = {
            'RVZ': 50,
            'ZIP': 30,
            '7Z': 20,
            'ISO': 40,
            'BIN': 10
        }
        score += file_type_scores.get(rom.file_type.upper(), 0)
        
        # Penalty for unwanted indicators
        unwanted_patterns = [
            r'beta', r'alpha', r'demo', r'sample', r'promo',
            r'kiosk', r'debug', r'prototype', r'test'
        ]
        
        for pattern in unwanted_patterns:
            if re.search(pattern, rom.name, re.IGNORECASE):
                score -= 50
                break
        
        # Bonus for "proper" or "final" releases
        good_patterns = [r'proper', r'final', r'complete']
        for pattern in good_patterns:
            if re.search(pattern, rom.name, re.IGNORECASE):
                score += 25
                break
        
        return score
    
    def scan_existing_roms(self, target_directory: Path, extract_archives: bool = False) -> Set[str]:
        """Scan the target directory for existing ROM files.
        
        Args:
            target_directory: Path to scan for existing ROMs.
            extract_archives: Whether archives are extracted for this platform.
            
        Returns:
            Set of normalized ROM names that already exist.
        """
        import time
        start_time = time.time()
        existing_roms = set()
        
        logger.info(f"Scanning for existing ROMs in: {target_directory}")
        
        # Check if path exists
        try:
            exists_check_start = time.time()
            path_exists = target_directory.exists()
            exists_check_time = time.time() - exists_check_start
            logger.info(f"Path existence check took {exists_check_time:.2f}s, exists: {path_exists}")
            
            if not path_exists:
                logger.info(f"Target directory does not exist: {target_directory}")
                return existing_roms
        except Exception as e:
            logger.error(f"Error checking if target directory exists: {e}")
            return existing_roms
        
        # Check if it's a directory
        try:
            is_dir_start = time.time()
            is_directory = target_directory.is_dir()
            is_dir_time = time.time() - is_dir_start
            logger.info(f"Directory check took {is_dir_time:.2f}s, is_dir: {is_directory}")
            
            if not is_directory:
                logger.warning(f"Target path is not a directory: {target_directory}")
                return existing_roms
        except Exception as e:
            logger.error(f"Error checking if target path is directory: {e}")
            return existing_roms
        
        # Try to list directory contents
        try:
            logger.info("Starting directory listing...")
            iterdir_start = time.time()
            
            file_count = 0
            for file_path in target_directory.iterdir():
                file_count += 1
                if file_count % 100 == 0:  # Log progress every 100 files
                    logger.info(f"Processed {file_count} files so far...")
                
                if file_path.is_file():
                    # Normalize the filename for comparison
                    normalized_name = self._normalize_name(file_path.stem)
                    existing_roms.add(normalized_name)
                    
                    if len(existing_roms) <= 5:  # Log first 5 existing ROMs
                        logger.info(f"Found existing ROM: {file_path.name}")
                    elif len(existing_roms) % 50 == 0:  # Log progress every 50 ROMs
                        logger.info(f"Found {len(existing_roms)} existing ROMs so far...")
            
            iterdir_time = time.time() - iterdir_start
            logger.info(f"Directory listing completed in {iterdir_time:.2f}s, processed {file_count} total files")
            logger.info(f"Found {len(existing_roms)} existing ROMs in {target_directory}")
            
        except PermissionError as e:
            logger.error(f"Permission denied accessing {target_directory}: {e}")
        except OSError as e:
            logger.error(f"OS error scanning existing ROMs in {target_directory}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning existing ROMs in {target_directory}: {e}", exc_info=True)
        
        total_time = time.time() - start_time
        logger.info(f"Existing ROM scan completed in {total_time:.2f}s")
        return existing_roms
    
    def is_rom_installed(self, rom: RomInfo, target_directory: Path, extract_archives: bool = False) -> bool:
        """Check if a ROM is already installed, considering extraction settings.
        
        Args:
            rom: ROM information object.
            target_directory: Directory where ROMs are stored.
            extract_archives: Whether archives are extracted for this platform.
            
        Returns:
            True if the ROM is installed, False otherwise.
        """
        if not target_directory.exists():
            return False
        
        normalized_name = self._normalize_name(rom.clean_name)
        
        try:
            for file_path in target_directory.iterdir():
                if file_path.is_file():
                    file_normalized = self._normalize_name(file_path.stem)
                    if file_normalized == normalized_name:
                        return True
        except Exception as e:
            logger.error(f"Error checking if ROM is installed: {e}")
            return False
        
        return False
    
    def filter_already_downloaded(self, roms: List[RomInfo], existing_roms: Set[str]) -> List[RomInfo]:
        """Filter out ROMs that have already been downloaded.
        
        Args:
            roms: List of available ROMs.
            existing_roms: Set of existing ROM names (normalized).
            
        Returns:
            List of ROMs that need to be downloaded.
        """
        filtered_roms = []
        
        for rom in roms:
            normalized_name = self._normalize_name(rom.clean_name)
            if normalized_name not in existing_roms:
                filtered_roms.append(rom)
            else:
                logger.debug(f"Skipping already downloaded ROM: {rom.clean_name}")
        
        logger.info(f"Filtered out {len(roms) - len(filtered_roms)} already downloaded ROMs")
        return filtered_roms
    
    def get_installed_rom_info(self, rom: RomInfo, target_directory: Path) -> tuple[bool, str, str]:
        """Get detailed information about an installed ROM.
        
        Args:
            rom: ROM information object.
            target_directory: Directory where ROMs are stored.
            
        Returns:
            Tuple of (is_installed, file_size, file_type).
        """
        if not target_directory.exists():
            logger.debug(f"Target directory does not exist: {target_directory}")
            return False, "", ""
        
        normalized_name = self._normalize_name(rom.clean_name)
        logger.debug(f"Checking installed status for ROM: {rom.clean_name} (normalized: {normalized_name})")
        
        try:
            file_count = 0
            for file_path in target_directory.iterdir():
                if file_path.is_file():
                    file_count += 1
                    file_normalized = self._normalize_name(file_path.stem)
                    if file_normalized == normalized_name:
                        logger.debug(f"Found matching installed ROM: {file_path.name}")
                        # Get file size
                        size_bytes = file_path.stat().st_size
                        size_str = self._format_bytes(size_bytes)
                        
                        # Get file type (extension without dot)
                        file_type = file_path.suffix.upper().replace('.', '')
                        
                        return True, size_str, file_type
            
            if file_count > 100:
                logger.warning(f"Large number of files in target directory ({file_count}), this may slow down scanning")
                
        except Exception as e:
            logger.error(f"Error getting installed ROM info for {rom.clean_name}: {e}")
            return False, "", ""
        
        return False, "", ""
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"