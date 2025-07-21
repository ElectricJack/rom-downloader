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
    
    def refresh_game_list(self):
        """Refresh the game list display"""
        import time
        start_time = time.time()
        
        platform = self.gui.get_current_platform_key()
        if not platform:
            return

        logger.info(f"=== refresh_game_list() started for {platform} ===")

        # Get games for platform
        games_start = time.time()
        games = self.gui.state_manager.get_games_for_platform(platform)
        games_time = time.time() - games_start
        logger.info(f"get_games_for_platform() took {games_time:.2f}s, got {len(games)} games")
        

        self.rebuild_game_tree(games, platform)
        self.apply_filters_to_tree()
        
        total_time = time.time() - start_time
        logger.info(f"=== refresh_game_list() completed in {total_time:.2f}s ===")

    def rebuild_game_tree(self, games: List['Game'], platform: str):
        """Rebuild the entire game tree from scratch"""
        logger.info(f"=== rebuild_game_tree() started with {len(games)} games ===")
        
        # Store the current games
        self.gui.current_games = games
        
        # Clear existing tree completely
        self.gui.game_tree.delete(*self.gui.game_tree.get_children())
        
        # Build tree with all games (filtering will be applied separately)
        for game in games:
            self._add_all_variants_to_tree(game, platform)
        
        logger.info(f"=== rebuild_game_tree() completed with {len(games)} games ===")
    
    def _add_all_variants_to_tree(self, game, platform):
        """Add a game with ALL its variants to the tree (no filtering)"""
        variants = game.get_variants_for_platform(platform)
        if not variants:
            return
        
        # Check if any variant is queued
        selection = self.gui.state_manager.get_selection(game.key, platform)
        queued_text = "✓" if selection else ""
        
        # Check installation status (simplified)
        installed_variants = [rom for rom in variants if rom.is_installed() is True]
        installed_text = "✓" if installed_variants else ""
        
        # Format tags for display
        tags = game.get_all_tags()
        if tags:
            categorized_tags = self.gui.library_processor.categorize_tags(tags)
            tags_text = self.gui.library_processor.format_tag_groups_compact(categorized_tags)
        else:
            tags_text = ""
        
        # Show all variants count
        variant_count_text = f"{len(variants)} variants"
        
        # Determine visual styling
        visual_tags = ['game']
        if selection:
            visual_tags.append('queued')
        if installed_variants:
            visual_tags.append('installed')
        if selection and installed_variants:
            visual_tags.append('queued_installed')
        
        # Insert game item
        game_item = self.gui.game_tree.insert(
            '',
            'end',
            text=game.display_name,
            values=(queued_text, installed_text, variant_count_text, tags_text, 'game', game.key, ''),
            tags=tuple(visual_tags)
        )
        
        # Add ALL variants as children
        for rom in variants:
            # Check if this specific variant is queued
            variant_queued = ""
            if selection and selection.selected_rom_variant == rom.create_variant_key():
                variant_queued = "✓"
            
            # Get installation status
            variant_installed = "✓" if rom.is_installed() is True else ""
            
            # Format tags for this variant
            rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
            
            # Determine visual styling for variant
            variant_visual_tags = ['variant']
            if variant_queued:
                variant_visual_tags.append('queued')
            if rom.is_installed() is True:
                variant_visual_tags.append('installed')
            if variant_queued and rom.is_installed() is True:
                variant_visual_tags.append('queued_installed')
            
            self.gui.game_tree.insert(
                game_item,
                'end',
                text=rom.filename,
                values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                tags=tuple(variant_visual_tags)
            )
    
    def apply_filters_to_tree(self):
        """Apply current filters by rebuilding tree from scratch with filtered data"""
        platform = self.gui.get_current_platform_key()
        if not platform:
            return
        
        # Get all games for this platform
        all_games = self.gui.current_games
        
        # Apply filters to get games that should be visible
        filtered_games = self._get_filtered_games(all_games, platform)
        
        # Clear the tree completely
        self.gui.game_tree.delete(*self.gui.game_tree.get_children())
        
        # Rebuild tree with only filtered games
        for game in filtered_games:
            self._add_filtered_game_to_tree(game, platform)
        
        self.gui.update_status(f"Showing {len(filtered_games)} games")
    
    def _get_filtered_games(self, games, platform):
        """Get games that match current filters and have matching variants"""
        filtered_games = []
        
        # Get current filter state
        active_tag_filters = self.gui.tag_filter_manager.get_active_filters()
        search_query = self.gui.search_query.get().lower()
        
        for game in games:
            # Apply search filter to game name
            if search_query and search_query not in game.display_name.lower():
                continue
            
            # Check if game has any variants that match tag filters
            variants = game.get_variants_for_platform(platform)
            matching_variants = self._get_matching_variants(variants, active_tag_filters)
            
            # Include game if it has at least one matching variant
            if matching_variants:
                filtered_games.append(game)
        
        return filtered_games
    
    def _get_matching_variants(self, variants, active_tag_filters):
        """Get variants that match the current tag filters"""
        if not active_tag_filters:
            # No filters active - all variants match
            return variants
        
        # Filter variants by tag criteria
        matching_variants = []
        for rom in variants:
            if self.gui.rom_matches_tags(rom, active_tag_filters):
                matching_variants.append(rom)
        
        return matching_variants
    
    def _add_filtered_game_to_tree(self, game, platform):
        """Add a game and its filtered variants to the tree"""
        # Get variants that match current filters
        active_tag_filters = self.gui.tag_filter_manager.get_active_filters()
        all_variants = game.get_variants_for_platform(platform)
        filtered_variants = self._get_matching_variants(all_variants, active_tag_filters)
        
        if not filtered_variants:
            return  # No matching variants, don't add game
        
        # Check if any variant is queued
        selection = self.gui.state_manager.get_selection(game.key, platform)
        queued_text = "✓" if selection else ""
        
        # Check installation status (simplified)
        installed_variants = [rom for rom in filtered_variants if rom.is_installed() is True]
        installed_text = "✓" if installed_variants else ""
        
        # Format tags for display
        tags = game.get_all_tags()
        if tags:
            categorized_tags = self.gui.library_processor.categorize_tags(tags)
            tags_text = self.gui.library_processor.format_tag_groups_compact(categorized_tags)
        else:
            tags_text = ""
        
        # Show filtered vs total variant count
        variant_count_text = f"{len(filtered_variants)}/{len(all_variants)} variants" if len(filtered_variants) != len(all_variants) else f"{len(all_variants)} variants"
        
        # Determine visual styling
        visual_tags = ['game']
        if selection:
            visual_tags.append('queued')
        if installed_variants:
            visual_tags.append('installed')
        if selection and installed_variants:
            visual_tags.append('queued_installed')
        
        # Insert game item
        game_item = self.gui.game_tree.insert(
            '',
            'end',
            text=game.display_name,
            values=(queued_text, installed_text, variant_count_text, tags_text, 'game', game.key, ''),
            tags=tuple(visual_tags)
        )
        
        # Add filtered variants as children
        for rom in filtered_variants:
            # Check if this specific variant is queued
            variant_queued = ""
            if selection and selection.selected_rom_variant == rom.create_variant_key():
                variant_queued = "✓"
            
            # Get installation status
            variant_installed = "✓" if rom.is_installed() is True else ""
            
            # Format tags for this variant
            rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
            
            # Determine visual styling for variant
            variant_visual_tags = ['variant']
            if variant_queued:
                variant_visual_tags.append('queued')
            if rom.is_installed() is True:
                variant_visual_tags.append('installed')
            if variant_queued and rom.is_installed() is True:
                variant_visual_tags.append('queued_installed')
            
            self.gui.game_tree.insert(
                game_item,
                'end',
                text=rom.filename,
                values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                tags=tuple(variant_visual_tags)
            )
    
