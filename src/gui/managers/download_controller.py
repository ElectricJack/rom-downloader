"""
Download Controller for managing ROM downloads and progress tracking.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
from typing import List, Callable, Optional
from pathlib import Path

from src.models.game_library import ROM
from src.downloader.enhanced_download_manager import EnhancedDownloadManager, DownloadProgress, DownloadResult
from src.config.enhanced_config_manager import EnhancedConfigManager
from src.state.distributed_state_manager import DistributedStateManager

logger = logging.getLogger(__name__)


class DownloadController:
    """Manages ROM downloads and progress tracking"""
    
    def __init__(self, gui_parent):
        """Initialize the download controller"""
        self.gui = gui_parent
        self.downloading = False
        self.installation_count = 0
        self.total_queued_count = 0
        
        # References to GUI components
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.copy_progress_bar: Optional[ttk.Progressbar] = None
        self.status_label: Optional[ttk.Label] = None
        self.copy_status_label: Optional[ttk.Label] = None
        self.cancel_install_button: Optional[ttk.Button] = None
        
        # References to managers
        self.download_manager: Optional[EnhancedDownloadManager] = None
        self.state_manager: Optional[DistributedStateManager] = None
        self.config_manager: Optional[EnhancedConfigManager] = None
    
    def set_ui_components(self, progress_bar: ttk.Progressbar, copy_progress_bar: ttk.Progressbar,
                         status_label: ttk.Label, copy_status_label: ttk.Label, 
                         cancel_install_button: ttk.Button):
        """Set references to UI components"""
        self.progress_bar = progress_bar
        self.copy_progress_bar = copy_progress_bar
        self.status_label = status_label
        self.copy_status_label = copy_status_label
        self.cancel_install_button = cancel_install_button
    
    def set_managers(self, download_manager: EnhancedDownloadManager, 
                    state_manager: DistributedStateManager,
                    config_manager: EnhancedConfigManager):
        """Set references to managers"""
        self.download_manager = download_manager
        self.state_manager = state_manager
        self.config_manager = config_manager
    
    def download_selected(self):
        """Download queued ROMs"""
        platform = self.gui.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        if self.downloading:
            messagebox.showwarning("Warning", "Download already in progress")
            return
        
        # Get queued ROMs
        selected_roms = self.state_manager.get_selected_roms(platform)
        
        if not selected_roms:
            messagebox.showinfo("Info", "No ROMs queued for download")
            return
        
        # Filter out already installed ROMs using cached data for speed
        roms_to_download = []
        already_installed = []
        
        for rom in selected_roms:
            # Use cached installation status to avoid expensive real-time checks
            cached_status = rom.is_installed()
            if cached_status is True:
                already_installed.append(rom.filename)
            else:
                # If not cached as installed, include it in download queue
                # Real installation check will happen during actual download process
                # This avoids expensive network checks that slow down the dialog
                roms_to_download.append(rom)
        
        # Inform user about already installed ROMs
        if already_installed:
            skipped_count = len(already_installed)
            message = f"Skipping {skipped_count} ROM(s) that are already installed:\n\n"
            message += "\n".join(already_installed[:10])  # Show first 10
            if len(already_installed) > 10:
                message += f"\n... and {len(already_installed) - 10} more"
            messagebox.showinfo("ROMs Already Installed", message)
        
        if not roms_to_download:
            messagebox.showinfo("Nothing to Download", "All queued ROMs are already installed.")
            return
        
        # Confirm download
        if not messagebox.askyesno("Confirm Download", f"Download {len(roms_to_download)} ROMs from queue?"):
            return
        
        self.downloading = True
        self._set_download_ui_state(downloading=True)
        self.update_status("Starting download...")
        self.update_copy_status("")  # Clear copy status at start
        
        # Start download in separate thread
        thread = threading.Thread(target=self._download_thread, args=(roms_to_download, platform))
        thread.daemon = True
        thread.start()
    
    def _download_thread(self, roms: List[ROM], platform: str):
        """Download ROMs in a separate thread"""
        try:
            # Check if GUI is still active
            if not self.gui._gui_active:
                return
            
            # Initialize tracking variables
            self.installation_count = 0
            self.total_queued_count = len(roms)
                
            def progress_callback(rom: ROM, progress: DownloadProgress):
                self.gui._safe_gui_update(lambda: self._update_download_progress(rom, progress))
            
            def completion_callback(rom: ROM, result: DownloadResult):
                self.gui._safe_gui_update(lambda: self._update_download_completion(rom, result))
            
            def copy_progress_callback(rom: ROM, progress: DownloadProgress):
                self.gui._safe_gui_update(lambda: self._update_copy_progress(rom, progress))
            
            def copy_completion_callback(rom: ROM, result: DownloadResult):
                self.gui._safe_gui_update(lambda: self._update_copy_completion(rom, result))
            
            # Start download with separate copy callbacks
            results = self.download_manager.download_roms(
                roms, platform, progress_callback, completion_callback,
                copy_progress_callback, copy_completion_callback
            )
            
            # Wait for all copies to complete, then show final results
            self.gui._safe_gui_update(lambda: self.update_status("Downloads complete, waiting for all copies to finish..."))
            
            # Wait for all pending copies to complete
            all_copies_complete = self.download_manager.wait_for_all_copies_complete(timeout=300)  # 5 minute timeout
            
            if all_copies_complete:
                self.gui._safe_gui_update(lambda: self._installation_complete())
            else:
                # Timeout occurred, show warning
                self.gui._safe_gui_update(lambda: self._installation_timeout_warning())
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            self.gui._safe_gui_update(lambda: self.update_status(f"Download error: {e}"))
        finally:
            self.downloading = False
            self.gui._safe_gui_update(lambda: self._set_download_ui_state(downloading=False))
    
    def _update_download_progress(self, rom: ROM, progress: DownloadProgress):
        """Update download progress in UI"""
        if not self.progress_bar:
            return
            
        if progress.operation == "downloading":
            self.progress_bar['value'] = progress.percentage
            self.update_status(f"Downloading {rom.filename} - {progress.percentage:.1f}% ({progress.speed_formatted})")
        elif progress.operation == "processing":
            if progress.total_bytes > 0:
                # Show pipeline step progress
                step_percentage = (progress.current_bytes / progress.total_bytes) * 100
                self.progress_bar['value'] = step_percentage
                self.update_status(f"Processing {rom.filename} - {progress.step} (step {progress.current_bytes + 1}/{progress.total_bytes})")
            else:
                # Indeterminate progress for processing
                self.progress_bar.configure(mode='indeterminate')
                self.progress_bar.start()
                self.update_status(f"Processing {rom.filename} - {progress.step}")
    
    def _update_download_completion(self, rom: ROM, result: DownloadResult):
        """Update download completion in UI"""
        if not self.progress_bar:
            return
            
        # Reset progress bar to determinate mode in case it was in indeterminate mode
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')
        
        if result.success:
            self.update_status(f"Downloaded: {rom.filename}")
            # Note: Don't refresh here as copy is still in progress
        else:
            self.update_status(f"Failed: {rom.filename} - {result.error_message}")
    
    def _update_copy_progress(self, rom: ROM, progress: DownloadProgress):
        """Update network copy progress in UI (separate from download progress)"""
        if not self.copy_progress_bar:
            return
            
        # Use the dedicated copy progress bar
        self.copy_progress_bar['value'] = progress.percentage
        self.update_copy_status(f"Copying {rom.clean_name} - {progress.percentage:.1f}% ({progress.speed_formatted})")
    
    def _update_copy_completion(self, rom: ROM, result: DownloadResult):
        """Update copy completion in UI"""
        if not self.copy_progress_bar:
            return
            
        if result.success:
            self.copy_progress_bar['value'] = 100  # Show completion briefly
            self.update_copy_status(f"Installed: {rom.clean_name}")
            self.installation_count += 1
            
            # Remove ROM from selection queue after successful installation
            platform = self.gui.current_platform.get()
            if platform:
                # Find the game key for this ROM
                for game in self.gui.current_games:
                    for variant_key, variant_rom in game.variants.items():
                        if variant_rom.filename == rom.filename:
                            # Remove from queue
                            self.state_manager.remove_selection(game.key, platform)
                            logger.info(f"Removed {game.key} from queue after successful installation")
                            break
            
            # Refresh display to update installed status and queue status after copy completes
            self.gui.refresh_game_list()
        else:
            self.copy_progress_bar['value'] = 0  # Reset on failure
            self.update_copy_status(f"Installation failed: {rom.clean_name} - {result.error_message}")
    
    def _installation_complete(self):
        """Handle installation completion"""
        if self.progress_bar:
            self.progress_bar['value'] = 0
        if self.copy_progress_bar:
            self.copy_progress_bar['value'] = 0
        self.update_status(f"Installation complete: {self.installation_count}/{self.total_queued_count} successful")
        self.update_copy_status("")  # Clear copy status
        messagebox.showinfo("Installation Complete", f"Successfully installed {self.installation_count} out of {self.total_queued_count} ROMs")
        
        # Refresh installed ROM cache
        platform = self.gui.current_platform.get()
        if platform:
            self.gui.installation_status_manager.check_installed_roms()
    
    def _installation_timeout_warning(self):
        """Handle installation timeout warning"""
        if self.progress_bar:
            self.progress_bar['value'] = 0
        if self.copy_progress_bar:
            self.copy_progress_bar['value'] = 0
        self.update_status(f"Installation timeout: {self.installation_count}/{self.total_queued_count} completed")
        self.update_copy_status("")  # Clear copy status
        messagebox.showwarning("Installation Timeout", 
                              f"Installation process timed out. {self.installation_count} out of {self.total_queued_count} ROMs completed.\n"
                              "Some copies may still be in progress.")
        
        # Refresh installed ROM cache
        platform = self.gui.current_platform.get()
        if platform:
            self.gui.installation_status_manager.check_installed_roms()
    
    def _set_download_ui_state(self, downloading: bool):
        """Enable/disable UI elements based on download state"""
        # Delegate to GUI for now, but could be moved here completely later
        self.gui._set_download_ui_state(downloading)
    
    def cancel_download(self):
        """Cancel ongoing download"""
        if self.download_manager:
            self.download_manager.cancel_downloads()
            self.update_status("Cancelling download...")
    
    def update_status(self, message: str):
        """Update download status label"""
        if self.status_label:
            self.status_label.config(text=message)
    
    def update_copy_status(self, message: str):
        """Update copy status label"""
        if self.copy_status_label:
            self.copy_status_label.config(text=message)
    
    def is_downloading(self) -> bool:
        """Check if download is currently in progress"""
        return self.downloading