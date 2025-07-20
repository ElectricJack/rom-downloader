"""
File Operations Manager for ROM Downloader GUI.

This module handles file operations and system integrations including:
- Import/export of download queues
- Cache management
- Opening system folders and files
- Temporary file cleanup
"""

import sys
import subprocess
import logging
from pathlib import Path
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..game_library_gui import GameLibraryGUI

logger = logging.getLogger(__name__)


class FileOperationsManager:
    """Manages file operations and system integrations."""
    
    def __init__(self, gui: 'GameLibraryGUI'):
        """Initialize the FileOperationsManager.
        
        Args:
            gui: Reference to the main GUI instance
        """
        self.gui = gui
        
    def export_selections(self) -> None:
        """Export download queue to file."""
        platform = self.gui.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                self.gui.state_manager.export_selections(platform, Path(filename))
                messagebox.showinfo("Success", "Download queue exported successfully")
                logger.info(f"Exported selections for platform {platform} to {filename}")
            except Exception as e:
                logger.error(f"Failed to export selections: {e}")
                messagebox.showerror("Error", f"Failed to export queue: {e}")
    
    def import_selections(self) -> None:
        """Import download queue from file."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                success = self.gui.state_manager.import_selections(Path(filename))
                if success:
                    messagebox.showinfo("Success", "Download queue imported successfully")
                    self.gui.refresh_game_list()
                    logger.info(f"Imported selections from {filename}")
                else:
                    messagebox.showerror("Error", "Failed to import queue")
                    logger.warning(f"Import failed for {filename}")
            except Exception as e:
                logger.error(f"Failed to import selections: {e}")
                messagebox.showerror("Error", f"Failed to import queue: {e}")
    
    def clear_cache(self) -> None:
        """Clear application cache."""
        if messagebox.askyesno("Confirm", "Clear all cached data?"):
            try:
                # Clear state manager cache for current platform
                if self.gui.state_manager.platform_library:
                    self.gui.state_manager.platform_library.games.clear()
                    self.gui.state_manager.platform_library.tag_registry.clear()
                    self.gui.state_manager.platform_dirty = True
                
                # Clear installed ROM cache
                self.gui.installation_status_manager.clear_existing_roms_cache()
                
                self.gui.refresh_game_list()
                self.gui.update_status("Cache cleared")
                logger.info("Application cache cleared")
                
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
                messagebox.showerror("Error", f"Failed to clear cache: {e}")
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files."""
        try:
            self.gui.download_manager.cleanup_temp_files()
            self.gui.update_status("Temporary files cleaned up")
            logger.info("Temporary files cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
            messagebox.showerror("Error", f"Failed to cleanup temporary files: {e}")
    
    def open_platform_config(self) -> None:
        """Open the platform configuration file."""
        config_file = self.gui.config_manager.config_file
        try:
            self._open_file_with_system_app(config_file)
            logger.info(f"Opened platform config: {config_file}")
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open config file: {config_file}")
            logger.error(f"Failed to open config file: {config_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config file: {e}")
            logger.error(f"Failed to open config file: {e}")
    
    def open_roms_folder(self) -> None:
        """Open the ROMs folder for the currently selected platform."""
        current_platform = self.gui.current_platform.get()
        if not current_platform:
            messagebox.showwarning("No Platform", "Please select a platform first.")
            return
        
        # Get the target path for the current platform
        target_path = self.gui.config_manager.get_target_directory(current_platform)
        if not target_path:
            messagebox.showerror("Configuration Error", 
                               f"Target path not configured for platform: {current_platform}")
            return
        
        # Ensure the directory exists
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create ROMs folder: {e}")
            logger.error(f"Failed to create ROMs folder {target_path}: {e}")
            return
        
        try:
            self._open_folder_with_system_app(target_path)
            logger.info(f"Opened ROMs folder: {target_path}")
            
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open ROMs folder: {target_path}")
            logger.error(f"Failed to open ROMs folder: {target_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open ROMs folder: {e}")
            logger.error(f"Failed to open ROMs folder: {e}")
    
    def open_temp_folder(self) -> None:
        """Open the temporary download folder."""
        temp_folder = self.gui.download_manager.temp_dir
        
        # Ensure the temp directory exists
        try:
            temp_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create temp folder: {e}")
            logger.error(f"Failed to create temp folder {temp_folder}: {e}")
            return
        
        try:
            self._open_folder_with_system_app(temp_folder)
            logger.info(f"Opened temp folder: {temp_folder}")
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open temp folder: {temp_folder}")
            logger.error(f"Failed to open temp folder: {temp_folder}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open temp folder: {e}")
            logger.error(f"Failed to open temp folder: {e}")
    
    def _open_file_with_system_app(self, file_path: Path) -> None:
        """Open a file with the system's default application.
        
        Args:
            file_path: Path to the file to open
            
        Raises:
            subprocess.CalledProcessError: If the system command fails
        """
        if sys.platform.startswith('win'):
            subprocess.run(['start', str(file_path)], shell=True, check=True)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', str(file_path)], check=True)
        else:
            subprocess.run(['xdg-open', str(file_path)], check=True)
    
    def _open_folder_with_system_app(self, folder_path: Path) -> None:
        """Open a folder with the system's default file manager.
        
        Args:
            folder_path: Path to the folder to open
            
        Raises:
            subprocess.CalledProcessError: If the system command fails
        """
        if sys.platform.startswith('win'):
            subprocess.run(['explorer', str(folder_path)], check=True)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', str(folder_path)], check=True)
        else:
            subprocess.run(['xdg-open', str(folder_path)], check=True)