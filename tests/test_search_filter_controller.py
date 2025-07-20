"""
Test cases for SearchFilterController.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from typing import Set

import sys
import os
from pathlib import Path

# Add src to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)
sys.path.insert(0, project_root)

from gui.managers.search_filter_controller import SearchFilterController
from models.game_library import Game, ROM


class TestSearchFilterController(unittest.TestCase):
    """Test cases for SearchFilterController."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock GUI parent
        self.mock_gui_parent = Mock()
        self.mock_gui_parent.search_query = Mock()
        self.mock_gui_parent.search_query.get.return_value = ""
        self.mock_gui_parent.tag_filter_manager = Mock()
        self.mock_gui_parent.tag_filter_manager.get_active_filters.return_value = set()
        
        # Create controller
        self.controller = SearchFilterController(self.mock_gui_parent)
    
    def create_test_game(self, display_name: str, tags: Set[str] = None) -> Game:
        """Create a test game with specified name and tags."""
        game = Mock(spec=Game)
        game.display_name = display_name
        game.get_all_tags.return_value = tags or set()
        return game
    
    def create_test_rom(self, tags: Set[str] = None) -> ROM:
        """Create a test ROM with specified tags."""
        rom = Mock(spec=ROM)
        rom.tags = tags or set()
        return rom
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertIsNotNone(self.controller.gui_parent)
        self.assertIsNotNone(self.controller.advanced_filter)
        self.assertIsNone(self.controller._filters_changed_callback)
    
    def test_set_filters_changed_callback(self):
        """Test setting filters changed callback."""
        callback = Mock()
        self.controller.set_filters_changed_callback(callback)
        self.assertEqual(self.controller._filters_changed_callback, callback)
    
    def test_on_search_change_calls_callback(self):
        """Test that search change calls the callback."""
        callback = Mock()
        self.controller.set_filters_changed_callback(callback)
        
        self.controller.on_search_change()
        
        callback.assert_called_once()
    
    def test_on_search_change_no_callback(self):
        """Test search change when no callback is set."""
        # Should not raise an exception
        self.controller.on_search_change()
    
    def test_apply_filters_no_filters(self):
        """Test applying filters when no filters are active."""
        games = [
            self.create_test_game("Game 1"),
            self.create_test_game("Game 2"),
            self.create_test_game("Game 3")
        ]
        
        result = self.controller.apply_filters(games)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result, games)
    
    def test_apply_filters_search_only(self):
        """Test applying search filter only."""
        games = [
            self.create_test_game("Super Mario Bros"),
            self.create_test_game("Sonic the Hedgehog"),
            self.create_test_game("Mario Kart")
        ]
        
        self.mock_gui_parent.search_query.get.return_value = "mario"
        
        result = self.controller.apply_filters(games)
        
        self.assertEqual(len(result), 2)
        self.assertIn(games[0], result)  # Super Mario Bros
        self.assertIn(games[2], result)  # Mario Kart
        self.assertNotIn(games[1], result)  # Sonic the Hedgehog
    
    def test_apply_filters_search_case_insensitive(self):
        """Test that search filtering is case insensitive."""
        games = [
            self.create_test_game("SUPER MARIO BROS"),
            self.create_test_game("sonic the hedgehog")
        ]
        
        self.mock_gui_parent.search_query.get.return_value = "MARIO"
        
        result = self.controller.apply_filters(games)
        
        self.assertEqual(len(result), 1)
        self.assertIn(games[0], result)
    
    def test_apply_filters_tag_filters_only(self):
        """Test applying tag filters only."""
        games = [
            self.create_test_game("Game 1", {"action", "platformer"}),
            self.create_test_game("Game 2", {"rpg", "fantasy"}),
            self.create_test_game("Game 3", {"action", "shooter"})
        ]
        
        self.mock_gui_parent.tag_filter_manager.get_active_filters.return_value = {"action"}
        
        # Mock the advanced filter
        with patch.object(self.controller.advanced_filter, 'create_filter_criteria') as mock_criteria, \
             patch.object(self.controller.advanced_filter, 'rom_matches_criteria') as mock_matches:
            
            mock_criteria.return_value = {"action"}
            mock_matches.side_effect = lambda tags, criteria: "action" in tags
            
            result = self.controller.apply_filters(games)
            
            self.assertEqual(len(result), 2)
            self.assertIn(games[0], result)  # Game 1 (action, platformer)
            self.assertIn(games[2], result)  # Game 3 (action, shooter)
            self.assertNotIn(games[1], result)  # Game 2 (rpg, fantasy)
    
    def test_apply_filters_combined(self):
        """Test applying both search and tag filters."""
        games = [
            self.create_test_game("Mario Action Game", {"action", "platformer"}),
            self.create_test_game("Mario RPG Game", {"rpg", "fantasy"}),
            self.create_test_game("Sonic Action Game", {"action", "platformer"})
        ]
        
        self.mock_gui_parent.search_query.get.return_value = "mario"
        self.mock_gui_parent.tag_filter_manager.get_active_filters.return_value = {"action"}
        
        with patch.object(self.controller.advanced_filter, 'create_filter_criteria') as mock_criteria, \
             patch.object(self.controller.advanced_filter, 'rom_matches_criteria') as mock_matches:
            
            mock_criteria.return_value = {"action"}
            mock_matches.side_effect = lambda tags, criteria: "action" in tags
            
            result = self.controller.apply_filters(games)
            
            self.assertEqual(len(result), 1)
            self.assertIn(games[0], result)  # Mario Action Game
    
    def test_game_matches_tags_no_filters(self):
        """Test game matching when no filters are active."""
        game = self.create_test_game("Test Game", {"action"})
        
        result = self.controller.game_matches_tags(game)
        
        self.assertTrue(result)
    
    def test_game_matches_tags_with_filters(self):
        """Test game matching with active filters."""
        game = self.create_test_game("Test Game", {"action", "platformer"})
        filter_tags = {"action"}
        
        with patch.object(self.controller.advanced_filter, 'create_filter_criteria') as mock_criteria, \
             patch.object(self.controller.advanced_filter, 'rom_matches_criteria') as mock_matches:
            
            mock_criteria.return_value = {"action"}
            mock_matches.return_value = True
            
            result = self.controller.game_matches_tags(game, filter_tags)
            
            self.assertTrue(result)
            mock_criteria.assert_called_once_with(filter_tags)
            mock_matches.assert_called_once_with({"action", "platformer"}, {"action"})
    
    def test_game_matches_tags_uses_active_filters_when_none_provided(self):
        """Test that game matching uses active filters when none provided."""
        game = self.create_test_game("Test Game", {"action"})
        self.mock_gui_parent.tag_filter_manager.get_active_filters.return_value = {"action"}
        
        with patch.object(self.controller.advanced_filter, 'create_filter_criteria') as mock_criteria, \
             patch.object(self.controller.advanced_filter, 'rom_matches_criteria') as mock_matches:
            
            mock_criteria.return_value = {"action"}
            mock_matches.return_value = True
            
            result = self.controller.game_matches_tags(game)
            
            self.assertTrue(result)
            self.mock_gui_parent.tag_filter_manager.get_active_filters.assert_called_once()
    
    def test_rom_matches_tags_no_filters(self):
        """Test ROM matching when no filters are active."""
        rom = self.create_test_rom({"action"})
        
        result = self.controller.rom_matches_tags(rom)
        
        self.assertTrue(result)
    
    def test_rom_matches_tags_with_filters(self):
        """Test ROM matching with active filters."""
        rom = self.create_test_rom({"action", "platformer"})
        filter_tags = {"action"}
        
        with patch.object(self.controller.advanced_filter, 'create_filter_criteria') as mock_criteria, \
             patch.object(self.controller.advanced_filter, 'rom_matches_criteria') as mock_matches:
            
            mock_criteria.return_value = {"action"}
            mock_matches.return_value = True
            
            result = self.controller.rom_matches_tags(rom, filter_tags)
            
            self.assertTrue(result)
            mock_criteria.assert_called_once_with(filter_tags)
            mock_matches.assert_called_once_with({"action", "platformer"}, {"action"})
    
    def test_matches_search_query_empty_query(self):
        """Test matching search query when query is empty."""
        result = self.controller.matches_search_query("Test Text")
        
        self.assertTrue(result)
    
    def test_matches_search_query_with_query(self):
        """Test matching search query with actual query."""
        self.mock_gui_parent.search_query.get.return_value = "test"
        
        result_match = self.controller.matches_search_query("Test Text")
        result_no_match = self.controller.matches_search_query("Other Text")
        
        self.assertTrue(result_match)
        self.assertFalse(result_no_match)
    
    def test_matches_search_query_case_insensitive(self):
        """Test that search query matching is case insensitive."""
        result = self.controller.matches_search_query("TEST TEXT", "test")
        
        self.assertTrue(result)
    
    def test_matches_search_query_custom_query(self):
        """Test matching with custom query parameter."""
        result = self.controller.matches_search_query("Test Text", "custom")
        
        self.assertFalse(result)
    
    def test_get_current_search_query(self):
        """Test getting current search query."""
        self.mock_gui_parent.search_query.get.return_value = "test query"
        
        result = self.controller.get_current_search_query()
        
        self.assertEqual(result, "test query")
        self.mock_gui_parent.search_query.get.assert_called_once()
    
    def test_clear_search(self):
        """Test clearing search query."""
        self.controller.clear_search()
        
        self.mock_gui_parent.search_query.set.assert_called_once_with("")
    
    def test_set_search_query(self):
        """Test setting search query."""
        query = "new search query"
        
        self.controller.set_search_query(query)
        
        self.mock_gui_parent.search_query.set.assert_called_once_with(query)
    
    def test_apply_filters_empty_list(self):
        """Test applying filters to empty game list."""
        result = self.controller.apply_filters([])
        
        self.assertEqual(result, [])
    
    def test_apply_filters_preserves_order(self):
        """Test that applying filters preserves the order of games."""
        games = [
            self.create_test_game("Game A"),
            self.create_test_game("Game B"),
            self.create_test_game("Game C")
        ]
        
        result = self.controller.apply_filters(games)
        
        self.assertEqual([g.display_name for g in result], 
                        [g.display_name for g in games])


class TestSearchFilterControllerIntegration(unittest.TestCase):
    """Integration tests for SearchFilterController with real tkinter components."""
    
    def setUp(self):
        """Set up test fixtures with real tkinter components."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during testing
        
        # Create mock GUI parent with real tkinter StringVar
        self.mock_gui_parent = Mock()
        self.mock_gui_parent.search_query = tk.StringVar()
        self.mock_gui_parent.tag_filter_manager = Mock()
        self.mock_gui_parent.tag_filter_manager.get_active_filters.return_value = set()
        
        self.controller = SearchFilterController(self.mock_gui_parent)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.root.destroy()
    
    def test_search_query_integration(self):
        """Test integration with real tkinter StringVar."""
        # Set search query
        self.mock_gui_parent.search_query.set("mario")
        
        # Test getting query
        query = self.controller.get_current_search_query()
        self.assertEqual(query, "mario")
        
        # Test clearing query
        self.controller.clear_search()
        self.assertEqual(self.controller.get_current_search_query(), "")
        
        # Test setting new query
        self.controller.set_search_query("sonic")
        self.assertEqual(self.controller.get_current_search_query(), "sonic")


if __name__ == '__main__':
    unittest.main()