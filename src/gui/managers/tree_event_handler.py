"""
Tree event handler for managing user interactions with the game tree.
"""

import tkinter as tk
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from gui.game_library_gui import GameLibraryGUI

logger = logging.getLogger(__name__)


class TreeEventHandler:
    """Handles user interactions with the game tree view"""
    
    def __init__(self, gui: 'GameLibraryGUI'):
        """Initialize the tree event handler
        
        Args:
            gui: The main GUI instance for callbacks and state access
        """
        self.gui = gui
        
    def on_tree_click(self, event):
        """Handle tree click - only toggle queue on checkbox column click"""
        region = self.gui.game_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.gui.game_tree.identify_column(event.x)
            if column == '#1':  # Queued column
                self.toggle_queue_status(event)
    
    def toggle_queue_status(self, event):
        """Toggle queue status for game or variant"""
        # Prevent queue modifications during download
        if self.gui.download_controller.is_downloading():
            return
            
        item = self.gui.game_tree.identify_row(event.y)
        if not item:
            return
        
        platform = self.gui.get_current_platform_key()
        if not platform:
            return
        
        try:
            item_type = self.gui.game_tree.set(item, 'item_type')
            game_key = self.gui.game_tree.set(item, 'game_key')
            variant_key = self.gui.game_tree.set(item, 'variant_key')
        except:
            return
        
        if item_type == 'game':
            self.gui.queue_manager.toggle_game_queue_status(game_key, platform)
        elif item_type == 'variant':
            # Variants cannot be queued individually - ignore click
            return
    
    def toggle_game_queue(self, game_key: str, platform: str):
        """Toggle queue status for a specific game
        
        Args:
            game_key: The game key to toggle
            platform: The platform name
        """
        if self.gui.download_controller.is_downloading():
            logger.warning("Cannot modify queue during download")
            return
            
        self.gui.queue_manager.toggle_game_queue_status(game_key, platform)
    
    def toggle_variant_queue(self, game_key: str, variant_key: str, platform: str):
        """Toggle queue status for a specific ROM variant
        
        Args:
            game_key: The game key
            variant_key: The ROM variant key
            platform: The platform name
        """
        if self.gui.download_controller.is_downloading():
            logger.warning("Cannot modify queue during download")
            return
            
        # Note: Current implementation doesn't support individual variant queuing
        # This method is provided for potential future enhancement
        logger.debug(f"Variant queuing not supported: {game_key}/{variant_key}")
    
    def on_tree_right_click(self, event):
        """Handle right-click context menu"""
        # Prevent context menu during download
        if self.gui.download_controller.is_downloading():
            return
            
        item = self.gui.game_tree.identify_row(event.y)
        if item:
            # Update context menu state before showing
            self.gui.update_context_menu_state(item)
            self.gui.context_menu.post(event.x_root, event.y_root)
    
    def on_tree_select(self, event):
        """Handle tree selection (for expanding/collapsing)"""
        # We don't need special handling for selection changes in current implementation
        pass
    
    def bind_events(self):
        """Bind all tree events to the game tree"""
        if not self.gui.game_tree:
            logger.error("Cannot bind events: game_tree not initialized")
            return
            
        self.gui.game_tree.bind('<Button-1>', self.on_tree_click)
        self.gui.game_tree.bind('<Button-3>', self.on_tree_right_click)
        self.gui.game_tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        logger.debug("Tree events bound successfully")
    
    def unbind_events(self):
        """Unbind all tree events from the game tree"""
        if not self.gui.game_tree:
            return
            
        self.gui.game_tree.unbind('<Button-1>')
        self.gui.game_tree.unbind('<Button-3>')
        self.gui.game_tree.unbind('<<TreeviewSelect>>')
        
        logger.debug("Tree events unbound")
    
    def is_download_in_progress(self) -> bool:
        """Check if a download is currently in progress
        
        Returns:
            True if download is in progress, False otherwise
        """
        return self.gui.download_controller.is_downloading()
    
    def get_selected_item(self) -> str:
        """Get the currently selected tree item
        
        Returns:
            The ID of the selected item, or empty string if none
        """
        if not self.gui.game_tree:
            return ""
            
        selection = self.gui.game_tree.selection()
        return selection[0] if selection else ""
    
    def get_item_details(self, item_id: str) -> dict:
        """Get details about a tree item
        
        Args:
            item_id: The tree item ID
            
        Returns:
            Dictionary containing item details (item_type, game_key, variant_key)
        """
        if not self.gui.game_tree or not item_id:
            return {}
            
        try:
            return {
                'item_type': self.gui.game_tree.set(item_id, 'item_type'),
                'game_key': self.gui.game_tree.set(item_id, 'game_key'),
                'variant_key': self.gui.game_tree.set(item_id, 'variant_key')
            }
        except Exception as e:
            logger.error(f"Error getting item details for {item_id}: {e}")
            return {}