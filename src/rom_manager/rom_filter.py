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
from src.scraper.web_scraper import RomInfo
from src.utils.rom_utils import get_rom_utils

logger = logging.getLogger(__name__)

class RomFilter:
    """Handles filtering and deduplication of ROM collections."""
    
    def __init__(self, preferred_regions: List[str] = None):
        """Initialize the ROM filter.
        
        Args:
            preferred_regions: List of preferred regions in order of preference.
        """
        self.preferred_regions = preferred_regions or ["USA", "US", "English", "En", "World", "Europe", "Japan"]
        # Cache for installed ROM information to avoid repeated network scans
        self._installed_cache = {}
        self._cache_directory = None
        # Cache directory contents to avoid repeated directory scans
        self._directory_cache = {}
        self._directory_cache_time = None
        # Get ROM utilities instance
        self.rom_utils = get_rom_utils()
    
    def filter_and_deduplicate(self, roms: List[RomInfo]) -> List[RomInfo]:
        """Filter ROMs by removing duplicates and applying region preferences.
        
        Args:
            roms: List of ROM information objects.
            
        Returns:
            Filtered list of ROMs with duplicates removed.
        """
        logger.info(f"Filtering {len(roms)} ROMs...")
        
        # Group ROMs by their canonical name
        rom_groups = defaultdict(list)
        for rom in roms:
            canonical_name = self.rom_utils.get_canonical_rom_name(rom.filename)
            rom_groups[canonical_name].append(rom)
        
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
    
    def scan_existing_roms(self, target_directory: Path, _extract_archives: bool = False) -> Set[str]:
        """Scan the target directory for existing ROM files.
        
        Args:
            target_directory: Path to scan for existing ROMs.
            extract_archives: Whether archives are extracted for this platform.
            
        Returns:
            Set of canonical ROM names that already exist.
        """
        import time
        start_time = time.time()
        canonical_names = set()
        
        logger.info(f"Scanning for existing ROMs in: {target_directory}")
        
        # Check if path exists
        try:
            exists_check_start = time.time()
            path_exists = target_directory.exists()
            exists_check_time = time.time() - exists_check_start
            logger.info(f"Path existence check took {exists_check_time:.2f}s, exists: {path_exists}")
            
            if not path_exists:
                logger.info(f"Target directory does not exist: {target_directory}")
                return canonical_names
        except Exception as e:
            logger.error(f"Error checking if target directory exists: {e}")
            return canonical_names
        
        # Check if it's a directory
        try:
            is_dir_start = time.time()
            is_directory = target_directory.is_dir()
            is_dir_time = time.time() - is_dir_start
            logger.info(f"Directory check took {is_dir_time:.2f}s, is_dir: {is_directory}")
            
            if not is_directory:
                logger.warning(f"Target path is not a directory: {target_directory}")
                return canonical_names
        except Exception as e:
            logger.error(f"Error checking if target path is directory: {e}")
            return canonical_names
        
        # Try to list directory contents with optimized network scanning
        try:
            logger.info("Starting optimized directory listing...")
            iterdir_start = time.time()
            
            # Get all directory entries at once to minimize network calls
            logger.info("Fetching directory entries...")
            try:
                entries = list(target_directory.iterdir())
                fetch_time = time.time() - iterdir_start
                logger.info(f"Fetched {len(entries)} directory entries in {fetch_time:.2f}s")
            except Exception as e:
                logger.error(f"Failed to fetch directory entries: {e}")
                return canonical_names
            
            # Process entries using filename-based filtering (no additional network calls)
            process_start = time.time()
            file_count = 0
            
            for i, entry in enumerate(entries):
                if i % 100 == 0 and i > 0:  # Log progress every 100 entries
                    logger.info(f"Processed {i}/{len(entries)} entries, found {len(canonical_names)} ROMs so far...")
                
                entry_name = entry.name
                
                # Filter by file extension to avoid network calls to is_file()
                # This is much faster than checking file_path.is_file() over the network
                if self.rom_utils.is_rom_file(entry_name) and not entry_name.startswith('.'):
                    file_count += 1
                    # Get canonical name using the unified method
                    canonical_name = self.rom_utils.get_canonical_rom_name(entry_name)
                    canonical_names.add(canonical_name)
                    
                    if len(canonical_names) <= 5:  # Log first 5 existing ROMs
                        logger.info(f"Found existing ROM: {entry_name} -> {canonical_name}")
                    elif len(canonical_names) % 50 == 0:  # Log progress every 50 ROMs
                        logger.info(f"Found {len(canonical_names)} existing ROMs so far...")
            
            process_time = time.time() - process_start
            total_time = time.time() - iterdir_start
            logger.info(f"Entry processing completed in {process_time:.2f}s")
            logger.info(f"Total scan time: {total_time:.2f}s, processed {len(entries)} entries, found {len(canonical_names)} ROM files")
            
        except PermissionError as e:
            logger.error(f"Permission denied accessing {target_directory}: {e}")
        except OSError as e:
            logger.error(f"OS error scanning existing ROMs in {target_directory}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning existing ROMs in {target_directory}: {e}", exc_info=True)
        
        total_time = time.time() - start_time
        logger.info(f"Existing ROM scan completed in {total_time:.2f}s")
        return canonical_names
    
    def is_rom_installed(self, rom: RomInfo, target_directory: Path, _extract_archives: bool = False) -> bool:
        """Check if a ROM is already installed using canonical name matching.
        
        Args:
            rom: ROM information object.
            target_directory: Directory where ROMs are stored.
            extract_archives: Whether archives are extracted for this platform.
            
        Returns:
            True if the ROM is installed, False otherwise.
        """
        if not target_directory.exists():
            return False
        
        # Get the canonical name for this ROM
        rom_canonical_name = self.rom_utils.get_canonical_rom_name(rom.filename)
        
        try:
            for file_path in target_directory.iterdir():
                if file_path.is_file() and self.rom_utils.is_rom_file(file_path.name):
                    # Get canonical name of the installed file
                    file_canonical_name = self.rom_utils.get_canonical_rom_name(file_path.name)
                    if file_canonical_name == rom_canonical_name:
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
            normalized_name = self.rom_utils.get_canonical_rom_name(rom.filename)
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
        
        # Clear cache if directory changed
        if self._cache_directory != target_directory:
            logger.debug(f"Directory changed, clearing installed ROM cache")
            self._installed_cache.clear()
            self._directory_cache.clear()
            self._cache_directory = target_directory
            self._directory_cache_time = None
        
        normalized_name = self.rom_utils.get_canonical_rom_name(rom.filename)
        
        # Check cache first
        if normalized_name in self._installed_cache:
            logger.debug(f"Using cached result for ROM: {rom.clean_name}")
            return self._installed_cache[normalized_name]
        
        logger.debug(f"Checking installed status for ROM: {rom.clean_name} (normalized: {normalized_name})")
        
        # Use a more efficient approach for network drives
        rom_extensions = self.rom_utils.get_rom_extensions_list()
        
        try:
            # Try direct file matching first (much faster for network drives)
            for ext in rom_extensions:
                # Try various possible filenames
                possible_names = [
                    rom.clean_name + ext,
                    rom.name.replace('.zip', ext).replace('.7z', ext),
                ]
                
                for possible_name in possible_names:
                    possible_path = target_directory / possible_name
                    try:
                        if possible_path.exists():
                            logger.debug(f"Found matching installed ROM via direct lookup: {possible_name}")
                            size_bytes = possible_path.stat().st_size
                            size_str = self._format_bytes(size_bytes)
                            file_type = ext.upper().replace('.', '')
                            result = (True, size_str, file_type)
                            # Cache the result
                            self._installed_cache[normalized_name] = result
                            return result
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        continue
            
            # Fallback to directory scanning using cached directory contents
            logger.debug(f"Direct lookup failed, checking cached directory contents for {rom.clean_name}")
            
            # Build or use cached directory contents
            if not self._directory_cache:
                logger.debug(f"Building directory cache for {target_directory}")
                import time
                cache_start = time.time()
                
                try:
                    # Scan directory once and cache all ROM file info
                    for file_path in target_directory.iterdir():
                        file_name = file_path.name
                        # Check extension first to avoid expensive network calls
                        if self.rom_utils.is_rom_file(file_name):
                            try:
                                # Get file info and cache it by normalized name
                                file_stem = self.rom_utils.get_rom_stem(file_name)
                                file_normalized = self.rom_utils.normalize_rom_name(file_stem)
                                size_bytes = file_path.stat().st_size
                                size_str = self._format_bytes(size_bytes)
                                file_type = file_path.suffix.upper().replace('.', '')
                                
                                # Store in directory cache
                                self._directory_cache[file_normalized] = {
                                    'size': size_str,
                                    'type': file_type,
                                    'filename': file_name
                                }
                                
                            except (OSError, PermissionError):
                                # Skip files we can't access
                                continue
                    
                    cache_time = time.time() - cache_start
                    logger.info(f"Directory cache built in {cache_time:.2f}s, cached {len(self._directory_cache)} ROM files")
                    self._directory_cache_time = time.time()
                    
                except Exception as e:
                    logger.error(f"Error building directory cache: {e}")
                    self._directory_cache = {}
            
            # Check cached directory contents
            if normalized_name in self._directory_cache:
                cached_info = self._directory_cache[normalized_name]
                logger.debug(f"Found matching installed ROM in cache: {cached_info['filename']}")
                result = (True, cached_info['size'], cached_info['type'])
                # Cache the result in installed cache too
                self._installed_cache[normalized_name] = result
                return result
            
            # Cache negative result to avoid repeated scans
            result = (False, "", "")
            self._installed_cache[normalized_name] = result
                
        except Exception as e:
            logger.error(f"Error getting installed ROM info for {rom.clean_name}: {e}")
            return False, "", ""
        
        return False, "", ""
    
    def scan_installed_only_roms(self, target_directory: Path, platform: str, existing_online_roms: Set[str]) -> List['RomInfo']:
        """Scan for ROMs that are installed but not available online.
        
        Args:
            target_directory: Path to scan for existing ROMs.
            platform: Platform name for ROM creation.
            existing_online_roms: Set of normalized names of ROMs available online.
            
        Returns:
            List of RomInfo objects for installed-only ROMs.
        """
        from src.scraper.web_scraper import RomInfo
        
        installed_only_roms = []
        
        if not target_directory.exists():
            return installed_only_roms
        
        logger.info(f"Scanning for installed-only ROMs in: {target_directory}")
        
        try:
            rom_extensions = self.rom_utils.get_all_rom_extensions()
            
            for file_path in target_directory.iterdir():
                if file_path.is_file():
                    file_name = file_path.name
                    
                    # Check if it's a ROM file
                    has_rom_extension = self.rom_utils.is_rom_file(file_name)
                    
                    if has_rom_extension and not file_name.startswith('.'):
                        # Get canonical name using the unified method
                        normalized_name = self.rom_utils.get_canonical_rom_name(file_name)
                        
                        # Check if this ROM is NOT available online
                        if normalized_name not in existing_online_roms:
                            # Debug logging to help troubleshoot matching issues
                            logger.debug(f"ROM marked as installed-only: {file_name}")
                            logger.debug(f"  Stem: '{file_path.stem}'")
                            logger.debug(f"  Normalized: '{normalized_name}'")
                            logger.debug(f"  Available online ROMs (first 5): {list(existing_online_roms)[:5]}")
                            
                            # Get file size
                            try:
                                size_bytes = file_path.stat().st_size
                                size_str = self._format_bytes(size_bytes)
                            except (OSError, PermissionError):
                                size_str = "Unknown"
                            
                            # Create RomInfo for this installed-only ROM
                            rom_info = RomInfo(
                                name=file_name,
                                url="",  # No URL since it's not available online
                                size=size_str
                            )
                            rom_info.is_installed_only = True
                            
                            installed_only_roms.append(rom_info)
                            
                            logger.info(f"Found installed-only ROM: {file_name} (normalized: {normalized_name})")
            
            logger.info(f"Found {len(installed_only_roms)} installed-only ROMs")
            
        except Exception as e:
            logger.error(f"Error scanning for installed-only ROMs: {e}")
        
        return installed_only_roms
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"