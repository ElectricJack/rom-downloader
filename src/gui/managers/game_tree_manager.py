"""
GameTreeManager - Handles game tree view operations and management

This module manages the complex game tree view including:
- Tree building and rebuilding
- Filtering and search operations
- Visual updates and status management
- Variant management within games

Extracted from GameLibraryGUI as part of refactoring to improve separation of concerns.
"""

import logging
import time
import threading
import tkinter as tk
from typing import List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.game_library_gui import GameLibraryGUI
    from src.models.game import Game

logger = logging.getLogger(__name__)


class GameTreeManager:
    """Manages game tree view operations and state"""
    
    def __init__(self, gui: 'GameLibraryGUI'):
        """Initialize GameTreeManager with reference to main GUI"""
        self.gui = gui
        self._detached_items = []
    
    def refresh_game_list(self):
        """Refresh the game list display"""
        import time
        start_time = time.time()
        
        platform = self.gui.current_platform.get()
        if not platform:
            return

        logger.info(f"=== refresh_game_list() started for {platform} ===")

        # Get games for platform
        games_start = time.time()
        games = self.gui.state_manager.get_games_for_platform(platform)
        games_time = time.time() - games_start
        logger.info(f"get_games_for_platform() took {games_time:.2f}s, got {len(games)} games")
        
        # Check if we need to rebuild the tree (data has changed)
        if self.gui.current_games != games:
            rebuild_start = time.time()
            self.rebuild_game_tree(games, platform)
            rebuild_time = time.time() - rebuild_start
            logger.info(f"rebuild_game_tree() took {rebuild_time:.2f}s")
        else:
            # Just apply filters to existing tree (much faster)
            filter_start = time.time()
            self.apply_filters_to_tree()
            filter_time = time.time() - filter_start
            logger.info(f"apply_filters_to_tree() took {filter_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== refresh_game_list() completed in {total_time:.2f}s ===")

    def rebuild_game_tree(self, games: List['Game'], platform: str):
        """Rebuild the entire game tree (only when data changes)"""
        import time
        start_time = time.time()
        
        logger.info(f"=== rebuild_game_tree() started with {len(games)} games ===")
        
        # Cancel any running async installation updates since tree structure will change
        self.gui.installation_status_manager.cancel_async_updates()
        
        # Clear existing items
        clear_start = time.time()
        self.gui.game_tree.delete(*self.gui.game_tree.get_children())
        clear_time = time.time() - clear_start
        logger.info(f"Tree clearing took {clear_time:.2f}s")
        
        # Reset cancellation flag for new async updates
        # Reset async update cancellation flag
        self.gui.installation_status_manager._async_update_cancelled = False
        
        # Clear ROM cache since it's platform-specific
        self.gui.installation_status_manager.existing_roms = set()
        
        # Auto-populate existing ROMs cache and target directory exists
        target_dir = self.gui.config_manager.get_target_directory(platform)
        logger.info(f"Target directory for platform {platform}: {target_dir}")
        
        cache_start = time.time()
        if not self.gui.installation_status_manager.existing_roms:
            logger.info("ROM cache is empty, will populate asynchronously...")
            if target_dir:
                logger.info(f"Target directory configured: {target_dir}")
                # Start async ROM scanning - don't block the UI
                thread = threading.Thread(target=self.gui.installation_status_manager._async_populate_rom_cache, args=(platform, target_dir))
                thread.daemon = True
                thread.start()
            else:
                logger.warning(f"No target directory configured for platform: {platform}")
                self.gui.installation_status_manager.existing_roms = set()
        else:
            logger.info(f"ROM cache already populated with {len(self.gui.installation_status_manager.existing_roms)} entries")
        cache_time = time.time() - cache_start
        logger.info(f"ROM cache setup took {cache_time:.2f}s")

        # Populate tree with all games (no filtering during build)
        populate_start = time.time()
        for i, game in enumerate(games):
            if i % 200 == 0 and i > 0:
                logger.info(f"Added {i}/{len(games)} games to tree...")
            self.add_game_to_tree(game, platform)
        populate_time = time.time() - populate_start
        logger.info(f"Tree population took {populate_time:.2f}s for {len(games)} games")

        self.gui.current_games = games
        
        # Apply filters to the newly built tree
        filter_start = time.time()
        self.apply_filters_to_tree()
        filter_time = time.time() - filter_start
        logger.info(f"Filter application took {filter_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== rebuild_game_tree() completed in {total_time:.2f}s ===")
    
    def apply_filters_to_tree(self):
        """Apply current filters by showing/hiding tree items using consistent logic"""
        platform = self.gui.current_platform.get()
        if not platform:
            return
            
        # Store detached items to avoid memory leaks
        if not hasattr(self, '_detached_items'):
            self._detached_items = []
        
        # First, reattach any previously detached items
        for item_id in self._detached_items:
            try:
                self.gui.game_tree.reattach(item_id, '', 'end')
            except tk.TclError:
                # Item no longer exists, ignore
                pass
        self._detached_items.clear()
        
        # Apply the SAME logic every time: check each game and its variants
        games_with_matching_variants = 0
        
        for item_id in list(self.gui.game_tree.get_children()):  # Create list copy since we're modifying
            game_key = self.gui.game_tree.set(item_id, 'game_key')
            
            # Find the game object
            game = None
            for g in self.gui.current_games:
                if g.key == game_key:
                    game = g
                    break
            
            if not game:
                # Game not found, hide it
                self.gui.game_tree.detach(item_id)
                self._detached_items.append(item_id)
                continue
            
            # Check if game has any matching variants using consistent logic
            has_matching_variants = self._rebuild_game_variants(item_id, game_key, platform)
            
            # Apply search filter to game name
            search_query = self.gui.search_query.get().lower()
            matches_search = not search_query or search_query in game.display_name.lower()
            
            # Show game only if it has matching variants AND matches search
            if has_matching_variants and matches_search:
                games_with_matching_variants += 1
            else:
                # Hide this game
                self.gui.game_tree.detach(item_id)
                self._detached_items.append(item_id)
        
        self.gui.update_status(f"Showing {games_with_matching_variants} games")
    
    def _rebuild_game_variants(self, game_item_id: str, game_key: str, platform: str) -> bool:
        """Rebuild variant children for a game with current tag filters
        
        Returns:
            True if at least one variant matches the current filters, False otherwise
        """
        try:
            # Find the game object
            game = None
            for g in self.gui.current_games:
                if g.key == game_key:
                    game = g
                    break
            
            if not game:
                return False
            
            # Remove all existing variant children
            for child_id in list(self.gui.game_tree.get_children(game_item_id)):
                self.gui.game_tree.delete(child_id)
            
            # Get all variants for this platform
            variants = game.get_variants_for_platform(platform)
            
            # Filter variants based on current tag filters
            # Check if any filters are active first
            active_filters = self.gui.tag_filter_manager.get_active_filters()
            if active_filters:
                # Apply tag filtering only when filters are active
                filtered_variants = [rom for rom in variants if self.gui.rom_matches_tags(rom)]
            else:
                # No filters active - show all variants
                filtered_variants = variants
            
            # Update the variant count in the game item
            variant_count_text = f"{len(filtered_variants)}/{len(variants)} variants" if len(filtered_variants) != len(variants) else f"{len(variants)} variants"
            current_values = list(self.gui.game_tree.item(game_item_id, 'values'))
            current_values[2] = variant_count_text  # Update variant count column
            self.gui.game_tree.item(game_item_id, values=tuple(current_values))
            
            # Get current game selection
            selection = self.gui.state_manager.get_selection(game_key, platform)
            
            # Add filtered variants as children
            for rom in filtered_variants:
                # Check if this specific variant is queued
                variant_queued = ""
                if selection and selection.selected_rom_variant == rom.create_variant_key():
                    variant_queued = "✓"
                
                # Get installation status from cache if available
                cached_installed = rom.is_installed()
                variant_installed = "✓" if cached_installed is True else ""
                
                # Format tags for this variant
                rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
                
                # Determine visual styling for variant
                variant_visual_tags = ['variant']
                if variant_queued:
                    variant_visual_tags.append('queued')
                if cached_installed is True:
                    variant_visual_tags.append('installed')
                if variant_queued and cached_installed is True:
                    variant_visual_tags.append('queued_installed')
                
                self.gui.game_tree.insert(
                    game_item_id,
                    'end',
                    text=rom.filename,
                    values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                    tags=tuple(variant_visual_tags)
                )
            
            # Return whether any variants matched the filters
            return len(filtered_variants) > 0
        
        except Exception as e:
            logger.error(f"Error rebuilding variants for game {game_key}: {e}")
            return False
    
    def apply_visual_filters(self, visible_game_keys: Set[str]):
        """Apply visual filtering using tags and styling (backup method)"""
        # This method is kept as a backup but not used in the main flow
        for item_id in self.gui.game_tree.get_children():
            game_key = self.gui.game_tree.set(item_id, 'game_key')
            
            # Get current tags and remove any existing filter tags
            current_tags = list(self.gui.game_tree.item(item_id, 'tags'))
            current_tags = [tag for tag in current_tags if tag != 'filtered_out']
            
            if game_key not in visible_game_keys:
                # This game should be filtered out
                current_tags.append('filtered_out')
                self.gui.game_tree.item(item_id, tags=tuple(current_tags))
                
                # Also filter out child variants
                for child_id in self.gui.game_tree.get_children(item_id):
                    child_tags = list(self.gui.game_tree.item(child_id, 'tags'))
                    child_tags = [tag for tag in child_tags if tag != 'filtered_out']
                    child_tags.append('filtered_out')
                    self.gui.game_tree.item(child_id, tags=tuple(child_tags))
            else:
                # This game should be visible
                self.gui.game_tree.item(item_id, tags=tuple(current_tags))
                
                # Also show child variants
                for child_id in self.gui.game_tree.get_children(item_id):
                    child_tags = list(self.gui.game_tree.item(child_id, 'tags'))
                    child_tags = [tag for tag in child_tags if tag != 'filtered_out']
                    self.gui.game_tree.item(child_id, tags=tuple(child_tags))
        
        # Configure the filtered_out tag to make items barely visible
        self.gui.game_tree.tag_configure('filtered_out', foreground='lightgray', background='')
    
    def add_game_to_tree(self, game: 'Game', platform: str):
        """Add a game and its variants to the treeview"""
        # Get variants for this platform
        variants = game.get_variants_for_platform(platform)
        if not variants:
            return
        
        # Check if any variant is queued
        selection = self.gui.state_manager.get_selection(game.key, platform)
        queued_text = "✓" if selection else ""
        
        # Skip installation checking during initial tree population to avoid blocking
        # Installation status will be updated asynchronously after ROM cache is populated
        installed_text = ""
        
        # Filter variants based on active tag filters first
        # Check if any filters are active first
        active_filters = self.gui.tag_filter_manager.get_active_filters()
        if active_filters:
            # Apply tag filtering only when filters are active
            filtered_variants = [rom for rom in variants if self.gui.rom_matches_tags(rom)]
        else:
            # No filters active - show all variants
            filtered_variants = variants
        
        # Get tags for display with grouping
        tags = game.get_all_tags()
        if tags:
            # Use the processor to categorize and format tags
            categorized_tags = self.gui.library_processor.categorize_tags(tags)
            tags_text = self.gui.library_processor.format_tag_groups_compact(categorized_tags)
        else:
            tags_text = ""
        
        # Determine visual styling (installation status will be updated later)
        visual_tags = ['game']
        if selection:
            visual_tags.append('queued')
        
        # Show filtered vs total variant count
        variant_count_text = f"{len(filtered_variants)}/{len(variants)} variants" if len(filtered_variants) != len(variants) else f"{len(variants)} variants"
        
        # Insert game item
        game_item = self.gui.game_tree.insert(
            '',
            'end',
            text=game.display_name,
            values=(queued_text, installed_text, variant_count_text, tags_text, 'game', game.key, ''),
            tags=tuple(visual_tags)
        )
        
        # Add filtered ROM variants as children
        for rom in filtered_variants:
            # Check if this specific variant is queued
            variant_queued = ""
            if selection and selection.selected_rom_variant == rom.create_variant_key():
                variant_queued = "✓"
            
            # Skip installation checking during initial tree population to avoid blocking
            variant_installed = ""
            
            # Format tags for this variant
            rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
            
            # Determine visual styling for variant (installation status will be updated later)
            variant_visual_tags = ['variant']
            if variant_queued:
                variant_visual_tags.append('queued')
            
            self.gui.game_tree.insert(
                game_item,
                'end',
                text=rom.filename,
                values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                tags=tuple(variant_visual_tags)
            )