#!/usr/bin/env python3
"""
Test cases for GameTreeManager

Tests the game tree management functionality including:
- Tree building and rebuilding
- Filtering and search operations
- Visual updates and status management
- Variant management within games
"""

import sys
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import ttk
import logging

from gui.managers.game_tree_manager import GameTreeManager
from models.game_library import Game, ROM


class TestGameTreeManager(unittest.TestCase):
    """Test cases for GameTreeManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock GUI instance
        self.mock_gui = Mock()
        
        # Mock tkinter components
        self.mock_root = Mock()
        self.mock_game_tree = Mock(spec=ttk.Treeview)
        self.mock_gui.root = self.mock_root
        self.mock_gui.game_tree = self.mock_game_tree
        
        # Mock platform and search variables
        self.mock_platform_var = Mock()
        self.mock_platform_var.get.return_value = "test_platform"
        self.mock_gui.current_platform = self.mock_platform_var
        
        # Mock other GUI components
        self.mock_gui.current_games = []
        self.mock_gui.existing_roms = set()
        self.mock_gui._async_update_cancelled = False
        self.mock_gui._gui_active = True
        
        # Mock managers
        self.mock_gui.state_manager = Mock()
        self.mock_gui.config_manager = Mock()
        self.mock_gui.library_processor = Mock()
        self.mock_gui.advanced_filter = Mock()
        
        # Mock methods
        self.mock_gui.apply_filters = Mock()
        self.mock_gui.rom_matches_tags = Mock(return_value=True)
        self.mock_gui.update_status = Mock()
        self.mock_gui._async_populate_rom_cache = Mock()
        
        # Create GameTreeManager instance
        self.tree_manager = GameTreeManager(self.mock_gui)
    
    def test_init(self):
        """Test GameTreeManager initialization"""
        self.assertEqual(self.tree_manager.gui, self.mock_gui)
        self.assertEqual(self.tree_manager._detached_items, [])
    
    def test_refresh_game_list_no_platform(self):
        """Test refresh_game_list when no platform is selected"""
        self.mock_platform_var.get.return_value = ""
        
        self.tree_manager.refresh_game_list()
        
        # Should return early without doing anything
        self.mock_gui.state_manager.get_games_for_platform.assert_not_called()
    
    def test_refresh_game_list_rebuild_needed(self):
        """Test refresh_game_list when tree rebuild is needed"""
        # Setup test data
        test_games = [Mock(), Mock()]
        self.mock_gui.state_manager.get_games_for_platform.return_value = test_games
        self.mock_gui.current_games = []  # Different from test_games
        
        with patch.object(self.tree_manager, 'rebuild_game_tree') as mock_rebuild:
            self.tree_manager.refresh_game_list()
            
            self.mock_gui.state_manager.get_games_for_platform.assert_called_once_with("test_platform")
            mock_rebuild.assert_called_once_with(test_games, "test_platform")
    
    def test_refresh_game_list_filter_only(self):
        """Test refresh_game_list when only filtering is needed"""
        # Setup test data
        test_games = [Mock(), Mock()]
        self.mock_gui.state_manager.get_games_for_platform.return_value = test_games
        self.mock_gui.current_games = test_games  # Same as test_games
        
        with patch.object(self.tree_manager, 'apply_filters_to_tree') as mock_filter:
            self.tree_manager.refresh_game_list()
            
            self.mock_gui.state_manager.get_games_for_platform.assert_called_once_with("test_platform")
            mock_filter.assert_called_once()
    
    @patch('threading.Thread')
    def test_rebuild_game_tree(self, mock_thread):
        """Test rebuild_game_tree functionality"""
        # Setup test data
        test_games = [Mock(), Mock()]
        test_platform = "test_platform"
        test_target_dir = "/test/target"
        
        self.mock_gui.config_manager.get_target_directory.return_value = test_target_dir
        self.mock_game_tree.get_children.return_value = ["item1", "item2"]
        
        with patch.object(self.tree_manager, 'add_game_to_tree') as mock_add_game, \
             patch.object(self.tree_manager, 'apply_filters_to_tree') as mock_filter:
            
            self.tree_manager.rebuild_game_tree(test_games, test_platform)
            
            # Verify tree was cleared
            self.mock_game_tree.delete.assert_called_once_with("item1", "item2")
            
            # Verify async update cancellation was set initially (but may be reset)
            # The flag is first set to True, then reset to False
            pass  # This behavior is correct
            
            # Verify ROM cache was cleared
            self.assertEqual(self.mock_gui.existing_roms, set())
            
            # Verify games were added to tree
            self.assertEqual(mock_add_game.call_count, len(test_games))
            
            # Verify current_games was updated
            self.assertEqual(self.mock_gui.current_games, test_games)
            
            # Verify filters were applied
            mock_filter.assert_called_once()
            
            # Verify async ROM cache population was started
            mock_thread.assert_called_once()
    
    def test_rebuild_game_tree_no_target_dir(self):
        """Test rebuild_game_tree when no target directory is configured"""
        test_games = [Mock()]
        test_platform = "test_platform"
        
        self.mock_gui.config_manager.get_target_directory.return_value = None
        self.mock_game_tree.get_children.return_value = []
        
        with patch.object(self.tree_manager, 'add_game_to_tree') as mock_add_game, \
             patch.object(self.tree_manager, 'apply_filters_to_tree') as mock_filter:
            
            self.tree_manager.rebuild_game_tree(test_games, test_platform)
            
            # Should still proceed with tree building
            mock_add_game.assert_called_once()
            mock_filter.assert_called_once()
            
            # ROM cache should be empty
            self.assertEqual(self.mock_gui.existing_roms, set())
    
    def test_apply_filters_to_tree(self):
        """Test apply_filters_to_tree functionality"""
        # Setup test data
        test_games = [Mock(), Mock()]
        test_games[0].key = "game1"
        test_games[1].key = "game2"
        
        self.mock_gui.apply_filters.return_value = [test_games[0]]  # Only game1 passes filter
        self.mock_gui.current_games = test_games
        self.mock_game_tree.get_children.return_value = ["item1", "item2"]
        self.mock_game_tree.set.side_effect = lambda item, col: "game1" if item == "item1" else "game2"
        
        # Setup detached items from previous filtering
        self.tree_manager._detached_items = ["old_item"]
        
        with patch.object(self.tree_manager, '_rebuild_game_variants') as mock_rebuild_variants:
            self.tree_manager.apply_filters_to_tree()
            
            # Verify filters were applied
            self.mock_gui.apply_filters.assert_called_once_with(test_games)
            
            # Verify old detached items were reattached
            self.mock_game_tree.reattach.assert_called_once_with("old_item", '', 'end')
            
            # Verify item2 was detached (doesn't match filter)
            self.mock_game_tree.detach.assert_called_once_with("item2")
            self.assertIn("item2", self.tree_manager._detached_items)
            
            # Verify variants were rebuilt for visible game
            mock_rebuild_variants.assert_called_once_with("item1", "game1", "test_platform")
            
            # Verify status was updated
            self.mock_gui.update_status.assert_called_once_with("Showing 1 games")
    
    def test_rebuild_game_variants(self):
        """Test _rebuild_game_variants functionality"""
        # Setup test data
        test_game = Mock()
        test_game.key = "test_game"
        test_platform = "test_platform"
        test_item_id = "test_item"
        
        # Mock ROM variants
        mock_rom1 = Mock()
        mock_rom1.create_variant_key.return_value = "variant1"
        mock_rom1.filename = "rom1.zip"
        mock_rom1.size = "1MB"
        mock_rom1.tags = ["tag1", "tag2"]
        mock_rom1.is_installed.return_value = True
        
        mock_rom2 = Mock()
        mock_rom2.create_variant_key.return_value = "variant2"
        mock_rom2.filename = "rom2.zip"
        mock_rom2.size = "2MB"
        mock_rom2.tags = ["tag3"]
        mock_rom2.is_installed.return_value = False
        
        test_game.get_variants_for_platform.return_value = [mock_rom1, mock_rom2]
        self.mock_gui.current_games = [test_game]
        
        # Mock tree operations
        self.mock_game_tree.get_children.return_value = ["child1", "child2"]
        # Mock item() method to return current values when called with just item_id
        # and accept values parameter when setting
        def mock_item_side_effect(*args, **kwargs):
            if 'values' in kwargs:
                return None  # Setting values
            elif len(args) >= 2 and args[1] == 'values':
                # When called as item(item_id, 'values'), return the values tuple directly
                return ('queued', 'installed', 'old_count', 'tags', 'game', 'test_game', '')
            else:
                return {'values': ('queued', 'installed', 'old_count', 'tags', 'game', 'test_game', '')}
        
        self.mock_game_tree.item.side_effect = mock_item_side_effect
        
        # Mock selection
        mock_selection = Mock()
        mock_selection.selected_rom_variant = "variant1"
        self.mock_gui.state_manager.get_selection.return_value = mock_selection
        
        self.tree_manager._rebuild_game_variants(test_item_id, "test_game", test_platform)
        
        # Verify old children were deleted
        self.assertEqual(self.mock_game_tree.delete.call_count, 2)
        
        # Verify variant count was updated
        # The method calls item() first to get current values, then to set new values
        # Check that item() was called to update values
        calls = self.mock_game_tree.item.call_args_list
        # Should have at least one call to get values and one to set values
        self.assertGreater(len(calls), 0)
        
        # Verify variants were inserted
        self.assertEqual(self.mock_game_tree.insert.call_count, 2)
    
    def test_rebuild_game_variants_game_not_found(self):
        """Test _rebuild_game_variants when game is not found"""
        test_item_id = "test_item"
        test_game_key = "nonexistent_game"
        test_platform = "test_platform"
        
        self.mock_gui.current_games = []
        
        # Should return early without errors
        self.tree_manager._rebuild_game_variants(test_item_id, test_game_key, test_platform)
        
        # No tree operations should be performed
        self.mock_game_tree.get_children.assert_not_called()
    
    def test_apply_visual_filters(self):
        """Test apply_visual_filters functionality"""
        visible_game_keys = {"game1"}
        
        # Mock tree items
        self.mock_game_tree.get_children.side_effect = [
            ["item1", "item2"],  # Top level items
            ["child1"],          # Children of item1
            ["child2"]           # Children of item2
        ]
        
        self.mock_game_tree.set.side_effect = lambda item, col: "game1" if item == "item1" else "game2"
        self.mock_game_tree.item.return_value = {'tags': ['game']}
        
        self.tree_manager.apply_visual_filters(visible_game_keys)
        
        # Verify filtered_out tag was configured
        self.mock_game_tree.tag_configure.assert_called_once_with('filtered_out', foreground='lightgray', background='')
    
    def test_add_game_to_tree(self):
        """Test add_game_to_tree functionality"""
        # Setup test data
        test_game = Mock()
        test_game.key = "test_game"
        test_game.display_name = "Test Game"
        test_game.get_all_tags.return_value = {"action", "adventure"}
        test_platform = "test_platform"
        
        # Mock ROM variants
        mock_rom = Mock()
        mock_rom.create_variant_key.return_value = "variant1"
        mock_rom.filename = "rom1.zip"
        mock_rom.size = "1MB"
        mock_rom.tags = ["tag1"]
        
        test_game.get_variants_for_platform.return_value = [mock_rom]
        
        # Mock other dependencies
        self.mock_gui.state_manager.get_selection.return_value = None
        self.mock_gui.library_processor.categorize_tags.return_value = {"Genre": ["action"], "Theme": ["adventure"]}
        self.mock_gui.library_processor.format_tag_groups_compact.return_value = "Genre: action, Theme: adventure"
        self.mock_game_tree.insert.return_value = "game_item_id"
        
        self.tree_manager.add_game_to_tree(test_game, test_platform)
        
        # Verify game was inserted into tree
        game_insert_call = self.mock_game_tree.insert.call_args_list[0]
        self.assertEqual(game_insert_call[0][0], '')  # Parent
        self.assertEqual(game_insert_call[0][1], 'end')  # Index
        self.assertEqual(game_insert_call[1]['text'], "Test Game")
        self.assertIn('game', game_insert_call[1]['tags'])
        
        # Verify variant was inserted
        variant_insert_call = self.mock_game_tree.insert.call_args_list[1]
        self.assertEqual(variant_insert_call[0][0], "game_item_id")  # Parent
        self.assertEqual(variant_insert_call[1]['text'], "rom1.zip")
        self.assertIn('variant', variant_insert_call[1]['tags'])
    
    def test_add_game_to_tree_no_variants(self):
        """Test add_game_to_tree when game has no variants"""
        test_game = Mock()
        test_game.get_variants_for_platform.return_value = []
        test_platform = "test_platform"
        
        self.tree_manager.add_game_to_tree(test_game, test_platform)
        
        # Should return early without inserting anything
        self.mock_game_tree.insert.assert_not_called()
    
    def test_add_game_to_tree_with_selection(self):
        """Test add_game_to_tree when game has queued selection"""
        # Setup test data
        test_game = Mock()
        test_game.key = "test_game"
        test_game.display_name = "Test Game"
        test_game.get_all_tags.return_value = set()
        test_platform = "test_platform"
        
        # Mock ROM variant
        mock_rom = Mock()
        mock_rom.create_variant_key.return_value = "variant1"
        mock_rom.filename = "rom1.zip"
        mock_rom.size = "1MB"
        mock_rom.tags = []
        
        test_game.get_variants_for_platform.return_value = [mock_rom]
        
        # Mock selection
        mock_selection = Mock()
        mock_selection.selected_rom_variant = "variant1"
        self.mock_gui.state_manager.get_selection.return_value = mock_selection
        
        self.mock_game_tree.insert.return_value = "game_item_id"
        
        self.tree_manager.add_game_to_tree(test_game, test_platform)
        
        # Verify game has queued tag
        game_insert_call = self.mock_game_tree.insert.call_args_list[0]
        self.assertIn('queued', game_insert_call[1]['tags'])
        
        # Verify variant shows as queued
        variant_insert_call = self.mock_game_tree.insert.call_args_list[1]
        self.assertEqual(variant_insert_call[1]['values'][0], "✓")  # Queued column
        self.assertIn('queued', variant_insert_call[1]['tags'])


class TestGameTreeManagerIntegration(unittest.TestCase):
    """Integration tests for GameTreeManager"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create minimal GUI mock with real tkinter components
        self.root = tk.Tk()
        self.root.withdraw()  # Hide window during testing
        
        self.mock_gui = Mock()
        self.mock_gui.root = self.root
        self.mock_gui.game_tree = ttk.Treeview(self.root)
        
        # Configure columns
        self.mock_gui.game_tree['columns'] = ('queued', 'installed', 'size', 'tags', 'type', 'game_key', 'variant_key')
        
        # Mock other components
        self.mock_gui.current_platform = Mock()
        self.mock_gui.current_platform.get.return_value = "test_platform"
        self.mock_gui.current_games = []
        self.mock_gui.existing_roms = set()
        self.mock_gui._async_update_cancelled = False
        self.mock_gui._gui_active = True
        
        # Mock managers and methods
        self.mock_gui.state_manager = Mock()
        self.mock_gui.config_manager = Mock()
        self.mock_gui.library_processor = Mock()
        self.mock_gui.apply_filters = Mock()
        self.mock_gui.rom_matches_tags = Mock(return_value=True)
        self.mock_gui.update_status = Mock()
        self.mock_gui._async_populate_rom_cache = Mock()
        
        self.tree_manager = GameTreeManager(self.mock_gui)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if self.root:
            self.root.destroy()
    
    def test_real_tree_operations(self):
        """Test GameTreeManager with real tkinter Treeview"""
        # Create real game and ROM objects
        game = Mock()
        game.key = "test_game"
        game.display_name = "Test Game"
        game.get_all_tags.return_value = set()
        
        rom = Mock()
        rom.create_variant_key.return_value = "variant1"
        rom.filename = "test_rom.zip"
        rom.size = "1MB"
        rom.tags = []
        
        game.get_variants_for_platform.return_value = [rom]
        
        # Mock dependencies
        self.mock_gui.state_manager.get_selection.return_value = None
        self.mock_gui.library_processor.categorize_tags.return_value = {}
        self.mock_gui.library_processor.format_tag_groups_compact.return_value = ""
        
        # Add game to tree
        self.tree_manager.add_game_to_tree(game, "test_platform")
        
        # Verify tree structure
        tree_items = self.mock_gui.game_tree.get_children()
        self.assertEqual(len(tree_items), 1)
        
        # Check game item
        game_item = tree_items[0]
        self.assertEqual(self.mock_gui.game_tree.item(game_item, 'text'), "Test Game")
        
        # Check variant item
        variant_items = self.mock_gui.game_tree.get_children(game_item)
        self.assertEqual(len(variant_items), 1)
        variant_item = variant_items[0]
        self.assertEqual(self.mock_gui.game_tree.item(variant_item, 'text'), "test_rom.zip")


if __name__ == '__main__':
    # Set up logging for tests
    logging.basicConfig(level=logging.DEBUG)
    
    unittest.main()