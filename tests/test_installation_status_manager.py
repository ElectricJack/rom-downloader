"""
Test cases for InstallationStatusManager.

This module provides comprehensive test coverage for the InstallationStatusManager class,
including unit tests for ROM installation checking, caching mechanisms, and async operations.
"""

import unittest
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from src.gui.managers.installation_status_manager import InstallationStatusManager
from src.models.game_library import Game, ROM
from src.scraper.web_scraper import RomInfo


class TestInstallationStatusManager(unittest.TestCase):
    """Test suite for InstallationStatusManager."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create mock GUI
        self.mock_gui = Mock()
        self.mock_gui._gui_active = True
        
        # Create mock dependencies
        self.mock_config_manager = Mock()
        self.mock_rom_filter = Mock()
        self.mock_game_tree = Mock()
        
        # Set up GUI mock attributes
        self.mock_gui.config_manager = self.mock_config_manager
        self.mock_gui.rom_filter = self.mock_rom_filter
        self.mock_gui.game_tree = self.mock_game_tree
        self.mock_gui.current_games = []
        self.mock_gui.current_platform = Mock()
        self.mock_gui.progress_bar = Mock()
        self.mock_gui.update_status = Mock()
        self.mock_gui.show_warning = Mock()
        self.mock_gui.refresh_game_list = Mock()
        self.mock_gui._safe_gui_update = Mock(side_effect=lambda callback: callback())
        self.mock_gui.rom_matches_tags = Mock(return_value=True)
        
        # Create the manager
        self.manager = InstallationStatusManager(self.mock_gui)
    
    def test_init(self):
        """Test InstallationStatusManager initialization."""
        self.assertEqual(self.manager.gui, self.mock_gui)
        self.assertEqual(len(self.manager.existing_roms), 0)
        self.assertFalse(self.manager._async_update_cancelled)
    
    def test_property_access(self):
        """Test property access through GUI."""
        self.assertEqual(self.manager.config_manager, self.mock_config_manager)
        self.assertEqual(self.manager.rom_filter, self.mock_rom_filter)
        self.assertEqual(self.manager.game_tree, self.mock_game_tree)
        self.assertEqual(self.manager.current_games, [])
        self.assertTrue(self.manager._gui_active)
    
    def test_is_rom_installed_cached_true(self):
        """Test is_rom_installed with cached True result."""
        # Create mock ROM with cached status
        mock_rom = Mock()
        mock_rom.is_installed.return_value = True
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertTrue(result)
        mock_rom.is_installed.assert_called_once()
    
    def test_is_rom_installed_cached_false(self):
        """Test is_rom_installed with cached False result."""
        # Create mock ROM with cached status
        mock_rom = Mock()
        mock_rom.is_installed.return_value = False
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertFalse(result)
        mock_rom.is_installed.assert_called_once()
    
    def test_is_rom_installed_no_target_directory(self):
        """Test is_rom_installed when no target directory is configured."""
        mock_rom = Mock()
        mock_rom.is_installed.return_value = None  # No cached status
        self.mock_config_manager.get_target_directory.return_value = None
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertFalse(result)
        self.mock_config_manager.get_target_directory.assert_called_once_with("TestPlatform")
    
    def test_is_rom_installed_directory_not_exists(self):
        """Test is_rom_installed when target directory doesn't exist."""
        mock_rom = Mock()
        mock_rom.is_installed.return_value = None
        
        mock_target_dir = Mock()
        mock_target_dir.exists.return_value = False
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertFalse(result)
        mock_target_dir.exists.assert_called_once()
    
    def test_is_rom_installed_directory_error(self):
        """Test is_rom_installed when directory check raises exception."""
        mock_rom = Mock()
        mock_rom.is_installed.return_value = None
        
        mock_target_dir = Mock()
        mock_target_dir.exists.side_effect = OSError("Permission denied")
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertFalse(result)
    
    def test_is_rom_installed_with_cache(self):
        """Test is_rom_installed using existing ROM cache."""
        mock_rom = Mock()
        mock_rom.is_installed.return_value = None
        mock_rom.filename = "TestGame.zip"
        
        mock_target_dir = Mock()
        mock_target_dir.exists.return_value = True
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        # Set up existing ROM cache
        self.manager.existing_roms = {"testgame"}
        
        with patch.object(self.manager, '_precise_rom_match', return_value=True) as mock_match:
            result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertTrue(result)
        mock_match.assert_called_once_with("TestGame.zip", {"testgame"})
        mock_rom.set_installed.assert_called_once_with(True)
    
    def test_is_rom_installed_fallback_to_filter(self):
        """Test is_rom_installed fallback to ROM filter when cache is empty."""
        mock_rom = Mock()
        mock_rom.is_installed.return_value = None
        mock_rom.filename = "TestGame.zip"
        mock_rom.url = "http://example.com/testgame.zip"
        mock_rom.size = 1024
        
        mock_target_dir = Mock()
        mock_target_dir.exists.return_value = True
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        # Empty cache
        self.manager.existing_roms = set()
        
        # Mock ROM filter result
        self.mock_rom_filter.is_rom_installed.return_value = True
        
        result = self.manager.is_rom_installed(mock_rom, "TestPlatform")
        
        self.assertTrue(result)
        self.mock_rom_filter.is_rom_installed.assert_called_once()
        
        # Check RomInfo was created correctly
        call_args = self.mock_rom_filter.is_rom_installed.call_args[0]
        rom_info = call_args[0]
        self.assertEqual(rom_info.name, "TestGame.zip")
        self.assertEqual(rom_info.url, "http://example.com/testgame.zip")
        self.assertEqual(rom_info.size, 1024)
        
        mock_rom.set_installed.assert_called_once_with(True)
    
    def test_precise_rom_match_exact_match(self):
        """Test _precise_rom_match with exact filename match."""
        existing_roms = {"testgame", "anothergame"}
        
        result = self.manager._precise_rom_match("TestGame.zip", existing_roms)
        
        self.assertTrue(result)
    
    def test_precise_rom_match_normalized_match(self):
        """Test _precise_rom_match with normalized name match."""
        existing_roms = {"test_game_normalized"}
        
        self.mock_rom_filter._normalize_name.return_value = "test_game_normalized"
        
        result = self.manager._precise_rom_match("Test-Game.zip", existing_roms)
        
        self.assertTrue(result)
        self.mock_rom_filter._normalize_name.assert_called_once_with("Test-Game")
    
    def test_precise_rom_match_no_match(self):
        """Test _precise_rom_match when no match is found."""
        existing_roms = {"othergame", "differentgame"}
        
        self.mock_rom_filter._normalize_name.return_value = "testgame_normalized"
        
        result = self.manager._precise_rom_match("TestGame.zip", existing_roms)
        
        self.assertFalse(result)
    
    def test_are_same_rom_different_format_identical(self):
        """Test _are_same_rom_different_format with identical names."""
        result = self.manager._are_same_rom_different_format("testgame", "testgame")
        self.assertTrue(result)
    
    def test_are_same_rom_different_format_different(self):
        """Test _are_same_rom_different_format with different names."""
        result = self.manager._are_same_rom_different_format("testgame", "othergame")
        self.assertFalse(result)
    
    def test_check_installed_roms_no_platform(self):
        """Test check_installed_roms with no platform selected."""
        self.mock_gui.current_platform.get.return_value = None
        
        self.manager.check_installed_roms()
        
        self.mock_gui.show_warning.assert_called_once_with("Warning", "Please select a platform first")
    
    def test_check_installed_roms_no_target_dir(self):
        """Test check_installed_roms with no target directory configured."""
        self.mock_gui.current_platform.get.return_value = "TestPlatform"
        self.mock_config_manager.get_target_directory.return_value = None
        
        self.manager.check_installed_roms()
        
        self.mock_gui.show_warning.assert_called_once_with(
            "Warning", "No target directory configured for platform: TestPlatform"
        )
    
    @patch('threading.Thread')
    def test_check_installed_roms_success(self, mock_thread):
        """Test successful check_installed_roms execution."""
        self.mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_target_dir = Mock()
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        self.manager.check_installed_roms()
        
        self.mock_gui.update_status.assert_called_once_with("Scanning for installed ROMs...")
        self.mock_gui.progress_bar.configure.assert_called_once_with(mode='indeterminate')
        self.mock_gui.progress_bar.start.assert_called_once()
        
        mock_thread.assert_called_once()
        thread_args = mock_thread.call_args[1]
        self.assertEqual(thread_args['target'], self.manager._check_installed_thread)
        self.assertEqual(thread_args['args'], ("TestPlatform", mock_target_dir))
    
    def test_check_installed_thread_gui_inactive(self):
        """Test _check_installed_thread when GUI becomes inactive."""
        self.mock_gui._gui_active = False
        
        self.manager._check_installed_thread("TestPlatform", Path("/test"))
        
        # Should return early, no ROM filter calls
        self.mock_rom_filter.scan_existing_roms.assert_not_called()
    
    def test_check_installed_thread_success(self):
        """Test successful _check_installed_thread execution."""
        mock_target_dir = Path("/test")
        expected_roms = {"game1", "game2", "game3"}
        self.mock_rom_filter.scan_existing_roms.return_value = expected_roms
        
        self.manager._check_installed_thread("TestPlatform", mock_target_dir)
        
        self.assertEqual(self.manager.existing_roms, expected_roms)
        self.mock_rom_filter.scan_existing_roms.assert_called_once_with(mock_target_dir)
        self.mock_gui._safe_gui_update.assert_called()
    
    def test_check_installed_thread_exception(self):
        """Test _check_installed_thread with exception during scanning."""
        mock_target_dir = Path("/test")
        self.mock_rom_filter.scan_existing_roms.side_effect = OSError("Scan failed")
        
        self.manager._check_installed_thread("TestPlatform", mock_target_dir)
        
        # Should handle exception gracefully
        self.mock_gui._safe_gui_update.assert_called()
    
    def test_bulk_update_installation_cache_no_games(self):
        """Test _bulk_update_installation_cache with no games."""
        self.manager.current_games = []
        self.manager.existing_roms = {"game1"}
        
        self.manager._bulk_update_installation_cache("TestPlatform")
        
        # Should return early, no processing
    
    def test_bulk_update_installation_cache_no_roms(self):
        """Test _bulk_update_installation_cache with no existing ROMs."""
        mock_game = Mock()
        self.manager.current_games = [mock_game]
        self.manager.existing_roms = set()
        
        self.manager._bulk_update_installation_cache("TestPlatform")
        
        # Should return early, no processing
    
    def test_bulk_update_installation_cache_success(self):
        """Test successful _bulk_update_installation_cache execution."""
        # Create mock game with variants
        mock_game = Mock()
        mock_rom1 = Mock()
        mock_rom1.filename = "game1.zip"
        mock_rom2 = Mock()
        mock_rom2.filename = "game2.zip"
        
        mock_game.get_variants_for_platform.return_value = [mock_rom1, mock_rom2]
        mock_game.clear_installation_cache_for_platform = Mock()
        
        self.manager.current_games = [mock_game]
        self.manager.existing_roms = {"game1"}
        
        with patch.object(self.manager, '_precise_rom_match', side_effect=[True, False]) as mock_match:
            self.manager._bulk_update_installation_cache("TestPlatform")
        
        mock_game.clear_installation_cache_for_platform.assert_called_once_with("TestPlatform")
        mock_match.assert_has_calls([
            call("game1.zip", {"game1"}),
            call("game2.zip", {"game1"})
        ])
        mock_rom1.set_installed.assert_called_once_with(True)
        mock_rom2.set_installed.assert_called_once_with(False)
    
    def test_update_rom_cache(self):
        """Test _update_rom_cache functionality."""
        existing_roms = {"game1", "game2"}
        
        with patch.object(self.manager, '_bulk_update_installation_cache') as mock_bulk_update, \
             patch('threading.Thread') as mock_thread:
            
            self.manager._update_rom_cache(existing_roms, "TestPlatform")
        
        self.assertEqual(self.manager.existing_roms, existing_roms)
        mock_bulk_update.assert_called_once_with("TestPlatform")
        mock_thread.assert_called_once()
        self.mock_gui.update_status.assert_called_once_with("Ready")
    
    def test_check_installed_complete(self):
        """Test _check_installed_complete functionality."""
        self.manager._check_installed_complete(42)
        
        self.mock_gui.update_status.assert_called_once_with("Found 42 installed ROMs")
        self.mock_gui.refresh_game_list.assert_called_once()
    
    def test_clear_existing_roms_cache(self):
        """Test clear_existing_roms_cache functionality."""
        self.manager.existing_roms = {"game1", "game2"}
        
        self.manager.clear_existing_roms_cache()
        
        self.assertEqual(len(self.manager.existing_roms), 0)
    
    def test_cancel_async_updates(self):
        """Test cancel_async_updates functionality."""
        self.assertFalse(self.manager._async_update_cancelled)
        
        self.manager.cancel_async_updates()
        
        self.assertTrue(self.manager._async_update_cancelled)
    
    @patch('threading.Thread')
    def test_start_background_checking(self, mock_thread):
        """Test start_background_checking functionality."""
        mock_target_dir = Mock()
        self.mock_config_manager.get_target_directory.return_value = mock_target_dir
        
        self.manager.start_background_checking("TestPlatform")
        
        mock_thread.assert_called_once()
        thread_args = mock_thread.call_args[1]
        self.assertEqual(thread_args['target'], self.manager._async_populate_rom_cache)
        self.assertEqual(thread_args['args'], ("TestPlatform", mock_target_dir))
    
    def test_start_background_checking_no_target_dir(self):
        """Test start_background_checking with no target directory."""
        self.mock_config_manager.get_target_directory.return_value = None
        
        with patch('threading.Thread') as mock_thread:
            self.manager.start_background_checking("TestPlatform")
        
        mock_thread.assert_not_called()
    
    def test_prepare_cached_game_update_no_tree_item(self):
        """Test _prepare_cached_game_update when tree item doesn't exist."""
        self.mock_game_tree.exists.return_value = False
        
        result = self.manager._prepare_cached_game_update("item1", Mock(), "TestPlatform")
        
        self.assertIsNone(result)
    
    def test_prepare_cached_game_update_success(self):
        """Test successful _prepare_cached_game_update execution."""
        self.mock_game_tree.exists.return_value = True
        self.mock_game_tree.item.return_value = {'tags': ['game', 'queued']}
        
        # Create mock game with installed ROM
        mock_game = Mock()
        mock_rom = Mock()
        mock_rom.is_installed.return_value = True
        mock_game.get_variants_for_platform.return_value = [mock_rom]
        
        result = self.manager._prepare_cached_game_update("item1", mock_game, "TestPlatform")
        
        expected = {
            'item_id': "item1",
            'type': 'game',
            'installed_text': "✓",
            'tags': ('game', 'queued', 'installed', 'queued_installed')
        }
        self.assertEqual(result, expected)
    
    def test_prepare_cached_variant_update_success(self):
        """Test successful _prepare_cached_variant_update execution."""
        self.mock_game_tree.exists.return_value = True
        self.mock_game_tree.set.return_value = "variant_key_1"
        self.mock_game_tree.item.return_value = {'tags': ['variant']}
        
        # Create mock game with matching ROM variant
        mock_game = Mock()
        mock_rom = Mock()
        mock_rom.is_installed.return_value = True
        mock_rom.create_variant_key.return_value = "variant_key_1"
        mock_game.get_variants_for_platform.return_value = [mock_rom]
        
        result = self.manager._prepare_cached_variant_update("item1", mock_game, "TestPlatform")
        
        expected = {
            'item_id': "item1",
            'type': 'variant',
            'installed_text': "✓",
            'tags': ('variant', 'installed')
        }
        self.assertEqual(result, expected)
    
    def test_apply_tree_updates_success(self):
        """Test successful _apply_tree_updates execution."""
        self.mock_game_tree.exists.return_value = True
        self.mock_game_tree.item.return_value = {'values': ['', '', 'Game Name']}
        
        updates = [
            {
                'item_id': 'item1',
                'installed_text': '✓',
                'tags': ('game', 'installed')
            }
        ]
        
        self.manager._apply_tree_updates(updates)
        
        self.mock_game_tree.item.assert_called()
    
    def test_apply_tree_updates_gui_inactive(self):
        """Test _apply_tree_updates when GUI becomes inactive."""
        self.mock_gui._gui_active = False
        
        updates = [{'item_id': 'item1', 'installed_text': '✓', 'tags': ('game',)}]
        
        self.manager._apply_tree_updates(updates)
        
        # Should break early when GUI is inactive
        self.mock_game_tree.exists.assert_not_called()


class TestInstallationStatusManagerAsync(unittest.TestCase):
    """Test suite for async operations in InstallationStatusManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_gui = Mock()
        self.mock_gui._gui_active = True
        self.mock_gui.current_platform = Mock()
        self.mock_gui.current_platform.get.return_value = "TestPlatform"
        self.mock_gui.game_tree = Mock()
        self.mock_gui.game_tree.get_children.return_value = []
        self.mock_gui._safe_gui_update = Mock(side_effect=lambda callback: callback())
        self.mock_gui.update_status = Mock()
        
        self.manager = InstallationStatusManager(self.mock_gui)
    
    def test_async_populate_rom_cache_gui_inactive(self):
        """Test _async_populate_rom_cache when GUI becomes inactive."""
        self.mock_gui._gui_active = False
        
        self.manager._async_populate_rom_cache("TestPlatform", Path("/test"))
        
        # Should return early
        self.mock_gui.update_status.assert_not_called()
    
    def test_async_populate_rom_cache_directory_not_exists(self):
        """Test _async_populate_rom_cache when directory doesn't exist."""
        mock_target_dir = Mock()
        mock_target_dir.exists.return_value = False
        
        self.manager._async_populate_rom_cache("TestPlatform", mock_target_dir)
        
        # Should handle non-existent directory gracefully
        self.mock_gui._safe_gui_update.assert_called()
    
    def test_async_update_tree_from_cache_cancelled(self):
        """Test _async_update_tree_from_cache when cancelled."""
        self.manager._async_update_cancelled = True
        
        self.manager._async_update_tree_from_cache()
        
        # Should return early when cancelled
        self.mock_gui.game_tree.get_children.assert_not_called()
    
    def test_async_update_tree_installation_status_no_platform(self):
        """Test _async_update_tree_installation_status with no platform."""
        self.mock_gui.current_platform.get.return_value = None
        
        self.manager._async_update_tree_installation_status()
        
        # Should return early when no platform
        self.mock_gui.game_tree.get_children.assert_not_called()


if __name__ == '__main__':
    unittest.main()