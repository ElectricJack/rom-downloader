"""
Migration tool for converting legacy state format to new format.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime

from .state_manager import StateManager
from .transactional_state_manager import TransactionalStateManager
from models.game_library import Game, ROM, UserSelection, GameLibrary

logger = logging.getLogger(__name__)


class StateMigrationTool:
    """Tool for migrating legacy state format to new format"""
    
    def __init__(self):
        self.legacy_state_path = Path('state/app_state.json')
        self.new_state_path = Path('game_library.json')
        
    def needs_migration(self) -> bool:
        """Check if migration is needed"""
        return (self.legacy_state_path.exists() and 
                not self.new_state_path.exists())
    
    def migrate(self) -> bool:
        """Migrate legacy state to new format"""
        try:
            if not self.legacy_state_path.exists():
                logger.info("No legacy state file found, migration not needed")
                return True
                
            if self.new_state_path.exists():
                logger.info("New state file already exists, migration not needed")
                return True
            
            logger.info("Starting state migration from legacy format")
            
            # Load legacy state
            legacy_manager = StateManager(self.legacy_state_path)
            
            # Create new state manager
            new_manager = TransactionalStateManager(self.new_state_path)
            
            # Migrate platform selections
            migrated_count = 0
            for platform in legacy_manager.get_all_platforms():
                migrated_count += self._migrate_platform_selections(
                    legacy_manager, new_manager, platform
                )
            
            # Save new state
            new_manager.save()
            
            logger.info(f"Migration completed successfully: {migrated_count} selections migrated")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _migrate_platform_selections(self, legacy_manager: StateManager, 
                                   new_manager: TransactionalStateManager,
                                   platform: str) -> int:
        """Migrate selections for a specific platform"""
        
        # Get legacy selections
        legacy_selections = legacy_manager.load_platform_selections(platform)
        
        if not legacy_selections:
            return 0
        
        migrated_count = 0
        
        # Convert each selection to new format
        for rom_name in legacy_selections:
            try:
                # Create a basic game and ROM for migration
                game_key = self._normalize_game_name(rom_name)
                
                # Create a minimal ROM object
                rom = ROM(
                    filename=rom_name,
                    url="",  # URL will be populated when scanning
                    size="",
                    file_type=self._extract_file_type(rom_name),
                    platform=platform,
                    tags=self._extract_tags_from_filename(rom_name)
                )
                
                # Create game with this ROM
                game = Game(
                    key=game_key,
                    display_name=self._clean_display_name(rom_name),
                    platforms={platform}
                )
                
                # Add ROM variant to game
                variant_key = rom.create_variant_key()
                game.variants[variant_key] = rom
                
                # Add game to library
                new_manager.add_game(game)
                
                # Create selection
                new_manager.select_rom_variant(game_key, platform, variant_key)
                
                migrated_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to migrate ROM {rom_name}: {e}")
                continue
        
        return migrated_count
    
    def _normalize_game_name(self, rom_name: str) -> str:
        """Normalize ROM name to create game key"""
        # Remove file extension
        name = Path(rom_name).stem
        
        # Remove common ROM tags in parentheses and brackets
        import re
        name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
        name = re.sub(r'\s*\[[^\]]*\]\s*', ' ', name)
        
        # Clean up spacing and normalize
        name = ' '.join(name.split())
        
        return name.lower()
    
    def _clean_display_name(self, rom_name: str) -> str:
        """Clean ROM name for display"""
        # Remove file extension
        name = Path(rom_name).stem
        
        # Remove region tags but keep version info
        import re
        name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
        
        # Clean up spacing
        name = ' '.join(name.split())
        
        return name
    
    def _extract_file_type(self, filename: str) -> str:
        """Extract file type from filename"""
        return Path(filename).suffix.lower()
    
    def _extract_tags_from_filename(self, filename: str) -> Set[str]:
        """Extract tags from ROM filename"""
        import re
        
        tags = set()
        
        # Extract content from parentheses and brackets
        parentheses_content = re.findall(r'\(([^)]+)\)', filename)
        brackets_content = re.findall(r'\[([^\]]+)\]', filename)
        
        all_content = parentheses_content + brackets_content
        
        for content in all_content:
            # Split by common separators
            parts = re.split(r'[,;+&]', content)
            
            for part in parts:
                part = part.strip()
                if part:
                    tags.add(part)
        
        return tags
    
    def create_migration_backup(self) -> Optional[Path]:
        """Create backup of legacy state before migration"""
        if not self.legacy_state_path.exists():
            return None
            
        try:
            backup_path = self.legacy_state_path.with_suffix('.json.pre_migration')
            
            # Copy legacy state to backup
            import shutil
            shutil.copy2(self.legacy_state_path, backup_path)
            
            logger.info(f"Created migration backup at {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create migration backup: {e}")
            return None
    
    def validate_migration(self) -> bool:
        """Validate that migration was successful"""
        try:
            if not self.new_state_path.exists():
                logger.error("New state file not found after migration")
                return False
            
            # Try to load new state
            new_manager = TransactionalStateManager(self.new_state_path)
            stats = new_manager.get_stats()
            
            if stats['total_games'] == 0 and stats['total_selections'] == 0:
                # Check if legacy state had selections
                if self.legacy_state_path.exists():
                    legacy_manager = StateManager(self.legacy_state_path)
                    legacy_platforms = legacy_manager.get_all_platforms()
                    
                    if legacy_platforms:
                        # Had legacy data but no new data - migration failed
                        logger.error("Migration validation failed: no data in new format")
                        return False
            
            logger.info(f"Migration validation passed: {stats}")
            return True
            
        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            return False
    
    def rollback_migration(self) -> bool:
        """Rollback migration by restoring legacy state"""
        try:
            backup_path = self.legacy_state_path.with_suffix('.json.pre_migration')
            
            if not backup_path.exists():
                logger.error("No migration backup found for rollback")
                return False
            
            # Remove new state file
            if self.new_state_path.exists():
                self.new_state_path.unlink()
            
            # Restore legacy state from backup
            import shutil
            shutil.copy2(backup_path, self.legacy_state_path)
            
            logger.info("Migration rollback completed")
            return True
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return False
    
    def get_migration_summary(self) -> Dict:
        """Get summary of what would be migrated"""
        try:
            if not self.legacy_state_path.exists():
                return {'legacy_exists': False}
            
            legacy_manager = StateManager(self.legacy_state_path)
            platforms = legacy_manager.get_all_platforms()
            
            summary = {
                'legacy_exists': True,
                'platforms': {},
                'total_selections': 0
            }
            
            for platform in platforms:
                selections = legacy_manager.load_platform_selections(platform)
                summary['platforms'][platform] = len(selections)
                summary['total_selections'] += len(selections)
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get migration summary: {e}")
            return {'error': str(e)}


def migrate_if_needed():
    """Convenience function to migrate if needed"""
    migrator = StateMigrationTool()
    
    if migrator.needs_migration():
        logger.info("Legacy state detected, starting migration...")
        
        # Create backup
        backup_path = migrator.create_migration_backup()
        
        # Perform migration
        if migrator.migrate():
            # Validate migration
            if migrator.validate_migration():
                logger.info("Migration completed successfully")
                return True
            else:
                logger.error("Migration validation failed, rolling back...")
                migrator.rollback_migration()
                return False
        else:
            logger.error("Migration failed")
            return False
    else:
        logger.info("No migration needed")
        return True


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run migration
    success = migrate_if_needed()
    
    if success:
        print("Migration completed successfully")
    else:
        print("Migration failed")