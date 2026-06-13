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
        
        NOTE: This method is deprecated. Filtering is now handled consistently
        in GameTreeManager.apply_filters_to_tree() to avoid multiple code paths.
        
        Args:
            games: List of games to filter
            
        Returns:
            All games (filtering is handled in the tree manager)
        """
        logger.debug(f"apply_filters called with {len(games)} games - delegating to tree manager")
        return games
    
    def game_matches_tags(self, game: Game, filter_tags: Set[str] = None) -> bool:
        """Check if game matches current tag filters using advanced filtering logic.
        
        A game matches if ANY of its ROM variants match the filter criteria.
        
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
            logger.debug(f"No filters active, game '{game.display_name}' matches")
            return True
            
        # Create filter criteria from selected tags
        criteria = self.advanced_filter.create_filter_criteria(filter_tags)
        
        # Check if ANY variant of this game matches the criteria
        # This is the correct logic: a game should be shown if it has at least one matching variant
        platform = self.gui_parent.get_current_platform_key()
        if platform:
            variants = game.get_variants_for_platform(platform)
            for rom in variants:
                if self.advanced_filter.rom_matches_criteria(rom.tags, criteria):
                    logger.debug(f"Game '{game.display_name}' matches because variant '{rom.filename}' with tags {rom.tags} matches filters {filter_tags}")
                    return True
        
        # Fallback: check combined tags (for backwards compatibility)
        game_tags = game.get_all_tags()
        result = self.advanced_filter.rom_matches_criteria(game_tags, criteria)
        logger.debug(f"Game '{game.display_name}' fallback check with combined tags {game_tags} matches filters {filter_tags}: {result}")
        return result
    
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