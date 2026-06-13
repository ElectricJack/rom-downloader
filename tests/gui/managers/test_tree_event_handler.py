"""
Tests for TreeEventHandler class.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk

from src.gui.managers.tree_event_handler import TreeEventHandler


class TestTreeEventHandler(unittest.TestCase):
    """Test cases for TreeEventHandler"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock GUI instance
        self.mock_gui = Mock()
        self.mock_gui.game_tree = Mock()
        self.mock_gui.context_menu = Mock()
        self.mock_gui.current_platform = Mock()
        self.mock_gui.download_controller = Mock()
        self.mock_gui.queue_manager = Mock()
        
        # Set up default mock returns
        self.mock_gui.current_platform.get.return_value = "test_platform"
        self.mock_gui.download_controller.is_downloading.return_value = False
        
        # Create the event handler
        self.handler = TreeEventHandler(self.mock_gui)
    
    def test_init(self):
        """Test TreeEventHandler initialization"""
        self.assertEqual(self.handler.gui, self.mock_gui)
    
    def test_on_tree_click_queued_column(self):
        """Test clicking on the queued column triggers toggle"""
        # Create mock event
        mock_event = Mock()
        mock_event.x = 100
        mock_event.y = 50
        
        # Configure mock returns
        self.mock_gui.game_tree.identify_region.return_value = "cell"
        self.mock_gui.game_tree.identify_column.return_value = "#1"  # Queued column
        
        # Call the method
        with patch.object(self.handler, 'toggle_queue_status') as mock_toggle:
            self.handler.on_tree_click(mock_event)
            
        # Verify toggle was called
        mock_toggle.assert_called_once_with(mock_event)
    
    def test_on_tree_click_other_column(self):
        """Test clicking on other columns doesn't trigger toggle"""
        # Create mock event
        mock_event = Mock()
        mock_event.x = 100
        mock_event.y = 50
        
        # Configure mock returns for non-queued column
        self.mock_gui.game_tree.identify_region.return_value = "cell"
        self.mock_gui.game_tree.identify_column.return_value = "#2"  # Not queued column
        
        # Call the method
        with patch.object(self.handler, 'toggle_queue_status') as mock_toggle:
            self.handler.on_tree_click(mock_event)
            
        # Verify toggle was not called
        mock_toggle.assert_not_called()
    
    def test_on_tree_click_non_cell_region(self):
        """Test clicking outside cell region doesn't trigger toggle"""
        # Create mock event
        mock_event = Mock()
        mock_event.x = 100
        mock_event.y = 50
        
        # Configure mock returns for non-cell region
        self.mock_gui.game_tree.identify_region.return_value = "separator"
        
        # Call the method
        with patch.object(self.handler, 'toggle_queue_status') as mock_toggle:
            self.handler.on_tree_click(mock_event)
            
        # Verify toggle was not called
        mock_toggle.assert_not_called()
    
    def test_toggle_queue_status_during_download(self):
        """Test toggle is prevented during download"""
        # Set up download in progress
        self.mock_gui.download_controller.is_downloading.return_value = True
        
        mock_event = Mock()
        mock_event.y = 50
        
        # Call the method
        self.handler.toggle_queue_status(mock_event)
        
        # Verify no queue operations were performed
        self.mock_gui.game_tree.identify_row.assert_not_called()
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_queue_status_no_item(self):
        """Test toggle with no item identified"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure to return no item
        self.mock_gui.game_tree.identify_row.return_value = None
        
        # Call the method
        self.handler.toggle_queue_status(mock_event)
        
        # Verify no queue operations were performed
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_queue_status_no_platform(self):
        """Test toggle with no platform selected"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure to return no platform
        self.mock_gui.current_platform.get.return_value = ""
        self.mock_gui.game_tree.identify_row.return_value = "item1"
        
        # Call the method
        self.handler.toggle_queue_status(mock_event)
        
        # Verify no queue operations were performed
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_queue_status_game_item(self):
        """Test toggle queue status for game item"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure mock returns
        self.mock_gui.game_tree.identify_row.return_value = "item1"
        self.mock_gui.game_tree.set.side_effect = lambda item, col: {
            ('item1', 'item_type'): 'game',
            ('item1', 'game_key'): 'test_game',
            ('item1', 'variant_key'): ''
        }.get((item, col), '')
        
        # Call the method
        self.handler.toggle_queue_status(mock_event)
        
        # Verify queue manager was called
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_called_once_with(
            'test_game', 'test_platform'
        )
    
    def test_toggle_queue_status_variant_item(self):
        """Test toggle queue status for variant item (should be ignored)"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure mock returns for variant
        self.mock_gui.game_tree.identify_row.return_value = "item1"
        self.mock_gui.game_tree.set.side_effect = lambda item, col: {
            ('item1', 'item_type'): 'variant',
            ('item1', 'game_key'): 'test_game',
            ('item1', 'variant_key'): 'test_variant'
        }.get((item, col), '')
        
        # Call the method
        self.handler.toggle_queue_status(mock_event)
        
        # Verify queue manager was not called for variants
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_queue_status_exception_handling(self):
        """Test toggle queue status handles exceptions gracefully"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure to raise exception
        self.mock_gui.game_tree.identify_row.return_value = "item1"
        self.mock_gui.game_tree.set.side_effect = Exception("Test error")
        
        # Call the method - should not raise exception
        try:
            self.handler.toggle_queue_status(mock_event)
        except Exception:
            self.fail("toggle_queue_status raised an exception")
        
        # Verify queue manager was not called
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_game_queue(self):
        """Test toggle_game_queue method"""
        # Call the method
        self.handler.toggle_game_queue("test_game", "test_platform")
        
        # Verify queue manager was called
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_called_once_with(
            "test_game", "test_platform"
        )
    
    def test_toggle_game_queue_during_download(self):
        """Test toggle_game_queue is prevented during download"""
        # Set up download in progress
        self.mock_gui.download_controller.is_downloading.return_value = True
        
        # Call the method
        self.handler.toggle_game_queue("test_game", "test_platform")
        
        # Verify queue manager was not called
        self.mock_gui.queue_manager.toggle_game_queue_status.assert_not_called()
    
    def test_toggle_variant_queue(self):
        """Test toggle_variant_queue method (currently not supported)"""
        # Call the method - should not raise exception
        try:
            self.handler.toggle_variant_queue("test_game", "test_variant", "test_platform")
        except Exception:
            self.fail("toggle_variant_queue raised an exception")
        
        # Note: This method currently logs a debug message but doesn't perform actions
    
    def test_on_tree_right_click(self):
        """Test right-click context menu"""
        mock_event = Mock()
        mock_event.y = 50
        mock_event.x_root = 200
        mock_event.y_root = 150
        
        # Configure to identify an item
        self.mock_gui.game_tree.identify_row.return_value = "item1"
        
        # Call the method
        self.handler.on_tree_right_click(mock_event)
        
        # Verify context menu was posted
        self.mock_gui.context_menu.post.assert_called_once_with(200, 150)
    
    def test_on_tree_right_click_no_item(self):
        """Test right-click with no item"""
        mock_event = Mock()
        mock_event.y = 50
        
        # Configure to return no item
        self.mock_gui.game_tree.identify_row.return_value = None
        
        # Call the method
        self.handler.on_tree_right_click(mock_event)
        
        # Verify context menu was not posted
        self.mock_gui.context_menu.post.assert_not_called()
    
    def test_on_tree_right_click_during_download(self):
        """Test right-click is prevented during download"""
        # Set up download in progress
        self.mock_gui.download_controller.is_downloading.return_value = True
        
        mock_event = Mock()
        mock_event.y = 50
        
        # Call the method
        self.handler.on_tree_right_click(mock_event)
        
        # Verify no context menu operations
        self.mock_gui.game_tree.identify_row.assert_not_called()
        self.mock_gui.context_menu.post.assert_not_called()
    
    def test_on_tree_select(self):
        """Test tree selection handler (currently no-op)"""
        mock_event = Mock()
        
        # Call the method - should not raise exception
        try:
            self.handler.on_tree_select(mock_event)
        except Exception:
            self.fail("on_tree_select raised an exception")
    
    def test_bind_events(self):
        """Test binding events to the tree"""
        # Call the method
        self.handler.bind_events()
        
        # Verify events were bound
        self.mock_gui.game_tree.bind.assert_any_call('<Button-1>', self.handler.on_tree_click)
        self.mock_gui.game_tree.bind.assert_any_call('<Button-3>', self.handler.on_tree_right_click)
        self.mock_gui.game_tree.bind.assert_any_call('<<TreeviewSelect>>', self.handler.on_tree_select)
    
    def test_bind_events_no_tree(self):
        """Test binding events when tree is not initialized"""
        # Set tree to None
        self.mock_gui.game_tree = None
        
        # Call the method - should not raise exception
        try:
            self.handler.bind_events()
        except Exception:
            self.fail("bind_events raised an exception when tree is None")
    
    def test_unbind_events(self):
        """Test unbinding events from the tree"""
        # Call the method
        self.handler.unbind_events()
        
        # Verify events were unbound
        self.mock_gui.game_tree.unbind.assert_any_call('<Button-1>')
        self.mock_gui.game_tree.unbind.assert_any_call('<Button-3>')
        self.mock_gui.game_tree.unbind.assert_any_call('<<TreeviewSelect>>')
    
    def test_unbind_events_no_tree(self):
        """Test unbinding events when tree is not initialized"""
        # Set tree to None
        self.mock_gui.game_tree = None
        
        # Call the method - should not raise exception
        try:
            self.handler.unbind_events()
        except Exception:
            self.fail("unbind_events raised an exception when tree is None")
    
    def test_is_download_in_progress(self):
        """Test checking download progress status"""
        # Test when download is not in progress
        self.mock_gui.download_controller.is_downloading.return_value = False
        self.assertFalse(self.handler.is_download_in_progress())
        
        # Test when download is in progress
        self.mock_gui.download_controller.is_downloading.return_value = True
        self.assertTrue(self.handler.is_download_in_progress())
    
    def test_get_selected_item(self):
        """Test getting the selected tree item"""
        # Test with selection
        self.mock_gui.game_tree.selection.return_value = ["item1", "item2"]
        self.assertEqual(self.handler.get_selected_item(), "item1")
        
        # Test with no selection
        self.mock_gui.game_tree.selection.return_value = []
        self.assertEqual(self.handler.get_selected_item(), "")
    
    def test_get_selected_item_no_tree(self):
        """Test getting selected item when tree is not initialized"""
        # Set tree to None
        self.mock_gui.game_tree = None
        
        # Should return empty string
        self.assertEqual(self.handler.get_selected_item(), "")
    
    def test_get_item_details(self):
        """Test getting item details"""
        # Configure mock returns
        self.mock_gui.game_tree.set.side_effect = lambda item, col: {
            ('item1', 'item_type'): 'game',
            ('item1', 'game_key'): 'test_game',
            ('item1', 'variant_key'): 'test_variant'
        }.get((item, col), '')
        
        # Call the method
        result = self.handler.get_item_details("item1")
        
        # Verify result
        expected = {
            'item_type': 'game',
            'game_key': 'test_game',
            'variant_key': 'test_variant'
        }
        self.assertEqual(result, expected)
    
    def test_get_item_details_no_item(self):
        """Test getting details for invalid item"""
        result = self.handler.get_item_details("")
        self.assertEqual(result, {})
    
    def test_get_item_details_no_tree(self):
        """Test getting details when tree is not initialized"""
        # Set tree to None
        self.mock_gui.game_tree = None
        
        result = self.handler.get_item_details("item1")
        self.assertEqual(result, {})
    
    def test_get_item_details_exception(self):
        """Test getting details handles exceptions gracefully"""
        # Configure to raise exception
        self.mock_gui.game_tree.set.side_effect = Exception("Test error")
        
        result = self.handler.get_item_details("item1")
        self.assertEqual(result, {})


class TestTreeEventHandlerIntegration(unittest.TestCase):
    """Integration tests for TreeEventHandler with real Tkinter components"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create real Tkinter components for integration testing
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during testing
        
        # Create a real treeview
        self.tree = ttk.Treeview(self.root, columns=('queued', 'installed'))
        self.tree.heading('#0', text='Name')
        self.tree.heading('queued', text='Queued')
        self.tree.heading('installed', text='Installed')
        
        # Add some test items
        game_item = self.tree.insert('', 'end', text='Test Game', values=('', ''))
        self.tree.set(game_item, 'item_type', 'game')
        self.tree.set(game_item, 'game_key', 'test_game')
        self.tree.set(game_item, 'variant_key', '')
        
        variant_item = self.tree.insert(game_item, 'end', text='Test Variant', values=('', ''))
        self.tree.set(variant_item, 'item_type', 'variant')
        self.tree.set(variant_item, 'game_key', 'test_game')
        self.tree.set(variant_item, 'variant_key', 'test_variant')
        
        # Create mock GUI with real tree
        self.mock_gui = Mock()
        self.mock_gui.game_tree = self.tree
        self.mock_gui.context_menu = Mock()
        self.mock_gui.current_platform = Mock()
        self.mock_gui.download_controller = Mock()
        self.mock_gui.queue_manager = Mock()
        
        # Set up default mock returns
        self.mock_gui.current_platform.get.return_value = "test_platform"
        self.mock_gui.download_controller.is_downloading.return_value = False
        
        # Create the event handler
        self.handler = TreeEventHandler(self.mock_gui)
    
    def tearDown(self):
        """Clean up after integration tests"""
        self.root.destroy()
    
    def test_real_tree_integration(self):
        """Test that the handler works with a real treeview"""
        # Bind events
        self.handler.bind_events()
        
        # Test getting item details with real tree
        items = self.tree.get_children()
        self.assertTrue(len(items) > 0)
        
        game_item = items[0]
        details = self.handler.get_item_details(game_item)
        
        self.assertEqual(details['item_type'], 'game')
        self.assertEqual(details['game_key'], 'test_game')
        self.assertEqual(details['variant_key'], '')
        
        # Test unbinding
        self.handler.unbind_events()


if __name__ == '__main__':
    unittest.main()