"""
Search and filter controller for managing search queries and filtering operations.
"""

import tkinter as tk
from typing import List, Set, Optional, Callable
import logging

from src.models.game_library import Game, ROM
from src.filters.advanced_rom_filter import AdvancedRomFilter

logger = logging.getLogger(__name__)


class SearchFilterController:
    """Manages search queries and filtering operations for the game library."""
    
    def __init__(self, gui_parent):
        """Initialize the search filter controller.
        
        Args:
            gui_parent: The parent GUI instance that provides access to other components
        """
        self.gui_parent = gui_parent
        self.advanced_filter = AdvancedRomFilter()
        
        # Callbacks
        self._filters_changed_callback: Optional[Callable] = None
        
        logger.info("Search filter controller initialized")
    
    def set_filters_changed_callback(self, callback: Callable):
        """Set callback to be called when filters change.
        
        Args:
            callback: Function to call when filters need to be reapplied
        """
        self._filters_changed_callback = callback
    
    def on_search_change(self, *_args):
        """Handle search text change"""
        logger.debug("Search query changed")
        # Use fast filtering instead of full refresh
        if self._filters_changed_callback:
            self._filters_changed_callback()
    
    def apply_filters(self, games: List[Game]) -> List[Game]:
        """Apply current filters to game list.
        
        Args:
            games: List of games to filter
            
        Returns:
            List of filtered games
        """
        filtered_games = games
        
        # Apply tag filters (both checkbox and custom tags)
        all_active_filters = self.gui_parent.tag_filter_manager.get_active_filters()
        if all_active_filters:
            filtered_games = [
                game for game in filtered_games
                if self.game_matches_tags(game, all_active_filters)
            ]
            logger.debug(f"Tag filtering: {len(games)} -> {len(filtered_games)} games (filters: {all_active_filters})")
        else:
            logger.debug(f"No tag filters active, keeping all {len(games)} games")
        
        # Apply search filter
        search_query = self.gui_parent.search_query.get().lower()
        if search_query:
            pre_search_count = len(filtered_games)
            filtered_games = [
                game for game in filtered_games
                if search_query in game.display_name.lower()
            ]
            logger.debug(f"Search filtering: {pre_search_count} -> {len(filtered_games)} games (query: '{search_query}')")
        
        logger.debug(f"Applied filters: {len(games)} -> {len(filtered_games)} games")
        return filtered_games
    
    def game_matches_tags(self, game: Game, filter_tags: Set[str] = None) -> bool:
        """Check if game matches current tag filters using advanced filtering logic.
        
        Args:
            game: Game to check
            filter_tags: Set of filter tags to match against
            
        Returns:
            True if game matches the filter criteria
        """
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            filter_tags = self.gui_parent.tag_filter_manager.get_active_filters()
        
        if not filter_tags:
            return True
            
        # Create filter criteria from selected tags
        criteria = self.advanced_filter.create_filter_criteria(filter_tags)
        
        # Check if game matches criteria using all its tags
        game_tags = game.get_all_tags()
        return self.advanced_filter.rom_matches_criteria(game_tags, criteria)
    
    def rom_matches_tags(self, rom: ROM, filter_tags: Set[str] = None) -> bool:
        """Check if ROM variant matches current tag filters using advanced filtering logic.
        
        Args:
            rom: ROM to check
            filter_tags: Set of filter tags to match against
            
        Returns:
            True if ROM matches the filter criteria
        """
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            filter_tags = self.gui_parent.tag_filter_manager.get_active_filters()
        
        if not filter_tags:
            return True
            
        # Create filter criteria from selected tags
        criteria = self.advanced_filter.create_filter_criteria(filter_tags)
        
        # Check if ROM matches criteria
        return self.advanced_filter.rom_matches_criteria(rom.tags, criteria)
    
    def matches_search_query(self, text: str, search_query: str = None) -> bool:
        """Check if text matches the current search query.
        
        Args:
            text: Text to search in
            search_query: Search query to match (uses current if None)
            
        Returns:
            True if text matches search query
        """
        if search_query is None:
            search_query = self.gui_parent.search_query.get()
        
        if not search_query:
            return True
            
        return search_query.lower() in text.lower()
    
    def get_current_search_query(self) -> str:
        """Get the current search query.
        
        Returns:
            Current search query string
        """
        return self.gui_parent.search_query.get()
    
    def clear_search(self):
        """Clear the current search query."""
        self.gui_parent.search_query.set("")
        logger.debug("Search query cleared")
    
    def set_search_query(self, query: str):
        """Set the search query.
        
        Args:
            query: Search query to set
        """
        self.gui_parent.search_query.set(query)
        logger.debug(f"Search query set to: {query}")