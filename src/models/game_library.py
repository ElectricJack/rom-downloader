"""
Enhanced data models for game library management.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class ROM:
    """Represents a specific ROM variant"""
    filename: str
    url: str
    size: str
    file_type: str
    tags: Set[str] = field(default_factory=set)
    platform: str = ""
    game_key: str = ""
    clean_name: str = ""  # Cleaned filename for display
    _installed_filename: Optional[str] = field(default=None, init=False)  # Actual installed filename on disk
    is_installed_only: bool = False  # True if ROM is only available locally, not online
    
    def __post_init__(self):
        """Ensure tags is always a set"""
        if isinstance(self.tags, (list, tuple)):
            self.tags = set(self.tags)
        
        # Generate clean_name if not provided
        if not self.clean_name:
            self.clean_name = self._generate_clean_name()
    
    def _generate_clean_name(self) -> str:
        """Generate a clean name from filename for display purposes"""
        import re
        
        # Remove file extensions (all supported ROM and archive formats)
        clean = re.sub(r'\.(rvz|zip|7z|iso|bin|cue|chd|gcm|nes|sfc|smc|gba|gbc|gb|nds|n64|z64|v64|vb|pce|a26|a52|a78|cdi|gdi|wux|wud)$', '', self.filename, flags=re.IGNORECASE)
        
        # Remove common prefixes/suffixes but keep region info
        clean = re.sub(r'^\[.*?\]\s*', '', clean)  # Remove [tags] at start
        # Remove non-region parenthetical info (keep region patterns)
        region_patterns = [r'\(USA?\)', r'\(US\)', r'\(Europe?\)', r'\(Japan\)', r'\(World\)', r'\(En\)', r'\(English\)']
        has_region = any(re.search(pattern, clean, re.IGNORECASE) for pattern in region_patterns)
        
        if not has_region:
            # Only remove parentheses if no region found
            clean = re.sub(r'\s*\(.*?\)$', '', clean)
        
        return clean.strip()
    
    @property
    def size_bytes(self) -> int:
        """Convert size string to bytes for comparison"""
        if not self.size:
            return 0
        
        # Parse size strings like "1.5GB", "512MB", etc.
        size_str = self.size.upper().replace(' ', '')
        
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }
        
        for unit, multiplier in multipliers.items():
            if size_str.endswith(unit):
                try:
                    number = float(size_str[:-len(unit)])
                    return int(number * multiplier)
                except ValueError:
                    pass
        
        return 0
    
    def has_tag(self, tag: str) -> bool:
        """Check if ROM has a specific tag (case-insensitive)"""
        return tag.lower() in {t.lower() for t in self.tags}
    
    def create_variant_key(self) -> str:
        """Create unique key for this ROM variant"""
        sorted_tags = sorted(self.tags)
        tag_string = '_'.join(sorted_tags) if sorted_tags else 'no_tags'
        return f"{self.file_type}_{tag_string}"
    
    def is_installed(self) -> Optional[bool]:
        """Get installation status derived from installed filename"""
        if self._installed_filename is None:
            return None  # Status unknown/not cached
        return self._installed_filename != ""  # Empty string means checked but not installed
    
    def set_installed(self, installed: bool, installed_filename: str = None):
        """Set installation status by setting the actual installed filename"""
        if installed and installed_filename:
            self._installed_filename = installed_filename
        elif installed and not installed_filename:
            # Installed but no filename provided - this shouldn't happen in new code
            # but maintain backward compatibility
            self._installed_filename = "unknown"
        else:
            # Not installed
            self._installed_filename = ""
    
    def get_installed_filename(self) -> Optional[str]:
        """Get the actual installed filename if available"""
        return self._installed_filename
    
    def clear_installation_cache(self):
        """Clear cached installation status by clearing installed filename"""
        self._installed_filename = None


@dataclass
class Game:
    """Represents a unique game with multiple ROM variants"""
    key: str
    display_name: str
    platforms: Set[str] = field(default_factory=set)
    variants: Dict[str, ROM] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure platforms is always a set"""
        if isinstance(self.platforms, (list, tuple)):
            self.platforms = set(self.platforms)
    
    def add_variant(self, rom: ROM):
        """Add a ROM variant to this game"""
        variant_key = rom.create_variant_key()
        self.variants[variant_key] = rom
        self.platforms.add(rom.platform)
        rom.game_key = self.key
    
    def get_variants_for_platform(self, platform: str) -> List[ROM]:
        """Get all ROM variants for a specific platform"""
        return [rom for rom in self.variants.values() if rom.platform == platform]
    
    def get_best_variant(self, platform: str, preferred_tags: List[str] = None) -> Optional[ROM]:
        """Get the best ROM variant for a platform based on preferences"""
        variants = self.get_variants_for_platform(platform)
        if not variants:
            return None
        
        if not preferred_tags:
            return variants[0]
        
        # Score variants based on preferred tags
        def score_variant(rom: ROM) -> int:
            score = 0
            for i, tag in enumerate(preferred_tags):
                if rom.has_tag(tag):
                    score += len(preferred_tags) - i  # Higher score for earlier preferences
            return score
        
        return max(variants, key=score_variant)
    
    def get_all_tags(self) -> Set[str]:
        """Get all unique tags across all variants"""
        all_tags = set()
        for rom in self.variants.values():
            all_tags.update(rom.tags)
        return all_tags
    
    def get_installed_variants(self, platform: str) -> List[ROM]:
        """Get all installed variants for a platform (using cached status)"""
        variants = self.get_variants_for_platform(platform)
        return [rom for rom in variants if rom.is_installed() is True]
    
    def has_installed_variants(self, platform: str) -> bool:
        """Check if any variants are installed for a platform (using cached status)"""
        return len(self.get_installed_variants(platform)) > 0
    
    def clear_installation_cache_for_platform(self, platform: str):
        """Clear installation cache for all variants of a platform"""
        for rom in self.get_variants_for_platform(platform):
            rom.clear_installation_cache()


@dataclass
class UserSelection:
    """Represents user's selection for a game"""
    game_key: str
    platform: str
    selected_rom_variant: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Ensure timestamp is a datetime object"""
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class GameLibrary:
    """Container for the complete game library"""
    games: Dict[str, Game] = field(default_factory=dict)
    tag_registry: Dict[str, Set[str]] = field(default_factory=dict)  # platform -> tags
    selections: Dict[str, UserSelection] = field(default_factory=dict)  # platform:game_key -> selection
    
    def add_game(self, game: Game):
        """Add or update a game in the library"""
        self.games[game.key] = game
        
        # Update tag registry
        for platform in game.platforms:
            if platform not in self.tag_registry:
                self.tag_registry[platform] = set()
            self.tag_registry[platform].update(game.get_all_tags())
    
    def get_games_for_platform(self, platform: str) -> List[Game]:
        """Get all games available for a specific platform"""
        games = [game for game in self.games.values() if platform in game.platforms]
        return sorted(games, key=lambda game: game.display_name.lower())
    
    def get_platform_tags(self, platform: str) -> Set[str]:
        """Get all unique tags for a platform"""
        return self.tag_registry.get(platform, set())
    
    def select_rom_variant(self, game_key: str, platform: str, variant_key: str):
        """Record user's selection for a game variant"""
        selection_key = f"{platform}:{game_key}"
        self.selections[selection_key] = UserSelection(
            game_key=game_key,
            platform=platform,
            selected_rom_variant=variant_key
        )
    
    def get_selection(self, game_key: str, platform: str) -> Optional[UserSelection]:
        """Get user's selection for a game on a platform"""
        selection_key = f"{platform}:{game_key}"
        return self.selections.get(selection_key)
    
    def get_selections_for_platform(self, platform: str) -> List[UserSelection]:
        """Get all selections for a platform"""
        return [s for s in self.selections.values() if s.platform == platform]
    
    def get_selected_roms(self, platform: str) -> List[ROM]:
        """Get all ROMs selected by user for a platform"""
        selected_roms = []
        
        for selection in self.get_selections_for_platform(platform):
            game = self.games.get(selection.game_key)
            if game:
                rom = game.variants.get(selection.selected_rom_variant)
                if rom:
                    selected_roms.append(rom)
        
        return selected_roms
    
    def filter_games_by_tags(self, platform: str, required_tags: Set[str], 
                           exclude_tags: Set[str] = None) -> List[Game]:
        """Filter games by tags"""
        if exclude_tags is None:
            exclude_tags = set()
        
        filtered_games = []
        platform_games = self.get_games_for_platform(platform)
        
        for game in platform_games:
            game_tags = game.get_all_tags()
            
            # Check if game has all required tags
            if required_tags and not required_tags.issubset(game_tags):
                continue
            
            # Check if game has any excluded tags
            if exclude_tags and exclude_tags.intersection(game_tags):
                continue
            
            filtered_games.append(game)
        
        return filtered_games
    
    def get_stats(self) -> Dict[str, any]:
        """Get library statistics"""
        total_games = len(self.games)
        total_roms = sum(len(game.variants) for game in self.games.values())
        platforms = set()
        for game in self.games.values():
            platforms.update(game.platforms)
        
        return {
            'total_games': total_games,
            'total_roms': total_roms,
            'platforms': sorted(platforms),
            'platform_count': len(platforms),
            'total_selections': len(self.selections)
        }