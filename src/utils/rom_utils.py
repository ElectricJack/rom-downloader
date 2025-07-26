"""
ROM Utilities - Centralized ROM name handling and extension management.

This module provides utilities for:
- ROM name normalization and cleaning
- Extension handling from platform configuration
- Consistent ROM file identification across the application
"""

import re
import json
import logging
from pathlib import Path
from typing import Set, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class RomUtils:
    """Centralized utilities for ROM name handling and extension management."""
    
    _instance = None
    _extensions_cache = None
    _config_path = None
    
    def __new__(cls, config_path: Optional[Path] = None):
        """Singleton pattern to ensure consistent extension handling."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize ROM utilities with platform configuration.
        
        Args:
            config_path: Path to platforms.json configuration file
        """
        if config_path is None:
            # Default to config/platforms.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "platforms.json"
        
        # Only reload if config path changed
        if self._config_path != config_path:
            self._config_path = config_path
            self._extensions_cache = None
    
    @lru_cache(maxsize=1)
    def get_all_rom_extensions(self) -> Set[str]:
        """Get all ROM extensions from platform configuration.
        
        Returns:
            Set of all ROM file extensions (including compound extensions like .xiso.iso)
        """
        if self._extensions_cache is not None:
            return self._extensions_cache
        
        extensions = set()
        
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            platforms = config.get('platforms', {})
            
            for platform_name, platform_config in platforms.items():
                platform_extensions = platform_config.get('file_extensions', [])
                for ext in platform_extensions:
                    # Ensure extensions start with a dot
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    extensions.add(ext.lower())
            
            # Add Xbox compound extension that gets created during processing
            extensions.add('.xiso.iso')
            
            logger.info(f"Loaded {len(extensions)} ROM extensions from {len(platforms)} platforms")
            logger.debug(f"ROM extensions: {sorted(extensions)}")
            
        except Exception as e:
            logger.error(f"Error loading ROM extensions from {self._config_path}: {e}")
            # Fallback to common extensions
            extensions = {
                '.xiso.iso', '.zip', '.7z', '.rar', '.chd', '.cdi', '.gdi', '.bin', '.cue', '.iso',
                '.rvz', '.wux', '.wud', '.gba', '.gbc', '.gb', '.nes', '.sfc', '.smc',
                '.n64', '.z64', '.v64', '.nds', '.vb', '.a26', '.a52', '.a78', '.pce'
            }
            logger.warning(f"Using fallback ROM extensions: {len(extensions)} extensions")
        
        self._extensions_cache = extensions
        return extensions
    
    def get_rom_extensions_list(self) -> List[str]:
        """Get ROM extensions as a sorted list.
        
        Returns:
            Sorted list of ROM file extensions
        """
        return sorted(self.get_all_rom_extensions())
    
    def is_rom_file(self, filename: str) -> bool:
        """Check if a filename has a ROM extension.
        
        Args:
            filename: The filename to check
            
        Returns:
            True if the file has a ROM extension
        """
        filename_lower = filename.lower()
        extensions = self.get_all_rom_extensions()
        
        # Check for compound extensions first (like .xiso.iso)
        compound_extensions = [ext for ext in extensions if '.' in ext[1:]]  # Extensions with multiple dots
        for ext in sorted(compound_extensions, key=len, reverse=True):  # Check longest first
            if filename_lower.endswith(ext):
                return True
        
        # Check single extensions
        single_extensions = [ext for ext in extensions if '.' not in ext[1:]]
        for ext in single_extensions:
            if filename_lower.endswith(ext):
                return True
        
        return False
    
    def normalize_rom_name(self, name: str) -> str:
        """Normalize a ROM name for comparison purposes.
        
        This method provides consistent ROM name normalization across the entire application.
        
        Args:
            name: Original ROM name
            
        Returns:
            Normalized name for grouping and comparison
        """
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove file extensions using the centralized extension list
        extensions = self.get_all_rom_extensions()
        
        # Sort by length (descending) to check compound extensions first
        sorted_extensions = sorted(extensions, key=len, reverse=True)
        
        for ext in sorted_extensions:
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
    
    def precise_normalize_rom_name(self, name: str) -> str:
        """Normalize ROM name while preserving region and revision information.
        
        Unlike normalize_rom_name(), this keeps parenthetical content that's important
        for distinguishing between ROM variants.
        
        Args:
            name: Original ROM name
            
        Returns:
            Precisely normalized name that preserves important distinguishing information
        """
        normalized = name.lower().strip()
        
        # Remove file extensions using the centralized extension list
        extensions = self.get_all_rom_extensions()
        
        # Sort by length (descending) to check compound extensions first
        sorted_extensions = sorted(extensions, key=len, reverse=True)
        
        for ext in sorted_extensions:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break
        
        # Normalize whitespace and separators but KEEP parenthetical content
        normalized = re.sub(r'\s*[-_]\s*', ' ', normalized)  # Normalize separators  
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize multiple spaces
        normalized = normalized.strip()
        
        return normalized
    
    def get_rom_stem(self, filename: str) -> str:
        """Get the stem (filename without extension) for a ROM file.
        
        Properly handles compound extensions like .xiso.iso
        
        Args:
            filename: The ROM filename
            
        Returns:
            Filename without ROM extension
        """
        filename_lower = filename.lower()
        extensions = self.get_all_rom_extensions()
        
        # Sort by length (descending) to check compound extensions first
        sorted_extensions = sorted(extensions, key=len, reverse=True)
        
        for ext in sorted_extensions:
            if filename_lower.endswith(ext):
                # Return original case but without extension
                return filename[:-len(ext)]
        
        # If no ROM extension found, return as-is
        return filename
    
    def generate_file_pattern_for_platform(self, platform_id: str) -> str:
        """Generate a regex file pattern from platform's file extensions.
        
        Args:
            platform_id: Platform identifier (e.g., 'Xbox', 'GameCube')
            
        Returns:
            Regex pattern string that matches the platform's file extensions
        """
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            platforms = config.get('platforms', {})
            platform_config = platforms.get(platform_id, {})
            extensions = platform_config.get('file_extensions', [])
            
            if not extensions:
                logger.warning(f"No file extensions found for platform {platform_id}")
                return ".*"
            
            # Clean extensions and remove dots
            clean_extensions = []
            for ext in extensions:
                clean_ext = ext.lower().lstrip('.')
                # Handle compound extensions like .xiso.iso
                clean_extensions.append(clean_ext.replace('.', r'\.'))
            
            # Create regex pattern: .*(ext1|ext2|ext3)$
            pattern = r".*\.(" + "|".join(clean_extensions) + r")$"
            
            logger.debug(f"Generated pattern for {platform_id}: {pattern}")
            return pattern
            
        except Exception as e:
            logger.error(f"Error generating file pattern for platform {platform_id}: {e}")
            return ".*"
    
    def get_all_platform_file_patterns(self) -> dict:
        """Get file patterns for all platforms.
        
        Returns:
            Dictionary mapping platform_id to file pattern
        """
        patterns = {}
        
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            platforms = config.get('platforms', {})
            
            for platform_id in platforms.keys():
                patterns[platform_id] = self.generate_file_pattern_for_platform(platform_id)
                
        except Exception as e:
            logger.error(f"Error getting all platform file patterns: {e}")
        
        return patterns
    
    def clear_cache(self):
        """Clear the extensions cache to force reload from configuration."""
        self._extensions_cache = None
        self.get_all_rom_extensions.cache_clear()
    
    def get_canonical_rom_name(self, filename: str) -> str:
        """Get the canonical ROM name - the key for all operations.
        
        This becomes the ONLY method used for:
        - Game key generation
        - ROM matching
        - Deduplication
        - Storage keys
        
        Args:
            filename: Original ROM filename
            
        Returns:
            Canonical ROM name for all identification operations
        """
        stem = self.get_rom_stem(filename)
        return self.normalize_rom_name(stem)


# Global instance for easy access
_rom_utils_instance = None

def get_rom_utils(config_path: Optional[Path] = None) -> RomUtils:
    """Get the global ROM utilities instance.
    
    Args:
        config_path: Optional path to platforms.json (only used on first call)
        
    Returns:
        RomUtils instance
    """
    global _rom_utils_instance
    if _rom_utils_instance is None:
        _rom_utils_instance = RomUtils(config_path)
    return _rom_utils_instance