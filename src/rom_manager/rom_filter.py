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
        
        # Remove file extensions to ensure consistent comparison
        # Handle common ROM extensions
        rom_extensions = ['.zip', '.7z', '.rar', '.chd', '.cdi', '.gdi', '.bin', '.cue', '.iso', 
                         '.rvz', '.wux', '.wud', '.gba', '.gbc', '.gb', '.nes', '.sfc', '.smc', 
                         '.n64', '.z64', '.v64', '.nds', '.vb', '.a26', '.a52', '.a78', '.pce']
        
        for ext in rom_extensions:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break
        
        # Remove everything in parentheses and brackets (regions, languages, quality indicators, etc.)
        normalized = re.sub(r'\([^)]*\)', '', normalized)  # Remove (anything)
        normalized = re.sub(r'\[[^\]]*\]', '', normalized)  # Remove [anything]
        
        # Remove numeric prefixes (common in GBA/DS collections: "0001 - Game Name" or "0001 Game Name")
        normalized = re.sub(r'^\d{3,4}\s*-?\s*', '', normalized)
        
        # Normalize apostrophe possessives before removing special chars
        normalized = re.sub(r"(\w)'s\b", r'\1s', normalized)  # "hawk's" -> "hawks"
        
        # Handle common name variations (specific game title fixes)
        normalized = re.sub(r'\btony hawk\b', 'tony hawks', normalized)  # "tony hawk" -> "tony hawks"
        
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
    
    def scan_existing_roms(self, target_directory: Path, _extract_archives: bool = False) -> Set[str]:
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
                return existing_roms
            
            # Process entries using filename-based filtering (no additional network calls)
            process_start = time.time()
            file_count = 0
            rom_extensions = {'.rvz', '.zip', '.7z', '.iso', '.gcm', '.bin', '.cue', '.chd', 
                             '.n64', '.z64', '.v64', '.nes', '.sfc', '.smc', '.gba', '.gbc', '.gb', 
                             '.nds', '.vb', '.pce', '.a26', '.a52', '.a78', '.cdi', '.gdi', '.wux', '.wud'}
            
            for i, entry in enumerate(entries):
                if i % 100 == 0 and i > 0:  # Log progress every 100 entries
                    logger.info(f"Processed {i}/{len(entries)} entries, found {len(existing_roms)} ROMs so far...")
                
                entry_name = entry.name
                
                # Filter by file extension to avoid network calls to is_file()
                # This is much faster than checking file_path.is_file() over the network
                has_rom_extension = any(entry_name.lower().endswith(ext) for ext in rom_extensions)
                
                if has_rom_extension and not entry_name.startswith('.'):
                    file_count += 1
                    # Get filename without extension for precise matching
                    stem = entry_name
                    if '.' in stem:
                        stem = '.'.join(stem.split('.')[:-1])  # Remove last extension
                    
                    # Use the same normalization as _normalize_name() for consistency
                    normalized_name = self._normalize_name(stem)
                    existing_roms.add(normalized_name)
                    
                    if len(existing_roms) <= 5:  # Log first 5 existing ROMs
                        logger.info(f"Found existing ROM: {entry_name}")
                    elif len(existing_roms) % 50 == 0:  # Log progress every 50 ROMs
                        logger.info(f"Found {len(existing_roms)} existing ROMs so far...")
            
            process_time = time.time() - process_start
            total_time = time.time() - iterdir_start
            logger.info(f"Entry processing completed in {process_time:.2f}s")
            logger.info(f"Total scan time: {total_time:.2f}s, processed {len(entries)} entries, found {len(existing_roms)} ROM files")
            
        except PermissionError as e:
            logger.error(f"Permission denied accessing {target_directory}: {e}")
        except OSError as e:
            logger.error(f"OS error scanning existing ROMs in {target_directory}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning existing ROMs in {target_directory}: {e}", exc_info=True)
        
        total_time = time.time() - start_time
        logger.info(f"Existing ROM scan completed in {total_time:.2f}s")
        return existing_roms
    
    def is_rom_installed(self, rom: RomInfo, target_directory: Path, _extract_archives: bool = False) -> bool:
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
        
        # Clear cache if directory changed
        if self._cache_directory != target_directory:
            logger.debug(f"Directory changed, clearing installed ROM cache")
            self._installed_cache.clear()
            self._directory_cache.clear()
            self._cache_directory = target_directory
            self._directory_cache_time = None
        
        normalized_name = self._normalize_name(rom.clean_name)
        
        # Check cache first
        if normalized_name in self._installed_cache:
            logger.debug(f"Using cached result for ROM: {rom.clean_name}")
            return self._installed_cache[normalized_name]
        
        logger.debug(f"Checking installed status for ROM: {rom.clean_name} (normalized: {normalized_name})")
        
        # Use a more efficient approach for network drives
        rom_extensions = ['.rvz', '.zip', '.7z', '.iso', '.gcm', '.bin', '.cue', '.chd', 
                         '.n64', '.z64', '.v64', '.nes', '.sfc', '.smc', '.gba', '.gbc', '.gb', 
                         '.nds', '.vb', '.pce', '.a26', '.a52', '.a78', '.cdi', '.gdi', '.wux', '.wud']
        
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
                    rom_extensions_set = {ext.lower() for ext in rom_extensions}
                    
                    # Scan directory once and cache all ROM file info
                    for file_path in target_directory.iterdir():
                        file_name = file_path.name
                        # Check extension first to avoid expensive network calls
                        if file_name.lower().endswith(tuple(rom_extensions_set)):
                            try:
                                # Get file info and cache it by normalized name
                                file_normalized = self._normalize_name(file_path.stem)
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
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"