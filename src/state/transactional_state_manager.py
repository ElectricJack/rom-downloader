"""
Transactional state manager for persistent game library and user selections.
"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict, fields

from models.game_library import GameLibrary, Game, ROM, UserSelection

logger = logging.getLogger(__name__)


class TransactionalStateManager:
    """Manages persistent state with full transaction support"""
    
    def __init__(self, state_file: Path = None):
        self.state_file = state_file or Path('game_library.json')
        self.backup_file = self.state_file.with_suffix('.json.bak')
        self.temp_file = self.state_file.with_suffix('.json.tmp')
        
        self.library = GameLibrary()
        self.app_settings = {}
        self.dirty = False
        self.auto_save = True
        
        # Load existing state if available
        self.load()
    
    def load(self) -> bool:
        """Load state from disk with fallback to backup"""
        try:
            if self.state_file.exists():
                return self._load_from_file(self.state_file)
            elif self.backup_file.exists():
                logger.warning(f"Primary state file not found, loading from backup: {self.backup_file}")
                return self._load_from_file(self.backup_file)
            else:
                logger.info("No existing state file found, starting with empty library")
                return True
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False
    
    def _load_from_file(self, file_path: Path) -> bool:
        """Load state from a specific file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Validate version compatibility
            version = data.get('version', '1.0')
            if not self._is_compatible_version(version):
                logger.error(f"Incompatible state file version: {version}")
                return False
            
            # Reconstruct GameLibrary
            self.library = self._deserialize_library(data)
            self.dirty = False
            
            logger.info(f"Loaded state from {file_path}: {len(self.library.games)} games, {len(self.library.selections)} selections")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load state from {file_path}: {e}")
            return False
    
    def save(self) -> bool:
        """Save state to disk with atomic write and backup"""
        if not self.dirty:
            return True
        
        try:
            # Serialize library to data
            data = self._serialize_library()
            
            # Atomic write using temp file
            with open(self.temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
            
            # Create backup if original exists
            if self.state_file.exists():
                shutil.copy2(self.state_file, self.backup_file)
            
            # Move temp file to final location
            shutil.move(self.temp_file, self.state_file)
            
            self.dirty = False
            logger.info(f"Saved state to {self.state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            # Clean up temp file
            if self.temp_file.exists():
                self.temp_file.unlink()
            return False
    
    def save_if_dirty(self) -> bool:
        """Save state only if changes were made"""
        if self.dirty:
            return self.save()
        return True
    
    def _serialize_library(self) -> Dict[str, Any]:
        """Serialize GameLibrary to dictionary"""
        return {
            'version': '2.0',
            'timestamp': datetime.now().isoformat(),
            'app_settings': getattr(self, 'app_settings', {}),
            'games': {
                key: self._serialize_game(game) 
                for key, game in self.library.games.items()
            },
            'selections': {
                key: asdict(selection) 
                for key, selection in self.library.selections.items()
            },
            'tag_registry': {
                platform: list(tags) 
                for platform, tags in self.library.tag_registry.items()
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
    
    def _deserialize_library(self, data: Dict[str, Any]) -> GameLibrary:
        """Deserialize dictionary to GameLibrary"""
        library = GameLibrary()
        
        # Load app settings
        self.app_settings = data.get('app_settings', {})
        
        # Reconstruct games
        games_data = data.get('games', {})
        for game_key, game_data in games_data.items():
            game = self._deserialize_game(game_data)
            library.games[game_key] = game
        
        # Reconstruct selections
        selections_data = data.get('selections', {})
        for selection_key, selection_data in selections_data.items():
            selection = UserSelection(**selection_data)
            library.selections[selection_key] = selection
        
        # Reconstruct tag registry
        tag_registry_data = data.get('tag_registry', {})
        for platform, tags in tag_registry_data.items():
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
    
    def _is_compatible_version(self, version: str) -> bool:
        """Check if state file version is compatible"""
        # For now, accept all versions
        return True
    
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
    
    # GameLibrary proxy methods
    def add_game(self, game: Game):
        """Add or update a game in the library"""
        self.library.add_game(game)
        self.dirty = True
        if self.auto_save:
            self.save_if_dirty()
    
    def get_games_for_platform(self, platform: str) -> List[Game]:
        """Get all games available for a specific platform"""
        return self.library.get_games_for_platform(platform)
    
    def get_platform_tags(self, platform: str) -> set:
        """Get all unique tags for a platform"""
        return self.library.get_platform_tags(platform)
    
    def select_rom_variant(self, game_key: str, platform: str, variant_key: str):
        """Record user's selection for a game variant"""
        self.library.select_rom_variant(game_key, platform, variant_key)
        self.dirty = True
        if self.auto_save:
            self.save_if_dirty()
    
    def get_selection(self, game_key: str, platform: str) -> Optional[UserSelection]:
        """Get user's selection for a game on a platform"""
        return self.library.get_selection(game_key, platform)
    
    def get_selections_for_platform(self, platform: str) -> List[UserSelection]:
        """Get all selections for a platform"""
        return self.library.get_selections_for_platform(platform)
    
    def get_selected_roms(self, platform: str) -> List[ROM]:
        """Get all ROMs selected by user for a platform"""
        return self.library.get_selected_roms(platform)
    
    def filter_games_by_tags(self, platform: str, required_tags: set, 
                           exclude_tags: set = None) -> List[Game]:
        """Filter games by tags"""
        return self.library.filter_games_by_tags(platform, required_tags, exclude_tags)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        stats = self.library.get_stats()
        stats.update({
            'state_file': str(self.state_file),
            'backup_exists': self.backup_file.exists(),
            'dirty': self.dirty,
            'auto_save': self.auto_save
        })
        return stats
    
    def clear_platform_selections(self, platform: str):
        """Clear all selections for a platform"""
        keys_to_remove = [
            key for key in self.library.selections.keys() 
            if key.startswith(f"{platform}:")
        ]
        
        for key in keys_to_remove:
            del self.library.selections[key]
        
        self.dirty = True
        if self.auto_save:
            self.save_if_dirty()
    
    def clear_all_selections(self):
        """Clear all user selections"""
        self.library.selections.clear()
        self.dirty = True
        if self.auto_save:
            self.save_if_dirty()
    
    def export_selections(self, platform: str, output_file: Path):
        """Export selections for a platform to a file"""
        selections = self.get_selections_for_platform(platform)
        
        export_data = {
            'platform': platform,
            'timestamp': datetime.now().isoformat(),
            'selections': [asdict(selection) for selection in selections]
        }
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=self._json_serializer)
    
    def import_selections(self, input_file: Path) -> bool:
        """Import selections from a file"""
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)
            
            platform = data.get('platform')
            if not platform:
                logger.error("Import file missing platform information")
                return False
            
            selections_data = data.get('selections', [])
            
            for selection_data in selections_data:
                selection = UserSelection(**selection_data)
                selection_key = f"{platform}:{selection.game_key}"
                self.library.selections[selection_key] = selection
            
            self.dirty = True
            if self.auto_save:
                self.save_if_dirty()
            
            logger.info(f"Imported {len(selections_data)} selections for platform {platform}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import selections: {e}")
            return False
    
    def backup_state(self, backup_path: Path) -> bool:
        """Create a backup of the current state"""
        try:
            if self.state_file.exists():
                shutil.copy2(self.state_file, backup_path)
                logger.info(f"Created backup at {backup_path}")
                return True
            else:
                logger.warning("No state file to backup")
                return False
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore state from a backup file"""
        try:
            if backup_path.exists():
                # Create backup of current state first
                if self.state_file.exists():
                    current_backup = self.state_file.with_suffix('.json.pre_restore')
                    shutil.copy2(self.state_file, current_backup)
                
                # Restore from backup
                shutil.copy2(backup_path, self.state_file)
                
                # Reload state
                success = self.load()
                if success:
                    logger.info(f"Restored state from {backup_path}")
                return success
            else:
                logger.error(f"Backup file not found: {backup_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.auto_save = False
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic save"""
        self.auto_save = True
        if exc_type is None:  # No exception occurred
            self.save_if_dirty()
        else:
            logger.warning(f"Exception occurred in transaction: {exc_val}")
    
    # App settings methods
    def get_app_setting(self, key: str, default: Any = None) -> Any:
        """Get an application setting"""
        return self.app_settings.get(key, default)
    
    def set_app_setting(self, key: str, value: Any):
        """Set an application setting"""
        self.app_settings[key] = value
        self.dirty = True
        if self.auto_save:
            self.save_if_dirty()
    
    def get_last_selected_platform(self) -> Optional[str]:
        """Get the last selected platform"""
        return self.get_app_setting('last_selected_platform')
    
    def set_last_selected_platform(self, platform: str):
        """Set the last selected platform"""
        self.set_app_setting('last_selected_platform', platform)
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'dirty') and self.dirty:
            try:
                self.save()
            except:
                pass  # Don't raise exceptions in destructor