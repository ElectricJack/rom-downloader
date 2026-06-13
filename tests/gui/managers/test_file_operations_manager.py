"""
Tests for FileOperationsManager.
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog

from src.gui.managers.file_operations_manager import FileOperationsManager


class TestFileOperationsManager:
    """Test suite for FileOperationsManager."""
    
    @pytest.fixture
    def mock_gui(self):
        """Create a mock GUI instance."""
        gui = Mock()
        gui.current_platform = Mock()
        gui.state_manager = Mock()
        gui.config_manager = Mock()
        gui.download_manager = Mock()
        gui.installation_status_manager = Mock()
        gui.refresh_game_list = Mock()
        gui.update_status = Mock()
        return gui
    
    @pytest.fixture
    def file_operations_manager(self, mock_gui):
        """Create FileOperationsManager instance with mock GUI."""
        return FileOperationsManager(mock_gui)
    
    def test_init(self, mock_gui):
        """Test FileOperationsManager initialization."""
        manager = FileOperationsManager(mock_gui)
        assert manager.gui == mock_gui
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_export_selections_success(self, mock_messagebox, mock_filedialog, 
                                     file_operations_manager, mock_gui):
        """Test successful export of selections."""
        # Setup
        mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_filedialog.asksaveasfilename.return_value = "/path/to/export.json"
        mock_gui.state_manager.export_selections = Mock()
        
        # Execute
        file_operations_manager.export_selections()
        
        # Verify
        mock_filedialog.asksaveasfilename.assert_called_once_with(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        mock_gui.state_manager.export_selections.assert_called_once_with(
            "TestPlatform", Path("/path/to/export.json")
        )
        mock_messagebox.showinfo.assert_called_once_with(
            "Success", "Download queue exported successfully"
        )
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_export_selections_no_platform(self, mock_messagebox, 
                                          file_operations_manager, mock_gui):
        """Test export with no platform selected."""
        # Setup
        mock_gui.current_platform.get.return_value = ""
        
        # Execute
        file_operations_manager.export_selections()
        
        # Verify
        mock_messagebox.showwarning.assert_called_once_with(
            "Warning", "Please select a platform first"
        )
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    def test_export_selections_no_filename(self, mock_filedialog, 
                                         file_operations_manager, mock_gui):
        """Test export when user cancels file dialog."""
        # Setup
        mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_filedialog.asksaveasfilename.return_value = ""
        
        # Execute
        file_operations_manager.export_selections()
        
        # Verify - no further calls should be made
        mock_gui.state_manager.export_selections.assert_not_called()
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_export_selections_error(self, mock_messagebox, mock_filedialog,
                                   file_operations_manager, mock_gui):
        """Test export with exception handling."""
        # Setup
        mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_filedialog.asksaveasfilename.return_value = "/path/to/export.json"
        mock_gui.state_manager.export_selections.side_effect = Exception("Export failed")
        
        # Execute
        file_operations_manager.export_selections()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", "Failed to export queue: Export failed"
        )
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_import_selections_success(self, mock_messagebox, mock_filedialog,
                                     file_operations_manager, mock_gui):
        """Test successful import of selections."""
        # Setup
        mock_filedialog.askopenfilename.return_value = "/path/to/import.json"
        mock_gui.state_manager.import_selections.return_value = True
        
        # Execute
        file_operations_manager.import_selections()
        
        # Verify
        mock_filedialog.askopenfilename.assert_called_once_with(
            filetypes=[("JSON files", "*.json")]
        )
        mock_gui.state_manager.import_selections.assert_called_once_with(
            Path("/path/to/import.json")
        )
        mock_messagebox.showinfo.assert_called_once_with(
            "Success", "Download queue imported successfully"
        )
        mock_gui.refresh_game_list.assert_called_once()
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_import_selections_failure(self, mock_messagebox, mock_filedialog,
                                     file_operations_manager, mock_gui):
        """Test import when operation fails."""
        # Setup
        mock_filedialog.askopenfilename.return_value = "/path/to/import.json"
        mock_gui.state_manager.import_selections.return_value = False
        
        # Execute
        file_operations_manager.import_selections()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", "Failed to import queue"
        )
        mock_gui.refresh_game_list.assert_not_called()
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_import_selections_exception(self, mock_messagebox, mock_filedialog,
                                       file_operations_manager, mock_gui):
        """Test import with exception handling."""
        # Setup
        mock_filedialog.askopenfilename.return_value = "/path/to/import.json"
        mock_gui.state_manager.import_selections.side_effect = Exception("Import failed")
        
        # Execute
        file_operations_manager.import_selections()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", "Failed to import queue: Import failed"
        )
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_clear_cache_confirmed(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test cache clearing when user confirms."""
        # Setup
        mock_messagebox.askyesno.return_value = True
        mock_platform_library = Mock()
        mock_platform_library.games = Mock()
        mock_platform_library.tag_registry = Mock()
        mock_gui.state_manager.platform_library = mock_platform_library
        
        # Execute
        file_operations_manager.clear_cache()
        
        # Verify
        mock_messagebox.askyesno.assert_called_once_with("Confirm", "Clear all cached data?")
        mock_platform_library.games.clear.assert_called_once()
        mock_platform_library.tag_registry.clear.assert_called_once()
        assert mock_gui.state_manager.platform_dirty is True
        mock_gui.installation_status_manager.clear_existing_roms_cache.assert_called_once()
        mock_gui.refresh_game_list.assert_called_once()
        mock_gui.update_status.assert_called_once_with("Cache cleared")
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_clear_cache_cancelled(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test cache clearing when user cancels."""
        # Setup
        mock_messagebox.askyesno.return_value = False
        
        # Execute
        file_operations_manager.clear_cache()
        
        # Verify
        mock_gui.installation_status_manager.clear_existing_roms_cache.assert_not_called()
        mock_gui.refresh_game_list.assert_not_called()
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_clear_cache_exception(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test cache clearing with exception."""
        # Setup
        mock_messagebox.askyesno.return_value = True
        mock_gui.state_manager.platform_library = None
        mock_gui.installation_status_manager.clear_existing_roms_cache.side_effect = Exception("Clear failed")
        
        # Execute
        file_operations_manager.clear_cache()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", "Failed to clear cache: Clear failed"
        )
    
    def test_cleanup_temp_files_success(self, file_operations_manager, mock_gui):
        """Test successful temp files cleanup."""
        # Execute
        file_operations_manager.cleanup_temp_files()
        
        # Verify
        mock_gui.download_manager.cleanup_temp_files.assert_called_once()
        mock_gui.update_status.assert_called_once_with("Temporary files cleaned up")
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_cleanup_temp_files_exception(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test temp files cleanup with exception."""
        # Setup
        mock_gui.download_manager.cleanup_temp_files.side_effect = Exception("Cleanup failed")
        
        # Execute
        file_operations_manager.cleanup_temp_files()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", "Failed to cleanup temporary files: Cleanup failed"
        )
    
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_platform_config_success(self, mock_subprocess, file_operations_manager, mock_gui):
        """Test successful opening of platform config."""
        # Setup
        config_file = Path("/path/to/config.json")
        mock_gui.config_manager.config_file = config_file
        
        # Execute
        file_operations_manager.open_platform_config()
        
        # Verify
        mock_subprocess.run.assert_called_once()
    
    @patch('src.gui.managers.file_operations_manager.subprocess')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_open_platform_config_subprocess_error(self, mock_messagebox, mock_subprocess,
                                                  file_operations_manager, mock_gui):
        """Test opening platform config with subprocess error."""
        # Setup
        config_file = Path("/path/to/config.json")
        mock_gui.config_manager.config_file = config_file
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(1, "cmd")
        
        # Execute
        file_operations_manager.open_platform_config()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Error", f"Could not open config file: {config_file}"
        )
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_open_roms_folder_no_platform(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test opening ROMs folder with no platform selected."""
        # Setup
        mock_gui.current_platform.get.return_value = ""
        
        # Execute
        file_operations_manager.open_roms_folder()
        
        # Verify
        mock_messagebox.showwarning.assert_called_once_with(
            "No Platform", "Please select a platform first."
        )
    
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_open_roms_folder_no_target_path(self, mock_messagebox, file_operations_manager, mock_gui):
        """Test opening ROMs folder with no target path configured."""
        # Setup
        mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_gui.config_manager.get_target_directory.return_value = None
        
        # Execute
        file_operations_manager.open_roms_folder()
        
        # Verify
        mock_messagebox.showerror.assert_called_once_with(
            "Configuration Error", 
            "Target path not configured for platform: TestPlatform"
        )
    
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_roms_folder_success(self, mock_subprocess, file_operations_manager, mock_gui):
        """Test successful opening of ROMs folder."""
        # Setup
        target_path = Path("/path/to/roms")
        mock_gui.current_platform.get.return_value = "TestPlatform"
        mock_gui.config_manager.get_target_directory.return_value = target_path
        
        with patch.object(target_path, 'mkdir') as mock_mkdir:
            # Execute
            file_operations_manager.open_roms_folder()
            
            # Verify
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_subprocess.run.assert_called_once()
    
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_temp_folder_success(self, mock_subprocess, file_operations_manager, mock_gui):
        """Test successful opening of temp folder."""
        # Setup
        temp_folder = Path("/path/to/temp")
        mock_gui.download_manager.temp_dir = temp_folder
        
        with patch.object(temp_folder, 'mkdir') as mock_mkdir:
            # Execute
            file_operations_manager.open_temp_folder()
            
            # Verify
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_subprocess.run.assert_called_once()
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_file_with_system_app_windows(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening file on Windows."""
        # Setup
        mock_sys.platform = "win32"
        file_path = Path("/path/to/file.txt")
        
        # Execute
        file_operations_manager._open_file_with_system_app(file_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['start', str(file_path)], shell=True, check=True
        )
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_file_with_system_app_macos(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening file on macOS."""
        # Setup
        mock_sys.platform = "darwin"
        file_path = Path("/path/to/file.txt")
        
        # Execute
        file_operations_manager._open_file_with_system_app(file_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['open', str(file_path)], check=True
        )
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_file_with_system_app_linux(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening file on Linux."""
        # Setup
        mock_sys.platform = "linux"
        file_path = Path("/path/to/file.txt")
        
        # Execute
        file_operations_manager._open_file_with_system_app(file_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['xdg-open', str(file_path)], check=True
        )
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_folder_with_system_app_windows(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening folder on Windows."""
        # Setup
        mock_sys.platform = "win32"
        folder_path = Path("/path/to/folder")
        
        # Execute
        file_operations_manager._open_folder_with_system_app(folder_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['explorer', str(folder_path)], check=True
        )
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_folder_with_system_app_macos(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening folder on macOS."""
        # Setup
        mock_sys.platform = "darwin"
        folder_path = Path("/path/to/folder")
        
        # Execute
        file_operations_manager._open_folder_with_system_app(folder_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['open', str(folder_path)], check=True
        )
    
    @patch('src.gui.managers.file_operations_manager.sys')
    @patch('src.gui.managers.file_operations_manager.subprocess')
    def test_open_folder_with_system_app_linux(self, mock_subprocess, mock_sys, file_operations_manager):
        """Test opening folder on Linux."""
        # Setup
        mock_sys.platform = "linux"
        folder_path = Path("/path/to/folder")
        
        # Execute
        file_operations_manager._open_folder_with_system_app(folder_path)
        
        # Verify
        mock_subprocess.run.assert_called_once_with(
            ['xdg-open', str(folder_path)], check=True
        )


class TestFileOperationsManagerIntegration:
    """Integration tests for FileOperationsManager."""
    
    @pytest.fixture
    def root(self):
        """Create a Tkinter root for integration tests."""
        root = tk.Tk()
        root.withdraw()  # Hide the window
        yield root
        root.destroy()
    
    @pytest.fixture
    def mock_gui_integration(self, root):
        """Create a more realistic mock GUI for integration tests."""
        gui = Mock()
        gui.root = root
        gui.current_platform = tk.StringVar()
        gui.state_manager = Mock()
        gui.config_manager = Mock()
        gui.download_manager = Mock()
        gui.installation_status_manager = Mock()
        gui.refresh_game_list = Mock()
        gui.update_status = Mock()
        return gui
    
    @pytest.fixture
    def file_operations_manager_integration(self, mock_gui_integration):
        """Create FileOperationsManager for integration tests."""
        return FileOperationsManager(mock_gui_integration)
    
    @patch('src.gui.managers.file_operations_manager.filedialog')
    @patch('src.gui.managers.file_operations_manager.messagebox')
    def test_full_export_import_workflow(self, mock_messagebox, mock_filedialog,
                                       file_operations_manager_integration, mock_gui_integration):
        """Test complete export/import workflow."""
        # Setup export
        mock_gui_integration.current_platform.set("TestPlatform")
        export_path = "/path/to/export.json"
        import_path = "/path/to/import.json"
        
        # Test export
        mock_filedialog.asksaveasfilename.return_value = export_path
        file_operations_manager_integration.export_selections()
        
        # Test import
        mock_filedialog.askopenfilename.return_value = import_path
        mock_gui_integration.state_manager.import_selections.return_value = True
        file_operations_manager_integration.import_selections()
        
        # Verify both operations completed
        mock_gui_integration.state_manager.export_selections.assert_called_once()
        mock_gui_integration.state_manager.import_selections.assert_called_once()
        mock_gui_integration.refresh_game_list.assert_called_once()
        
        # Verify success messages
        assert mock_messagebox.showinfo.call_count == 2