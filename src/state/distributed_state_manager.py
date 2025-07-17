"""
Distributed state manager for better performance with large game libraries.

This manager stores:
- Each platform's game library in separate files: state/platforms/<platform>.json
- User selections in a separate file: state/selections.json
- App settings in: state/app_settings.json
"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import asdict

from src.models.game_library import GameLibrary, Game, ROM, UserSelection

logger = logging.getLogger(__name__)


class DistributedStateManager:
    """Manages persistent state with distributed files for better performance"""
    
    def __init__(self, state_dir: Path = None):
        self.state_dir = state_dir or Path('state')
        self.platforms_dir = self.state_dir / 'platforms'
        self.selections_file = self.state_dir / 'selections.json'
        self.app_settings_file = self.state_dir / 'app_settings.json'
        
        # Create directories if they don't exist
        self.state_dir.mkdir(exist_ok=True)
        self.platforms_dir.mkdir(exist_ok=True)
        
        # In-memory state (only for currently loaded platform)
        self.current_platform: Optional[str] = None
        self.platform_library: Optional[GameLibrary] = None
        self.selections: Dict[str, UserSelection] = {}
        self.app_settings: Dict[str, Any] = {}
        
        # Dirty flags for saving
        self.platform_dirty = False
        self.selections_dirty = False
        self.settings_dirty = False
        
        # Load app settings and selections
        self.load_app_settings()
        self.load_selections()
    
    def load_app_settings(self) -> bool:
        """Load application settings"""
        try:
            if self.app_settings_file.exists():
                with open(self.app_settings_file, 'r') as f:
                    self.app_settings = json.load(f)
                logger.debug(f"Loaded app settings: {len(self.app_settings)} settings")
                return True
            else:
                # Create default settings
                self.app_settings = {
                    'version': '3.0',
                    'created': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                self.save_app_settings()
                return True
        except Exception as e:
            logger.error(f"Failed to load app settings: {e}")
            self.app_settings = {}
            return False
    
    def save_app_settings(self) -> bool:
        """Save application settings"""
        if not self.settings_dirty:
            return True
        
        try:
            self.app_settings['last_updated'] = datetime.now().isoformat()
            
            with open(self.app_settings_file, 'w') as f:
                json.dump(self.app_settings, f, indent=2, default=self._json_serializer)
            
            self.settings_dirty = False
            logger.debug("Saved app settings")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save app settings: {e}")
            return False
    
    def load_selections(self) -> bool:
        """Load all user selections"""
        try:
            if self.selections_file.exists():
                with open(self.selections_file, 'r') as f:
                    data = json.load(f)
                
                # Convert dictionary data to UserSelection objects
                self.selections = {}
                for key, selection_data in data.get('selections', {}).items():
                    selection = UserSelection(**selection_data)
                    self.selections[key] = selection
                
                logger.info(f"Loaded {len(self.selections)} user selections")
                return True
            else:
                self.selections = {}
                self.save_selections()  # Create empty file
                return True
                
        except Exception as e:
            logger.error(f"Failed to load selections: {e}")
            self.selections = {}
            return False
    
    def save_selections(self) -> bool:
        """Save all user selections"""
        if not self.selections_dirty:
            return True
        
        try:
            # Create backup
            backup_file = self.selections_file.with_suffix('.json.bak')
            if self.selections_file.exists():
                shutil.copy2(self.selections_file, backup_file)
            
            # Prepare data for serialization
            data = {
                'version': '3.0',
                'timestamp': datetime.now().isoformat(),
                'selections': {
                    key: asdict(selection) 
                    for key, selection in self.selections.items()
                }
            }
            
            # Atomic write
            temp_file = self.selections_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
            
            shutil.move(temp_file, self.selections_file)
            
            self.selections_dirty = False
            logger.debug(f"Saved {len(self.selections)} user selections")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save selections: {e}")
            # Clean up temp file
            temp_file = self.selections_file.with_suffix('.json.tmp')
            if temp_file.exists():
                temp_file.unlink()
            return False
    
    def load_platform_library(self, platform: str) -> bool:
        """Load game library for a specific platform"""
        try:
            platform_file = self.platforms_dir / f"{platform}.json"
            
            if platform_file.exists():
                with open(platform_file, 'r') as f:
                    data = json.load(f)
                
                # Deserialize platform library
                library = self._deserialize_platform_library(data)
                
                self.current_platform = platform
                self.platform_library = library
                self.platform_dirty = False
                
                logger.info(f"Loaded platform {platform}: {len(library.games)} games")
                return True
            else:
                # Create empty library for new platform
                self.current_platform = platform
                self.platform_library = GameLibrary()
                self.platform_dirty = False
                
                logger.info(f"Created new library for platform {platform}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load platform library for {platform}: {e}")
            return False
    
    def save_platform_library(self, platform: str = None) -> bool:
        """Save game library for the current or specified platform"""
        if platform is None:
            platform = self.current_platform
        
        if not platform or not self.platform_library:
            return True
        
        if not self.platform_dirty:
            return True
        
        try:
            platform_file = self.platforms_dir / f"{platform}.json"
            
            # Create backup
            backup_file = platform_file.with_suffix('.json.bak')
            if platform_file.exists():
                shutil.copy2(platform_file, backup_file)
            
            # Serialize platform library
            data = self._serialize_platform_library(self.platform_library, platform)
            
            # Atomic write
            temp_file = platform_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
            
            shutil.move(temp_file, platform_file)
            
            self.platform_dirty = False
            logger.info(f"Saved platform {platform}: {len(self.platform_library.games)} games")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save platform library for {platform}: {e}")
            # Clean up temp file
            temp_file = platform_file.with_suffix('.json.tmp')
            if temp_file.exists():
                temp_file.unlink()
            return False
    
    def _serialize_platform_library(self, library: GameLibrary, platform: str) -> Dict[str, Any]:
        """Serialize platform-specific game library"""
        return {
            'version': '3.0',
            'platform': platform,
            'timestamp': datetime.now().isoformat(),
            'games': {
                key: self._serialize_game(game) 
                for key, game in library.games.items()
            },
            'tag_registry': list(library.tag_registry.get(platform, set())),
            'stats': {
                'total_games': len(library.games),
                'total_roms': sum(len(game.variants) for game in library.games.values())
            }
        }
    
    def _serialize_game(self, game: Game) -> Dict[str, Any]:
        """Serialize a Game object"""
        return {
            'key': game.key,
            'display_name': game.display_name,
            'platforms': list(game.platforms),
            'variants': {
                variant_key: asdict(rom) 
                for variant_key, rom in game.variants.items()
            }
        }
    
    def _deserialize_platform_library(self, data: Dict[str, Any]) -> GameLibrary:
        """Deserialize platform-specific game library"""
        library = GameLibrary()
        
        # Reconstruct games
        games_data = data.get('games', {})
        for game_key, game_data in games_data.items():
            game = self._deserialize_game(game_data)
            library.games[game_key] = game
        
        # Reconstruct tag registry for this platform
        platform = data.get('platform', 'unknown')
        tags = data.get('tag_registry', [])
        library.tag_registry[platform] = set(tags)
        
        return library
    
    def _deserialize_game(self, game_data: Dict[str, Any]) -> Game:
        """Deserialize a Game object"""
        game = Game(
            key=game_data['key'],
            display_name=game_data['display_name'],
            platforms=set(game_data['platforms'])
        )
        
        # Reconstruct ROM variants
        variants_data = game_data.get('variants', {})
        for variant_key, rom_data in variants_data.items():
            # Convert tags back to set
            if 'tags' in rom_data:
                rom_data['tags'] = set(rom_data['tags'])
            
            rom = ROM(**rom_data)
            game.variants[variant_key] = rom
        
        return game
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for special types"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, Path):
            return str(obj)
        else:
            return str(obj)
    
    # Public API methods (compatible with TransactionalStateManager)
    def add_game(self, game: Game):
        """Add or update a game in the current platform library"""
        if not self.platform_library:
            logger.error("No platform library loaded")
            return
        
        self.platform_library.add_game(game)
        self.platform_dirty = True
        # Note: Don't auto-save games immediately as they're often added in batches
    
    def get_games_for_platform(self, platform: str) -> List[Game]:
        """Get all games available for a specific platform"""
        if platform != self.current_platform:
            # Load the platform if it's different
            self.save_if_dirty()  # Save current platform first
            self.load_platform_library(platform)
        
        if self.platform_library:
            return list(self.platform_library.games.values())
        return []
    
    def get_platform_tags(self, platform: str) -> Set[str]:
        """Get all unique tags for a platform"""
        if platform != self.current_platform:
            # Load the platform if it's different
            self.save_if_dirty()  # Save current platform first
            self.load_platform_library(platform)
        
        if self.platform_library:
            return self.platform_library.tag_registry.get(platform, set())
        return set()
    
    def select_rom_variant(self, game_key: str, platform: str, variant_key: str):
        """Record user's selection for a game variant"""
        selection_key = f"{platform}:{game_key}"
        selection = UserSelection(
            game_key=game_key,
            platform=platform,
            selected_rom_variant=variant_key,
            timestamp=datetime.now()
        )
        self.selections[selection_key] = selection
        self.selections_dirty = True
        self.save_selections()  # Auto-save selections
    
    def get_selection(self, game_key: str, platform: str) -> Optional[UserSelection]:
        """Get user's selection for a game on a platform"""
        selection_key = f"{platform}:{game_key}"
        return self.selections.get(selection_key)
    
    def get_selections_for_platform(self, platform: str) -> List[UserSelection]:
        """Get all selections for a platform"""
        return [s for s in self.selections.values() if s.platform == platform]
    
    def get_selected_roms(self, platform: str) -> List[ROM]:
        """Get all ROMs selected by user for a platform"""
        if platform != self.current_platform:
            self.save_if_dirty()
            self.load_platform_library(platform)
        
        if not self.platform_library:
            return []
        
        selected_roms = []
        platform_selections = self.get_selections_for_platform(platform)
        
        for selection in platform_selections:
            game = self.platform_library.games.get(selection.game_key)
            if game:
                rom = game.variants.get(selection.selected_rom_variant)
                if rom:
                    selected_roms.append(rom)
        
        return selected_roms
    
    def clear_platform_selections(self, platform: str):
        """Clear all selections for a platform"""
        keys_to_remove = [
            key for key in self.selections.keys()
            if key.startswith(f"{platform}:")
        ]
        
        for key in keys_to_remove:
            del self.selections[key]
        
        self.selections_dirty = True
    
    def clear_all_selections(self):
        """Clear all user selections"""
        self.selections.clear()
        self.selections_dirty = True
    
    def save_if_dirty(self) -> bool:
        """Save all dirty state components"""
        success = True
        
        if self.platform_dirty:
            success &= self.save_platform_library()
        
        if self.selections_dirty:
            success &= self.save_selections()
        
        if self.settings_dirty:
            success &= self.save_app_settings()
        
        return success
    
    def get_available_platforms(self) -> List[str]:
        """Get list of platforms that have saved data"""
        platforms = []
        
        if self.platforms_dir.exists():
            for file_path in self.platforms_dir.glob("*.json"):
                if not file_path.name.endswith('.bak') and not file_path.name.endswith('.tmp'):
                    platform = file_path.stem
                    platforms.append(platform)
        
        return sorted(platforms)
    
    def get_platform_stats(self, platform: str) -> Dict[str, Any]:
        """Get statistics for a platform without fully loading it"""
        try:
            platform_file = self.platforms_dir / f"{platform}.json"
            
            if not platform_file.exists():
                return {'exists': False}
            
            with open(platform_file, 'r') as f:
                data = json.load(f)
            
            stats = data.get('stats', {})
            stats.update({
                'exists': True,
                'file_size': platform_file.stat().st_size,
                'last_modified': datetime.fromtimestamp(platform_file.stat().st_mtime).isoformat(),
                'timestamp': data.get('timestamp', 'unknown')
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats for platform {platform}: {e}")
            return {'exists': False, 'error': str(e)}
    

    # App settings proxy methods
    def get_app_setting(self, key: str, default: Any = None) -> Any:
        """Get an application setting"""
        return self.app_settings.get(key, default)
    
    def set_app_setting(self, key: str, value: Any):
        """Set an application setting"""
        self.app_settings[key] = value
        self.settings_dirty = True
    
    def get_last_selected_platform(self) -> Optional[str]:
        """Get the last selected platform"""
        return self.get_app_setting('last_selected_platform')
    
    def set_last_selected_platform(self, platform: str):
        """Set the last selected platform"""
        self.set_app_setting('last_selected_platform', platform)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        platforms = self.get_available_platforms()
        total_selections = len(self.selections)
        
        platform_stats = {}
        total_games = 0
        total_roms = 0
        
        for platform in platforms:
            stats = self.get_platform_stats(platform)
            platform_stats[platform] = stats
            total_games += stats.get('total_games', 0)
            total_roms += stats.get('total_roms', 0)
        
        return {
            'total_platforms': len(platforms),
            'total_games': total_games,
            'total_roms': total_roms,
            'total_selections': total_selections,
            'platforms': platform_stats,
            'state_directory': str(self.state_dir),
            'current_platform': self.current_platform
        }
    
    def __enter__(self):
        """Context manager entry - disable auto-save for batch operations"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save if no exception"""
        if exc_type is None:
            self.save_if_dirty()
        else:
            logger.warning(f"Exception in distributed state transaction: {exc_val}")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.save_if_dirty()
        except:
            pass  # Don't raise exceptions in destructor 