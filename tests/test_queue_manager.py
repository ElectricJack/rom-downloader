"""
Test cases for QueueManager

Tests the queue management functionality including:
- Adding/removing games and variants to/from download queue
- Batch operations for multiple selections
- Tree selection management
- Queue state tracking and updates
- Queue statistics and utilities
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import ttk

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui.managers.queue_manager import QueueManager


class MockGame:
    """Mock Game class for testing"""
    
    def __init__(self, key, name="Test Game"):
        self.key = key
        self.name = name
        self.display_name = name
        self._variants = []
    
    def get_variants_for_platform(self, platform):
        return self._variants
    
    def get_best_variant(self, platform, preferred_regions):
        return self._variants[0] if self._variants else None
    
    def add_variant(self, variant):
        self._variants.append(variant)


class MockROM:
    """Mock ROM class for testing"""
    
    def __init__(self, variant_key="test_variant"):
        self.variant_key = variant_key
    
    def create_variant_key(self):
        return self.variant_key


class MockSelection:
    """Mock UserSelection class for testing"""
    
    def __init__(self, selected_rom_variant=None):
        self.selected_rom_variant = selected_rom_variant


class TestQueueManager(unittest.TestCase):
    """Test cases for QueueManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock parent GUI
        self.mock_parent_gui = Mock()
        
        # Set up mock game tree
        self.mock_tree = Mock()
        self.mock_parent_gui.game_tree = self.mock_tree
        
        # Set up mock platform
        self.mock_platform = Mock()
        self.mock_platform.get.return_value = "TestPlatform"
        self.mock_parent_gui.current_platform = self.mock_platform
        
        # Set up mock state manager
        self.mock_state_manager = Mock()
        self.mock_state_manager.selections = {}
        self.mock_state_manager.__enter__ = Mock(return_value=self.mock_state_manager)
        self.mock_state_manager.__exit__ = Mock(return_value=None)
        self.mock_parent_gui.state_manager = self.mock_state_manager
        
        # Set up mock config manager
        self.mock_config_manager = Mock()
        self.mock_config_manager.get_preferred_regions.return_value = ['USA']
        self.mock_parent_gui.config_manager = self.mock_config_manager
        
        # Set up mock current games
        self.test_game1 = MockGame("game1", "Test Game 1")
        self.test_game2 = MockGame("game2", "Test Game 2")
        self.test_variant1 = MockROM("variant1")
        self.test_variant2 = MockROM("variant2")
        self.test_game1.add_variant(self.test_variant1)
        self.test_game2.add_variant(self.test_variant2)
        
        self.mock_parent_gui.current_games = [self.test_game1, self.test_game2]
        
        # Set up mock update methods
        self.mock_parent_gui.update_game_tree_items_batch = Mock()
        self.mock_parent_gui.update_game_tree_item = Mock()
        
        # Create QueueManager instance
        self.manager = QueueManager(self.mock_parent_gui)
    
    def test_initialization(self):
        """Test QueueManager initialization"""
        self.assertEqual(self.manager.parent_gui, self.mock_parent_gui)
        self.assertIsNone(self.manager.on_queue_changed)
    
    def test_add_game_to_queue_batch_success(self):
        """Test adding a game to queue in batch mode"""
        # Mock no existing selection
        self.mock_state_manager.get_selection.return_value = None
        
        # Test adding game
        result = self.manager.add_game_to_queue_batch("game1", "TestPlatform")
        
        # Verify result and calls
        self.assertTrue(result)
        self.mock_state_manager.select_rom_variant.assert_called_once_with("game1", "TestPlatform", "variant1")
    
    def test_add_game_to_queue_batch_already_queued(self):
        """Test adding a game that's already queued"""
        # Mock existing selection
        self.mock_state_manager.get_selection.return_value = MockSelection("variant1")
        
        # Test adding game
        result = self.manager.add_game_to_queue_batch("game1", "TestPlatform")
        
        # Verify no change
        self.assertFalse(result)
        self.mock_state_manager.select_rom_variant.assert_not_called()
    
    def test_add_game_to_queue_batch_no_game(self):
        """Test adding a non-existent game"""
        result = self.manager.add_game_to_queue_batch("nonexistent", "TestPlatform")
        
        self.assertFalse(result)
        self.mock_state_manager.select_rom_variant.assert_not_called()
    
    def test_add_variant_to_queue_batch_success(self):
        """Test adding a variant to queue in batch mode"""
        # Mock no existing selection
        self.mock_state_manager.get_selection.return_value = None
        
        # Test adding variant
        result = self.manager.add_variant_to_queue_batch("game1", "TestPlatform", "variant1")
        
        # Verify result and calls
        self.assertTrue(result)
        self.mock_state_manager.select_rom_variant.assert_called_once_with("game1", "TestPlatform", "variant1")
    
    def test_add_variant_to_queue_batch_already_queued(self):
        """Test adding a variant that's already queued"""
        # Mock existing selection with same variant
        self.mock_state_manager.get_selection.return_value = MockSelection("variant1")
        
        # Test adding variant
        result = self.manager.add_variant_to_queue_batch("game1", "TestPlatform", "variant1")
        
        # Verify no change
        self.assertFalse(result)
        self.mock_state_manager.select_rom_variant.assert_not_called()
    
    def test_add_to_queue_mixed_selections(self):
        """Test adding mixed game and variant selections to queue"""
        # Mock tree selections
        self.mock_tree.selection.return_value = ["item1", "item2"]
        
        # Mock tree data
        def mock_tree_set(item, column):
            if item == "item1":
                if column == 'item_type':
                    return 'game'
                elif column == 'game_key':
                    return 'game1'
                elif column == 'variant_key':
                    return None
            elif item == "item2":
                if column == 'item_type':
                    return 'variant'
                elif column == 'game_key':
                    return 'game2'
                elif column == 'variant_key':
                    return 'variant2'
            return ""
        
        self.mock_tree.set = mock_tree_set
        
        # Mock no existing selections
        self.mock_state_manager.get_selection.return_value = None
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test adding to queue
        self.manager.add_to_queue()
        
        # Verify state manager calls
        expected_calls = [
            call("game1", "TestPlatform", "variant1"),
            call("game2", "TestPlatform", "variant2")
        ]
        self.mock_state_manager.select_rom_variant.assert_has_calls(expected_calls, any_order=True)
        
        # Verify batch update called
        self.mock_parent_gui.update_game_tree_items_batch.assert_called_once()
        
        # Verify callback called
        mock_callback.assert_called_once()
    
    def test_remove_from_queue(self):
        """Test removing items from queue"""
        # Mock tree selections
        self.mock_tree.selection.return_value = ["item1", "item2"]
        
        # Mock tree data
        def mock_tree_set(item, column):
            if column == 'item_type':
                return 'game'
            elif column == 'game_key':
                return f'game_{item[-1]}'
            elif column == 'variant_key':
                return None
            return ""
        
        self.mock_tree.set = mock_tree_set
        
        # Add some selections to remove
        self.mock_state_manager.selections = {
            "TestPlatform:game_1": MockSelection("variant1"),
            "TestPlatform:game_2": MockSelection("variant2")
        }
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test removing from queue
        self.manager.remove_from_queue()
        
        # Verify selections removed
        self.assertEqual(len(self.mock_state_manager.selections), 0)
        
        # Verify batch update called
        self.mock_parent_gui.update_game_tree_items_batch.assert_called_once()
        
        # Verify callback called
        mock_callback.assert_called_once()
    
    def test_select_all_games(self):
        """Test selecting all games in tree"""
        # Mock tree structure
        self.mock_tree.get_children.side_effect = [
            ["game1", "game2"],  # Top level items
            ["variant1a", "variant1b"],  # Children of game1
            ["variant2a"]  # Children of game2
        ]
        
        # Test select all
        self.manager.select_all_games()
        
        # Verify all items selected (order doesn't matter)
        actual_call = self.mock_tree.selection_set.call_args[0][0]
        expected_items = {"game1", "game2", "variant1a", "variant1b", "variant2a"}
        self.assertEqual(set(actual_call), expected_items)
    
    def test_select_none_games(self):
        """Test clearing all selections"""
        self.mock_tree.selection.return_value = ["item1", "item2"]
        
        # Test select none
        self.manager.select_none_games()
        
        # Verify selections cleared
        self.mock_tree.selection_remove.assert_called_once_with(["item1", "item2"])
    
    def test_add_game_to_queue_individual(self):
        """Test adding individual game to queue"""
        # Mock no existing selection
        self.mock_state_manager.get_selection.return_value = None
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test adding game
        self.manager.add_game_to_queue("game1", "TestPlatform")
        
        # Verify calls
        self.mock_state_manager.select_rom_variant.assert_called_once_with("game1", "TestPlatform", "variant1")
        self.mock_state_manager.save_selections.assert_called_once()
        self.mock_parent_gui.update_game_tree_item.assert_called_once_with("game1", "TestPlatform")
        mock_callback.assert_called_once()
    
    def test_add_variant_to_queue_individual(self):
        """Test adding individual variant to queue"""
        # Mock no existing selection
        self.mock_state_manager.get_selection.return_value = None
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test adding variant
        self.manager.add_variant_to_queue("game1", "TestPlatform", "variant1")
        
        # Verify calls
        self.mock_state_manager.select_rom_variant.assert_called_once_with("game1", "TestPlatform", "variant1")
        self.mock_state_manager.save_selections.assert_called_once()
        self.mock_parent_gui.update_game_tree_item.assert_called_once_with("game1", "TestPlatform")
        mock_callback.assert_called_once()
    
    def test_remove_game_from_queue(self):
        """Test removing specific game from queue"""
        # Add game to queue first
        self.mock_state_manager.selections = {
            "TestPlatform:game1": MockSelection("variant1")
        }
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test removing game
        self.manager.remove_game_from_queue("game1", "TestPlatform")
        
        # Verify removal
        self.assertNotIn("TestPlatform:game1", self.mock_state_manager.selections)
        self.assertTrue(self.mock_state_manager.selections_dirty)
        self.mock_state_manager.save_selections.assert_called_once()
        self.mock_parent_gui.update_game_tree_item.assert_called_once_with("game1", "TestPlatform")
        mock_callback.assert_called_once()
    
    def test_is_game_queued(self):
        """Test checking if game is queued"""
        # Test game not queued
        self.mock_state_manager.get_selection.return_value = None
        self.assertFalse(self.manager.is_game_queued("game1", "TestPlatform"))
        
        # Test game queued
        self.mock_state_manager.get_selection.return_value = MockSelection("variant1")
        self.assertTrue(self.manager.is_game_queued("game1", "TestPlatform"))
    
    def test_get_queued_games(self):
        """Test getting list of queued games"""
        # Set up selections
        self.mock_state_manager.selections = {
            "TestPlatform:game1": MockSelection("variant1"),
            "TestPlatform:game2": MockSelection("variant2"),
            "OtherPlatform:game3": MockSelection("variant3")
        }
        
        # Test getting queued games
        queued = self.manager.get_queued_games("TestPlatform")
        
        # Verify correct games returned
        self.assertEqual(set(queued), {"game1", "game2"})
        self.assertEqual(len(queued), 2)
    
    def test_get_queued_count(self):
        """Test getting count of queued games"""
        # Set up selections
        self.mock_state_manager.selections = {
            "TestPlatform:game1": MockSelection("variant1"),
            "TestPlatform:game2": MockSelection("variant2"),
            "OtherPlatform:game3": MockSelection("variant3")
        }
        
        # Test getting count
        count = self.manager.get_queued_count("TestPlatform")
        
        # Verify count
        self.assertEqual(count, 2)
    
    def test_clear_all_queue(self):
        """Test clearing entire queue for platform"""
        # Set up selections
        self.mock_state_manager.selections = {
            "TestPlatform:game1": MockSelection("variant1"),
            "TestPlatform:game2": MockSelection("variant2"),
            "OtherPlatform:game3": MockSelection("variant3")
        }
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test clearing queue
        self.manager.clear_all_queue("TestPlatform")
        
        # Verify only TestPlatform games removed
        remaining_selections = self.mock_state_manager.selections
        self.assertNotIn("TestPlatform:game1", remaining_selections)
        self.assertNotIn("TestPlatform:game2", remaining_selections)
        self.assertIn("OtherPlatform:game3", remaining_selections)
        
        # Verify batch update and callback
        self.mock_parent_gui.update_game_tree_items_batch.assert_called_once()
        mock_callback.assert_called_once()
    
    def test_queue_all_filtered_games(self):
        """Test queueing all visible/filtered games"""
        # Mock tree structure with game items
        self.mock_tree.get_children.return_value = ["item1", "item2", "item3"]
        
        def mock_tree_set(item, column):
            if column == 'item_type':
                return 'game' if item in ["item1", "item2"] else 'variant'
            elif column == 'game_key':
                # Return valid game keys that exist in current_games
                if item == "item1":
                    return "game1"
                elif item == "item2":
                    return "game2"
                else:
                    return "game3"
            return ""
        
        self.mock_tree.set = mock_tree_set
        
        # Mock no existing selections
        self.mock_state_manager.get_selection.return_value = None
        
        # Mock callback
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        # Test queueing all filtered games
        self.manager.queue_all_filtered_games()
        
        # Verify only game items were queued (not variants)
        self.assertEqual(self.mock_state_manager.select_rom_variant.call_count, 2)
        
        # Verify batch update and callback
        self.mock_parent_gui.update_game_tree_items_batch.assert_called_once()
        mock_callback.assert_called_once()
    
    def test_toggle_game_queue_status(self):
        """Test toggling game queue status"""
        # Test adding when not queued
        self.mock_state_manager.get_selection.return_value = None
        
        mock_callback = Mock()
        self.manager.set_queue_changed_callback(mock_callback)
        
        self.manager.toggle_game_queue_status("game1", "TestPlatform")
        
        # Verify game added
        self.mock_state_manager.select_rom_variant.assert_called_once()
        mock_callback.assert_called_once()
        
        # Reset mocks
        self.mock_state_manager.reset_mock()
        mock_callback.reset_mock()
        
        # Test removing when queued
        self.mock_state_manager.selections = {"TestPlatform:game1": MockSelection("variant1")}
        self.mock_state_manager.get_selection.return_value = MockSelection("variant1")
        
        self.manager.toggle_game_queue_status("game1", "TestPlatform")
        
        # Verify game removed
        self.assertNotIn("TestPlatform:game1", self.mock_state_manager.selections)
        mock_callback.assert_called_once()
    
    def test_get_queued_variant_key(self):
        """Test getting variant key for queued game"""
        # Test game not queued
        self.mock_state_manager.get_selection.return_value = None
        variant_key = self.manager.get_queued_variant_key("game1", "TestPlatform")
        self.assertIsNone(variant_key)
        
        # Test game queued
        self.mock_state_manager.get_selection.return_value = MockSelection("variant1")
        variant_key = self.manager.get_queued_variant_key("game1", "TestPlatform")
        self.assertEqual(variant_key, "variant1")
    
    def test_get_queue_stats(self):
        """Test getting queue statistics"""
        # Set up selections
        self.mock_state_manager.selections = {
            "TestPlatform:game1": MockSelection("variant1"),
            "TestPlatform:game2": MockSelection("variant2")
        }
        
        # Test getting stats
        stats = self.manager.get_queue_stats("TestPlatform")
        
        # Verify stats
        self.assertEqual(stats['queued_games'], 2)
        self.assertEqual(stats['total_variants'], 2)  # Each test game has 1 variant
        self.assertEqual(set(stats['game_keys']), {"game1", "game2"})
    
    def test_callback_functionality(self):
        """Test callback setting and invocation"""
        mock_callback = Mock()
        
        # Set callback
        self.manager.set_queue_changed_callback(mock_callback)
        self.assertEqual(self.manager.on_queue_changed, mock_callback)
        
        # Test that callback is called
        self.manager._notify_queue_changed()
        mock_callback.assert_called_once()
    
    def test_find_game_by_key(self):
        """Test finding game by key"""
        # Test existing game
        game = self.manager._find_game_by_key("game1")
        self.assertIsNotNone(game)
        self.assertEqual(game.key, "game1")
        
        # Test non-existent game
        game = self.manager._find_game_by_key("nonexistent")
        self.assertIsNone(game)
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        # Test with no tree selections
        self.mock_tree.selection.return_value = []
        self.manager.add_to_queue()  # Should not crash
        
        # Test with no platform
        self.mock_platform.get.return_value = ""
        self.manager.add_to_queue()  # Should not crash
        
        # Test with invalid tree data
        self.mock_platform.get.return_value = "TestPlatform"
        self.mock_tree.selection.return_value = ["item1"]
        self.mock_tree.set.side_effect = Exception("Tree error")
        self.manager.add_to_queue()  # Should not crash
        
        # Test clearing empty queue
        self.mock_state_manager.selections = {}
        self.manager.clear_all_queue("TestPlatform")  # Should not crash
    
    def test_batch_operations_efficiency(self):
        """Test that batch operations use context manager correctly"""
        # Test add_to_queue uses batch mode
        self.mock_tree.selection.return_value = ["item1"]
        self.mock_tree.set.return_value = "game"
        
        self.manager.add_to_queue()
        
        # Verify context manager was used
        self.mock_state_manager.__enter__.assert_called_once()
        self.mock_state_manager.__exit__.assert_called_once()
        
        # Reset for next test
        self.mock_state_manager.reset_mock()
        
        # Test remove_from_queue uses batch mode
        self.manager.remove_from_queue()
        
        # Verify context manager was used
        self.mock_state_manager.__enter__.assert_called_once()
        self.mock_state_manager.__exit__.assert_called_once()


class TestQueueManagerIntegration(unittest.TestCase):
    """Integration tests for QueueManager"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create a more realistic parent GUI mock
        self.mock_parent_gui = Mock()
        
        # Set up mock components with more realistic behavior
        self.mock_tree = Mock()
        self.mock_parent_gui.game_tree = self.mock_tree
        
        self.mock_platform = Mock()
        self.mock_platform.get.return_value = "TestPlatform"
        self.mock_parent_gui.current_platform = self.mock_platform
        
        self.mock_state_manager = Mock()
        self.mock_state_manager.selections = {}
        self.mock_state_manager.selections_dirty = False
        self.mock_state_manager.__enter__ = Mock(return_value=self.mock_state_manager)
        self.mock_state_manager.__exit__ = Mock(return_value=None)
        self.mock_parent_gui.state_manager = self.mock_state_manager
        
        self.mock_config_manager = Mock()
        self.mock_config_manager.get_preferred_regions.return_value = ['USA', 'Europe']
        self.mock_parent_gui.config_manager = self.mock_config_manager
        
        # Create test games
        self.games = []
        for i in range(3):
            game = MockGame(f"game{i}", f"Test Game {i}")
            for j in range(2):
                variant = MockROM(f"variant{i}_{j}")
                game.add_variant(variant)
            self.games.append(game)
        
        self.mock_parent_gui.current_games = self.games
        self.mock_parent_gui.update_game_tree_items_batch = Mock()
        self.mock_parent_gui.update_game_tree_item = Mock()
        
        self.manager = QueueManager(self.mock_parent_gui)
    
    def test_complete_queue_workflow(self):
        """Test complete queue management workflow"""
        # Set up callback to track changes
        queue_changes = []
        def capture_changes():
            queue_changes.append(self.manager.get_queued_count("TestPlatform"))
        
        self.manager.set_queue_changed_callback(capture_changes)
        
        # 1. Add games to queue individually
        def mock_get_selection(game_key, platform):
            # Return None initially, then MockSelection after adding
            selection_key = f"{platform}:{game_key}"
            return MockSelection("variant0_0") if selection_key in self.mock_state_manager.selections else None
        
        self.mock_state_manager.get_selection.side_effect = mock_get_selection
        
        # Simulate adding to selections when select_rom_variant is called
        def mock_select_rom_variant(game_key, platform, variant_key):
            selection_key = f"{platform}:{game_key}"
            self.mock_state_manager.selections[selection_key] = MockSelection(variant_key)
        
        self.mock_state_manager.select_rom_variant.side_effect = mock_select_rom_variant
        
        self.manager.add_game_to_queue("game0", "TestPlatform")
        self.manager.add_game_to_queue("game1", "TestPlatform")
        
        # Verify games were added
        self.assertEqual(len(queue_changes), 2)
        
        # 2. Check queue status
        self.assertTrue(self.manager.is_game_queued("game0", "TestPlatform"))
        self.assertTrue(self.manager.is_game_queued("game1", "TestPlatform"))
        self.assertFalse(self.manager.is_game_queued("game2", "TestPlatform"))
        
        # 3. Get queue statistics
        stats = self.manager.get_queue_stats("TestPlatform")
        self.assertEqual(stats['queued_games'], 2)
        
        # 4. Toggle game status (remove)
        self.mock_state_manager.selections = {"TestPlatform:game0": MockSelection("variant0_0")}
        self.mock_state_manager.get_selection.return_value = MockSelection("variant0_0")
        self.manager.toggle_game_queue_status("game0", "TestPlatform")
        
        # 5. Clear all queue
        self.manager.clear_all_queue("TestPlatform")
        
        # Verify final state
        final_count = self.manager.get_queued_count("TestPlatform")
        self.assertEqual(final_count, 0)
        
        # Verify callbacks were called
        self.assertGreater(len(queue_changes), 2)
    
    def test_bulk_operations(self):
        """Test bulk queue operations"""
        # Mock tree selections for bulk operations
        self.mock_tree.selection.return_value = ["item0", "item1", "item2"]
        
        def mock_tree_set(item, column):
            item_num = int(item[-1])
            if column == 'item_type':
                return 'game'
            elif column == 'game_key':
                return f'game{item_num}'
            elif column == 'variant_key':
                return f'variant{item_num}_0'
            return ""
        
        self.mock_tree.set = mock_tree_set
        
        # Mock no existing selections
        self.mock_state_manager.get_selection.return_value = None
        
        # Set up callback
        changes = []
        self.manager.set_queue_changed_callback(lambda: changes.append("changed"))
        
        # Test bulk add
        self.manager.add_to_queue()
        
        # Verify bulk operations
        self.assertEqual(self.mock_state_manager.select_rom_variant.call_count, 3)
        self.mock_parent_gui.update_game_tree_items_batch.assert_called()
        self.assertEqual(len(changes), 1)
        
        # Test bulk remove
        self.mock_state_manager.selections = {
            "TestPlatform:game0": MockSelection("variant0_0"),
            "TestPlatform:game1": MockSelection("variant1_0"),
            "TestPlatform:game2": MockSelection("variant2_0")
        }
        
        self.manager.remove_from_queue()
        
        # Verify removal
        self.assertEqual(len(self.mock_state_manager.selections), 0)
        self.assertEqual(len(changes), 2)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)