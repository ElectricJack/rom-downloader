"""
Test cases for DownloadController
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import ttk
import threading
import time

from models.game_library import ROM, Game
from downloader.enhanced_download_manager import DownloadProgress, DownloadResult
from gui.managers.download_controller import DownloadController


class TestDownloadController(unittest.TestCase):
    """Test cases for DownloadController"""
    
    def setUp(self):
        """Set up test environment"""
        # Create mock GUI parent
        self.mock_gui = Mock()
        self.mock_gui.current_platform = Mock()
        self.mock_gui.current_platform.get.return_value = "TestPlatform"
        self.mock_gui.current_games = []
        self.mock_gui._gui_active = True
        self.mock_gui._safe_gui_update = lambda callback: callback()
        self.mock_gui.refresh_game_list = Mock()
        self.mock_gui.installation_status_manager = Mock()
        
        # Create download controller
        self.controller = DownloadController(self.mock_gui)
        
        # Create mock UI components
        self.mock_progress_bar = Mock(spec=ttk.Progressbar)
        self.mock_progress_bar.__setitem__ = Mock()
        self.mock_copy_progress_bar = Mock(spec=ttk.Progressbar)
        self.mock_copy_progress_bar.__setitem__ = Mock()
        self.mock_status_label = Mock(spec=ttk.Label)
        self.mock_copy_status_label = Mock(spec=ttk.Label)
        self.mock_cancel_button = Mock(spec=ttk.Button)
        
        # Set UI components
        self.controller.set_ui_components(
            self.mock_progress_bar, self.mock_copy_progress_bar,
            self.mock_status_label, self.mock_copy_status_label,
            self.mock_cancel_button
        )
        
        # Create mock managers
        self.mock_download_manager = Mock()
        self.mock_state_manager = Mock()
        self.mock_config_manager = Mock()
        
        # Set managers
        self.controller.set_managers(
            self.mock_download_manager, self.mock_state_manager, self.mock_config_manager
        )
    
    def test_initialization(self):
        """Test controller initialization"""
        controller = DownloadController(self.mock_gui)
        
        self.assertEqual(controller.gui, self.mock_gui)
        self.assertFalse(controller.downloading)
        self.assertEqual(controller.installation_count, 0)
        self.assertEqual(controller.total_queued_count, 0)
    
    def test_set_ui_components(self):
        """Test setting UI components"""
        controller = DownloadController(self.mock_gui)
        progress_bar = Mock()
        copy_progress_bar = Mock()
        status_label = Mock()
        copy_status_label = Mock()
        cancel_button = Mock()
        
        controller.set_ui_components(
            progress_bar, copy_progress_bar, status_label, copy_status_label, cancel_button
        )
        
        self.assertEqual(controller.progress_bar, progress_bar)
        self.assertEqual(controller.copy_progress_bar, copy_progress_bar)
        self.assertEqual(controller.status_label, status_label)
        self.assertEqual(controller.copy_status_label, copy_status_label)
        self.assertEqual(controller.cancel_install_button, cancel_button)
    
    def test_set_managers(self):
        """Test setting managers"""
        controller = DownloadController(self.mock_gui)
        download_manager = Mock()
        state_manager = Mock()
        config_manager = Mock()
        
        controller.set_managers(download_manager, state_manager, config_manager)
        
        self.assertEqual(controller.download_manager, download_manager)
        self.assertEqual(controller.state_manager, state_manager)
        self.assertEqual(controller.config_manager, config_manager)
    
    @patch('tkinter.messagebox.showwarning')
    def test_download_selected_no_platform(self, mock_warning):
        """Test download_selected with no platform selected"""
        self.mock_gui.current_platform.get.return_value = ""
        
        self.controller.download_selected()
        
        mock_warning.assert_called_once_with("Warning", "Please select a platform first")
    
    @patch('tkinter.messagebox.showwarning')
    def test_download_selected_already_downloading(self, mock_warning):
        """Test download_selected when already downloading"""
        self.controller.downloading = True
        
        self.controller.download_selected()
        
        mock_warning.assert_called_once_with("Warning", "Download already in progress")
    
    @patch('tkinter.messagebox.showinfo')
    def test_download_selected_no_roms_queued(self, mock_info):
        """Test download_selected with no ROMs queued"""
        self.mock_state_manager.get_selected_roms.return_value = []
        
        self.controller.download_selected()
        
        mock_info.assert_called_once_with("Info", "No ROMs queued for download")
    
    @patch('tkinter.messagebox.showinfo')
    def test_download_selected_all_roms_installed(self, mock_info):
        """Test download_selected when all ROMs are already installed"""
        # Create mock ROM that is already installed
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        mock_rom.is_installed.return_value = True
        
        self.mock_state_manager.get_selected_roms.return_value = [mock_rom]
        
        # First call shows already installed info
        with patch('tkinter.messagebox.showinfo') as mock_info:
            self.controller.download_selected()
            
            # Should show both messages
            expected_calls = [
                call("ROMs Already Installed", "Skipping 1 ROM(s) that are already installed:\n\ntest_rom.zip"),
                call("Nothing to Download", "All queued ROMs are already installed.")
            ]
            mock_info.assert_has_calls(expected_calls)
    
    @patch('tkinter.messagebox.askyesno')
    @patch('threading.Thread')
    def test_download_selected_success(self, mock_thread, mock_confirm):
        """Test successful download_selected"""
        # Create mock ROM that is not installed
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        mock_rom.is_installed.return_value = False
        
        self.mock_state_manager.get_selected_roms.return_value = [mock_rom]
        mock_confirm.return_value = True
        
        # Mock thread
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        self.controller.download_selected()
        
        # Verify download was started
        self.assertTrue(self.controller.downloading)
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        self.mock_gui._set_download_ui_state.assert_called_with(True)
    
    @patch('tkinter.messagebox.askyesno')
    def test_download_selected_cancelled_by_user(self, mock_confirm):
        """Test download_selected cancelled by user"""
        # Create mock ROM that is not installed
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        mock_rom.is_installed.return_value = False
        
        self.mock_state_manager.get_selected_roms.return_value = [mock_rom]
        mock_confirm.return_value = False
        
        self.controller.download_selected()
        
        # Verify download was not started
        self.assertFalse(self.controller.downloading)
    
    def test_download_thread(self):
        """Test _download_thread execution"""
        # Create mock ROMs
        mock_rom1 = Mock(spec=ROM)
        mock_rom1.filename = "rom1.zip"
        mock_rom2 = Mock(spec=ROM)
        mock_rom2.filename = "rom2.zip"
        roms = [mock_rom1, mock_rom2]
        platform = "TestPlatform"
        
        # Mock download manager
        self.mock_download_manager.download_roms.return_value = [True, True]
        self.mock_download_manager.wait_for_all_copies_complete.return_value = True
        
        # Run download thread
        self.controller._download_thread(roms, platform)
        
        # Verify download manager was called
        self.mock_download_manager.download_roms.assert_called_once()
        call_args = self.mock_download_manager.download_roms.call_args[0]
        self.assertEqual(call_args[0], roms)
        self.assertEqual(call_args[1], platform)
        
        # Verify tracking variables
        self.assertEqual(self.controller.total_queued_count, 2)
        self.assertFalse(self.controller.downloading)
    
    def test_update_download_progress_downloading(self):
        """Test _update_download_progress for downloading operation"""
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        
        progress = DownloadProgress(
            rom=mock_rom,
            operation="downloading",
            current_bytes=50,
            total_bytes=100,
            speed_bps=1572864  # 1.5 MB/s in bytes
        )
        
        self.controller._update_download_progress(mock_rom, progress)
        
        # Verify progress bar was updated (50% of 100 bytes)
        self.mock_progress_bar.__setitem__.assert_called_with('value', 50.0)
        self.mock_status_label.config.assert_called_with(
            text="Downloading test_rom.zip - 50.0% (1.5 MB/s)"
        )
    
    def test_update_download_progress_processing(self):
        """Test _update_download_progress for processing operation"""
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        
        progress = DownloadProgress(
            rom=mock_rom,
            operation="processing",
            step="extracting",
            current_bytes=1,
            total_bytes=3
        )
        
        self.controller._update_download_progress(mock_rom, progress)
        
        # Verify progress bar was updated with step percentage
        expected_percentage = (1 / 3) * 100
        self.mock_progress_bar.__setitem__.assert_called_with('value', expected_percentage)
        self.mock_status_label.config.assert_called_with(
            text="Processing test_rom.zip - extracting (step 2/3)"
        )
    
    def test_update_download_progress_processing_indeterminate(self):
        """Test _update_download_progress for indeterminate processing"""
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        
        progress = DownloadProgress(
            rom=mock_rom,
            operation="processing",
            step="validating",
            total_bytes=0
        )
        
        self.controller._update_download_progress(mock_rom, progress)
        
        # Verify progress bar switched to indeterminate mode
        self.mock_progress_bar.configure.assert_called_with(mode='indeterminate')
        self.mock_progress_bar.start.assert_called_once()
        self.mock_status_label.config.assert_called_with(
            text="Processing test_rom.zip - validating"
        )
    
    def test_update_download_completion_success(self):
        """Test _update_download_completion for successful download"""
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        
        result = DownloadResult(rom=mock_rom, success=True)
        
        self.controller._update_download_completion(mock_rom, result)
        
        # Verify progress bar was reset and status updated
        self.mock_progress_bar.stop.assert_called_once()
        self.mock_progress_bar.configure.assert_called_with(mode='determinate')
        self.mock_status_label.config.assert_called_with(text="Downloaded: test_rom.zip")
    
    def test_update_download_completion_failure(self):
        """Test _update_download_completion for failed download"""
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test_rom.zip"
        
        result = DownloadResult(rom=mock_rom, success=False, error_message="Network error")
        
        self.controller._update_download_completion(mock_rom, result)
        
        # Verify progress bar was reset and error status updated
        self.mock_progress_bar.stop.assert_called_once()
        self.mock_progress_bar.configure.assert_called_with(mode='determinate')
        self.mock_status_label.config.assert_called_with(
            text="Failed: test_rom.zip - Network error"
        )
    
    def test_update_copy_progress(self):
        """Test _update_copy_progress"""
        mock_rom = Mock(spec=ROM)
        mock_rom.clean_name = "Test ROM"
        
        progress = DownloadProgress(
            rom=mock_rom,
            current_bytes=75,
            total_bytes=100,
            speed_bps=2097152  # 2.0 MB/s in bytes
        )
        
        self.controller._update_copy_progress(mock_rom, progress)
        
        # Verify copy progress bar was updated
        self.mock_copy_progress_bar.__setitem__.assert_called_with('value', 75.0)
        self.mock_copy_status_label.config.assert_called_with(
            text="Copying Test ROM - 75.0% (2.0 MB/s)"
        )
    
    def test_update_copy_completion_success(self):
        """Test _update_copy_completion for successful copy"""
        mock_rom = Mock(spec=ROM)
        mock_rom.clean_name = "Test ROM"
        mock_rom.filename = "test_rom.zip"
        
        # Create mock game with variants
        mock_game = Mock(spec=Game)
        mock_game.key = "test_game"
        mock_game.variants = {"variant1": mock_rom}
        self.mock_gui.current_games = [mock_game]
        
        result = DownloadResult(rom=mock_rom, success=True)
        
        self.controller._update_copy_completion(mock_rom, result)
        
        # Verify copy progress and status updated
        self.mock_copy_progress_bar.__setitem__.assert_called_with('value', 100)
        self.mock_copy_status_label.config.assert_called_with(text="Installed: Test ROM")
        
        # Verify installation count incremented
        self.assertEqual(self.controller.installation_count, 1)
        
        # Verify ROM was removed from queue
        self.mock_state_manager.remove_selection.assert_called_with("test_game", "TestPlatform")
        
        # Verify game list was refreshed
        self.mock_gui.refresh_game_list.assert_called_once()
    
    def test_update_copy_completion_failure(self):
        """Test _update_copy_completion for failed copy"""
        mock_rom = Mock(spec=ROM)
        mock_rom.clean_name = "Test ROM"
        
        result = DownloadResult(rom=mock_rom, success=False, error_message="Disk full")
        
        self.controller._update_copy_completion(mock_rom, result)
        
        # Verify copy progress was reset and error status updated
        self.mock_copy_progress_bar.__setitem__.assert_called_with('value', 0)
        self.mock_copy_status_label.config.assert_called_with(
            text="Installation failed: Test ROM - Disk full"
        )
        
        # Verify installation count was not incremented
        self.assertEqual(self.controller.installation_count, 0)
    
    @patch('tkinter.messagebox.showinfo')
    def test_installation_complete(self, mock_info):
        """Test _installation_complete"""
        self.controller.installation_count = 3
        self.controller.total_queued_count = 5
        
        self.controller._installation_complete()
        
        # Verify progress bars were reset
        self.mock_progress_bar.__setitem__.assert_called_with('value', 0)
        self.mock_copy_progress_bar.__setitem__.assert_called_with('value', 0)
        
        # Verify status was updated
        self.mock_status_label.config.assert_called_with(
            text="Installation complete: 3/5 successful"
        )
        self.mock_copy_status_label.config.assert_called_with(text="")
        
        # Verify success dialog was shown
        mock_info.assert_called_once_with(
            "Installation Complete", "Successfully installed 3 out of 5 ROMs"
        )
        
        # Verify installed ROM cache was refreshed
        self.mock_gui.installation_status_manager.check_installed_roms.assert_called_once()
    
    @patch('tkinter.messagebox.showwarning')
    def test_installation_timeout_warning(self, mock_warning):
        """Test _installation_timeout_warning"""
        self.controller.installation_count = 2
        self.controller.total_queued_count = 5
        
        self.controller._installation_timeout_warning()
        
        # Verify progress bars were reset
        self.mock_progress_bar.__setitem__.assert_called_with('value', 0)
        self.mock_copy_progress_bar.__setitem__.assert_called_with('value', 0)
        
        # Verify status was updated
        self.mock_status_label.config.assert_called_with(
            text="Installation timeout: 2/5 completed"
        )
        self.mock_copy_status_label.config.assert_called_with(text="")
        
        # Verify timeout warning was shown
        expected_message = ("Installation process timed out. 2 out of 5 ROMs completed.\n"
                          "Some copies may still be in progress.")
        mock_warning.assert_called_once_with("Installation Timeout", expected_message)
        
        # Verify installed ROM cache was refreshed
        self.mock_gui.installation_status_manager.check_installed_roms.assert_called_once()
    
    def test_cancel_download(self):
        """Test cancel_download"""
        self.controller.cancel_download()
        
        # Verify download manager cancel was called
        self.mock_download_manager.cancel_downloads.assert_called_once()
        
        # Verify status was updated
        self.mock_status_label.config.assert_called_with(text="Cancelling download...")
    
    def test_update_status(self):
        """Test update_status"""
        self.controller.update_status("Test message")
        
        self.mock_status_label.config.assert_called_once_with(text="Test message")
    
    def test_update_copy_status(self):
        """Test update_copy_status"""
        self.controller.update_copy_status("Copy message")
        
        self.mock_copy_status_label.config.assert_called_once_with(text="Copy message")
    
    def test_is_downloading(self):
        """Test is_downloading"""
        # Initially not downloading
        self.assertFalse(self.controller.is_downloading())
        
        # Set downloading
        self.controller.downloading = True
        self.assertTrue(self.controller.is_downloading())
        
        # Reset downloading
        self.controller.downloading = False
        self.assertFalse(self.controller.is_downloading())
    
    def test_ui_components_none_handling(self):
        """Test that methods handle None UI components gracefully"""
        # Create controller without UI components
        controller = DownloadController(self.mock_gui)
        controller.set_managers(
            self.mock_download_manager, self.mock_state_manager, self.mock_config_manager
        )
        
        # Test methods that use UI components
        mock_rom = Mock(spec=ROM)
        mock_rom.filename = "test.zip"
        
        progress = DownloadProgress(rom=mock_rom, operation="downloading", current_bytes=50, total_bytes=100)
        result = DownloadResult(rom=mock_rom, success=True)
        
        # These should not raise exceptions
        controller._update_download_progress(mock_rom, progress)
        controller._update_download_completion(mock_rom, result)
        controller._update_copy_progress(mock_rom, progress)
        controller._update_copy_completion(mock_rom, result)
        controller._installation_complete()
        controller._installation_timeout_warning()
    
    def test_gui_inactive_handling(self):
        """Test handling when GUI becomes inactive"""
        self.mock_gui._gui_active = False
        
        # Create mock ROMs
        mock_rom = Mock(spec=ROM)
        roms = [mock_rom]
        platform = "TestPlatform"
        
        # Run download thread - should return early
        self.controller._download_thread(roms, platform)
        
        # Verify download manager was not called
        self.mock_download_manager.download_roms.assert_not_called()


if __name__ == '__main__':
    unittest.main()