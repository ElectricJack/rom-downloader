"""
Queue Manager for the ROM Downloader GUI

Handles all queue-related functionality including:
- Adding/removing games and variants to/from download queue
- Batch operations for multiple selections
- Tree selection management
- Queue state tracking and updates
"""

import logging
from typing import Set, List, Optional, Callable
from src.models.game_library import Game

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages download queue functionality for the game library GUI"""
    
    def __init__(self, parent_gui):
        """Initialize the queue manager
        
        Args:
            parent_gui: Reference to the main GameLibraryGUI instance
        """
        self.parent_gui = parent_gui
        
        # Callbacks
        self.on_queue_changed: Optional[Callable] = None
    
    def add_to_queue(self) -> None:
        """Add selected items to download queue via context menu"""
        selections = self.parent_gui.game_tree.selection()
        if not selections:
            return
        
        platform = self.parent_gui.get_current_platform_key()
        if not platform:
            return
        
        # Use batch mode to prevent auto-save during bulk operations
        with self.parent_gui.state_manager:
            # Track which games were modified for batch updates
            modified_games = set()
            
            # Process all selected items
            for item in selections:
                try:
                    item_type = self.parent_gui.game_tree.set(item, 'item_type')
                    game_key = self.parent_gui.game_tree.set(item, 'game_key')
                    variant_key = self.parent_gui.game_tree.set(item, 'variant_key')
                except:
                    continue
                
                if item_type == 'game':
                    if self.add_game_to_queue_batch(game_key, platform):
                        modified_games.add(game_key)
                elif item_type == 'variant':
                    if self.add_variant_to_queue_batch(game_key, platform, variant_key):
                        modified_games.add(game_key)
        
        # Update all modified games in batch
        self.parent_gui.update_game_tree_items_batch(modified_games, platform)
        self._notify_queue_changed()
    
    def add_game_to_queue_batch(self, game_key: str, platform: str) -> bool:
        """Add a game to download queue (batch operation, returns True if modified)"""
        # Find game
        game = self._find_game_by_key(game_key)
        if not game:
            return False
        
        # Check if already queued
        current_selection = self.parent_gui.state_manager.get_selection(game_key, platform)
        if current_selection:
            return False  # Already queued
        
        # Add to queue - pick best variant that's not installed-only
        variants = game.get_variants_for_platform(platform)
        # Filter out installed-only ROMs since they can't be downloaded
        downloadable_variants = [rom for rom in variants if not rom.is_installed_only]
        
        if downloadable_variants:
            # Create a temporary game with only downloadable variants to get best choice
            temp_game = Game(key=game.key, display_name=game.display_name, platforms=game.platforms)
            for variant in downloadable_variants:
                temp_game.add_variant(variant)
            
            best_variant = temp_game.get_best_variant(platform, self.parent_gui.config_manager.get_preferred_regions())
            if best_variant:
                variant_key = best_variant.create_variant_key()
                self.parent_gui.state_manager.select_rom_variant(game_key, platform, variant_key)
                return True
        elif variants:
            # Game has only installed-only ROMs
            logger.warning(f"Cannot queue game '{game.display_name}' - all variants are installed-only")
            return False
        
        return False
    
    def add_variant_to_queue_batch(self, game_key: str, platform: str, variant_key: str) -> bool:
        """Add a specific variant to download queue (batch operation, returns True if modified)"""
        # Find the ROM variant to check if it's installed-only
        game = self._find_game_by_key(game_key)
        if not game:
            return False
        
        rom_variant = game.variants.get(variant_key)
        if not rom_variant:
            return False
            
        # Prevent queueing installed-only ROMs
        if rom_variant.is_installed_only:
            logger.warning(f"Cannot queue installed-only ROM: {rom_variant.filename}")
            return False
        
        # Check if already queued with this variant
        current_selection = self.parent_gui.state_manager.get_selection(game_key, platform)
        if current_selection and current_selection.selected_rom_variant == variant_key:
            return False  # Already queued with this variant
        
        self.parent_gui.state_manager.select_rom_variant(game_key, platform, variant_key)
        return True
    
    def remove_from_queue(self) -> None:
        """Remove selected items from download queue via context menu"""
        selections = self.parent_gui.game_tree.selection()
        if not selections:
            return
        
        platform = self.parent_gui.get_current_platform_key()
        if not platform:
            return
        
        # Use batch mode to prevent auto-save during bulk operations
        with self.parent_gui.state_manager:
            # Process all selected items
            for item in selections:
                try:
                    item_type = self.parent_gui.game_tree.set(item, 'item_type')
                    game_key = self.parent_gui.game_tree.set(item, 'game_key')
                    variant_key = self.parent_gui.game_tree.set(item, 'variant_key')
                except:
                    continue
                
                if item_type in ['game', 'variant']:
                    # Remove from queue regardless of whether it's game or variant level
                    selection_key = f"{platform}:{game_key}"
                    if selection_key in self.parent_gui.state_manager.selections:
                        del self.parent_gui.state_manager.selections[selection_key]
                        self.parent_gui.state_manager.selections_dirty = True
        
        # Update all affected items in batch
        processed_games = set()
        for item in selections:
            try:
                game_key = self.parent_gui.game_tree.set(item, 'game_key')
                if game_key:
                    processed_games.add(game_key)
            except:
                continue
        
        # Use batch update for better performance
        self.parent_gui.update_game_tree_items_batch(processed_games, platform)
        self._notify_queue_changed()
    
    def add_all_variants_to_queue(self) -> None:
        """Add all variants of selected games to queue"""
        selections = self.parent_gui.game_tree.selection()
        if not selections:
            return
        
        platform = self.parent_gui.get_current_platform_key()
        if not platform:
            return
        
        # Process all selected items
        processed_games = set()
        for item in selections:
            try:
                game_key = self.parent_gui.game_tree.set(item, 'game_key')
                if game_key and game_key not in processed_games:
                    self.add_game_to_queue(game_key, platform)
                    processed_games.add(game_key)
            except:
                continue
        
        self._notify_queue_changed()
    
    def remove_all_variants_from_queue(self) -> None:
        """Remove all variants of selected games from queue"""
        # This is the same as regular remove for our current implementation
        self.remove_from_queue()
    
    def select_all_games(self) -> None:
        """Select all visible items in the tree (highlight all rows)"""
        # Get all items from the tree (games and variants)
        all_items = []
        for item_id in self.parent_gui.game_tree.get_children():
            all_items.append(item_id)
            # Also add child variants
            for child_id in self.parent_gui.game_tree.get_children(item_id):
                all_items.append(child_id)
        
        # Select all items in the tree
        if all_items:
            self.parent_gui.game_tree.selection_set(all_items)
    
    def select_none_games(self) -> None:
        """Clear all selected items in the tree (remove highlight from all rows)"""
        # Clear all tree selections
        self.parent_gui.game_tree.selection_remove(self.parent_gui.game_tree.selection())
    
    def add_game_to_queue(self, game_key: str, platform: str) -> None:
        """Add a game to download queue (selects best variant)"""
        if self.add_game_to_queue_batch(game_key, platform):
            self.parent_gui.state_manager.save_selections()
            self.parent_gui.update_game_tree_item(game_key, platform)
            self._notify_queue_changed()
    
    def add_variant_to_queue(self, game_key: str, platform: str, variant_key: str) -> None:
        """Add a specific variant to download queue"""
        if self.add_variant_to_queue_batch(game_key, platform, variant_key):
            self.parent_gui.state_manager.save_selections()
            self.parent_gui.update_game_tree_item(game_key, platform)
            self._notify_queue_changed()
    
    def remove_game_from_queue(self, game_key: str, platform: str) -> None:
        """Remove a specific game from the download queue"""
        selection_key = f"{platform}:{game_key}"
        if selection_key in self.parent_gui.state_manager.selections:
            del self.parent_gui.state_manager.selections[selection_key]
            self.parent_gui.state_manager.selections_dirty = True
            self.parent_gui.state_manager.save_selections()
            self.parent_gui.update_game_tree_item(game_key, platform)
            self._notify_queue_changed()
    
    def is_game_queued(self, game_key: str, platform: str) -> bool:
        """Check if a game is currently in the download queue"""
        selection = self.parent_gui.state_manager.get_selection(game_key, platform)
        return selection is not None
    
    def get_queued_games(self, platform: str) -> List[str]:
        """Get list of game keys that are currently queued for download"""
        queued_games = []
        for selection_key, selection in self.parent_gui.state_manager.selections.items():
            if selection_key.startswith(f"{platform}:"):
                game_key = selection_key.split(":", 1)[1]
                queued_games.append(game_key)
        return queued_games
    
    def get_queued_count(self, platform: str) -> int:
        """Get the number of games currently queued for download"""
        return len(self.get_queued_games(platform))
    
    def clear_all_queue(self, platform: str) -> None:
        """Clear all items from the download queue for a platform"""
        queued_games = self.get_queued_games(platform)
        if not queued_games:
            return
        
        # Use batch mode for efficiency
        with self.parent_gui.state_manager:
            for game_key in queued_games:
                selection_key = f"{platform}:{game_key}"
                if selection_key in self.parent_gui.state_manager.selections:
                    del self.parent_gui.state_manager.selections[selection_key]
                    self.parent_gui.state_manager.selections_dirty = True
        
        # Update tree items in batch
        self.parent_gui.update_game_tree_items_batch(set(queued_games), platform)
        self._notify_queue_changed()
    
    def queue_all_filtered_games(self) -> None:
        """Add all currently visible/filtered games to the queue"""
        platform = self.parent_gui.get_current_platform_key()
        if not platform:
            return
        
        # Get all visible game items
        game_keys = set()
        for item_id in self.parent_gui.game_tree.get_children():
            try:
                item_type = self.parent_gui.game_tree.set(item_id, 'item_type')
                if item_type == 'game':
                    game_key = self.parent_gui.game_tree.set(item_id, 'game_key')
                    if game_key:
                        game_keys.add(game_key)
            except:
                continue
        
        if not game_keys:
            return
        
        # Use batch mode for efficiency
        with self.parent_gui.state_manager:
            modified_games = set()
            for game_key in game_keys:
                if self.add_game_to_queue_batch(game_key, platform):
                    modified_games.add(game_key)
        
        # Update tree items in batch
        if modified_games:
            self.parent_gui.update_game_tree_items_batch(modified_games, platform)
            self._notify_queue_changed()
    
    def toggle_game_queue_status(self, game_key: str, platform: str) -> None:
        """Toggle a game's queue status (add if not queued, remove if queued)"""
        if self.is_game_queued(game_key, platform):
            self.remove_game_from_queue(game_key, platform)
        else:
            self.add_game_to_queue(game_key, platform)
    
    def get_queued_variant_key(self, game_key: str, platform: str) -> Optional[str]:
        """Get the variant key for a queued game, or None if not queued"""
        selection = self.parent_gui.state_manager.get_selection(game_key, platform)
        return selection.selected_rom_variant if selection else None
    
    def set_queue_changed_callback(self, callback: Callable) -> None:
        """Set the callback to call when queue state changes"""
        self.on_queue_changed = callback
    
    def _find_game_by_key(self, game_key: str) -> Optional[Game]:
        """Find a game by its key in the current games list"""
        for game in self.parent_gui.current_games:
            if game.key == game_key:
                return game
        return None
    
    def _notify_queue_changed(self) -> None:
        """Notify that the queue state has changed"""
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def get_queue_stats(self, platform: str) -> dict:
        """Get statistics about the current queue state"""
        queued_games = self.get_queued_games(platform)
        total_variants = 0
        
        for game_key in queued_games:
            game = self._find_game_by_key(game_key)
            if game:
                variants = game.get_variants_for_platform(platform)
                total_variants += len(variants)
        
        return {
            'queued_games': len(queued_games),
            'total_variants': total_variants,
            'game_keys': queued_games
        }