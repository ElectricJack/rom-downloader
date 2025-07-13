"""
Main GUI Window for ROM Downloader
Provides the primary user interface for ROM selection and downloading.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from pathlib import Path
from typing import List, Dict, Optional

# Import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config.config import ConfigManager
from scraper.web_scraper import WebScraper, RomInfo
from rom_manager.rom_filter import RomFilter
from downloader.download_manager import DownloadManager, DownloadProgress

logger = logging.getLogger(__name__)

class MainWindow:
    """Main application window for the ROM Downloader."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the main window.
        
        Args:
            root: The root Tkinter window.
        """
        self.root = root
        self.root.title("ROM Downloader")
        self.root.geometry("800x600")
        
        # Initialize components
        self.config_manager = ConfigManager()
        self.web_scraper = WebScraper()
        self.rom_filter = RomFilter(self.config_manager.get_setting("preferred_regions"))
        self.download_manager = DownloadManager(
            temp_path=self.config_manager.get_setting("temp_download_path", "./temp_downloads"),
            delay_min=self.config_manager.get_setting("download_delay_min", 2),
            delay_max=self.config_manager.get_setting("download_delay_max", 5)
        )
        
        # State variables
        self.available_roms: List[RomInfo] = []
        self.selected_roms: Dict[str, tk.BooleanVar] = {}
        self.current_platform = ""
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('rom_downloader.log')
            ]
        )
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Platform selection
        ttk.Label(main_frame, text="Platform:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(main_frame, textvariable=self.platform_var, 
                                          values=list(self.config_manager.get_platforms().keys()),
                                          state="readonly")
        self.platform_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 10))
        self.platform_combo.bind('<<ComboboxSelected>>', self.on_platform_selected)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.scan_button = ttk.Button(control_frame, text="Scan ROMs", command=self.scan_roms)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.select_all_button = ttk.Button(control_frame, text="Select All", command=self.select_all_roms)
        self.select_all_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.deselect_all_button = ttk.Button(control_frame, text="Deselect All", command=self.deselect_all_roms)
        self.deselect_all_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.download_button = ttk.Button(control_frame, text="Download Selected", command=self.start_download)
        self.download_button.pack(side=tk.RIGHT)
        
        # ROM list frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create treeview for ROM list
        self.rom_tree = ttk.Treeview(list_frame, columns=('region', 'size', 'type'), show='tree headings')
        self.rom_tree.heading('#0', text='ROM Name')
        self.rom_tree.heading('region', text='Region')
        self.rom_tree.heading('size', text='Size')
        self.rom_tree.heading('type', text='Type')
        
        self.rom_tree.column('#0', width=400)
        self.rom_tree.column('region', width=100)
        self.rom_tree.column('size', width=100)
        self.rom_tree.column('type', width=80)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rom_tree.yview)
        tree_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.rom_tree.xview)
        self.rom_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        self.rom_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind double-click to toggle selection
        self.rom_tree.bind('<Double-1>', self.toggle_rom_selection)
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Select a platform and click 'Scan ROMs' to begin")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Initially disable buttons
        self.update_button_states()
    
    def on_platform_selected(self, event=None):
        """Handle platform selection change."""
        self.current_platform = self.platform_var.get()
        self.update_status(f"Platform selected: {self.current_platform}")
        self.clear_rom_list()
        self.update_button_states()
    
    def scan_roms(self):
        """Scan for available ROMs on the selected platform."""
        if not self.current_platform:
            messagebox.showwarning("No Platform", "Please select a platform first.")
            return
        
        # Run scanning in a separate thread to avoid blocking UI
        threading.Thread(target=self._scan_roms_thread, daemon=True).start()
    
    def _scan_roms_thread(self):
        """Thread function for scanning ROMs."""
        try:
            self.update_status("Scanning for ROMs...")
            self.scan_button.config(state='disabled')
            
            platform_config = self.config_manager.get_platform(self.current_platform)
            if not platform_config:
                self.update_status("Error: Platform configuration not found")
                return
            
            # Scrape ROMs from the platform URL
            url = platform_config['url']
            file_pattern = platform_config.get('file_pattern')
            
            self.update_status(f"Fetching ROM list from {url}...")
            raw_roms = self.web_scraper.scrape_roms(url, file_pattern)
            
            if not raw_roms:
                self.update_status("No ROMs found or unable to connect to the URL")
                return
            
            self.update_status(f"Found {len(raw_roms)} ROMs, filtering duplicates...")
            
            # Filter and deduplicate
            filtered_roms = self.rom_filter.filter_and_deduplicate(raw_roms)
            
            # Check which ROMs are already downloaded
            target_path = self.config_manager.get_target_path(self.current_platform)
            if target_path:
                existing_roms = self.rom_filter.scan_existing_roms(target_path)
                filtered_roms = self.rom_filter.filter_already_downloaded(filtered_roms, existing_roms)
            
            # Update UI on main thread
            self.root.after(0, self._update_rom_list, filtered_roms)
            
        except Exception as e:
            logger.error(f"Error scanning ROMs: {e}")
            self.root.after(0, self.update_status, f"Error scanning ROMs: {e}")
        finally:
            self.root.after(0, lambda: self.scan_button.config(state='normal'))
    
    def _update_rom_list(self, roms: List[RomInfo]):
        """Update the ROM list in the UI (called on main thread)."""
        self.available_roms = roms
        self.clear_rom_list()
        self.selected_roms.clear()
        
        # Add ROMs to the tree
        for rom in roms:
            # Create a tag for each ROM to track selection
            rom_id = self.rom_tree.insert('', 'end', text=rom.clean_name,
                                         values=(rom.region, rom.size, rom.file_type),
                                         tags=(rom.name,))
            
            # Create boolean variable for selection tracking
            self.selected_roms[rom.name] = tk.BooleanVar()
        
        self.update_status(f"Found {len(roms)} unique ROMs available for download")
        self.update_button_states()
    
    def clear_rom_list(self):
        """Clear the ROM list."""
        for item in self.rom_tree.get_children():
            self.rom_tree.delete(item)
    
    def toggle_rom_selection(self, event):
        """Toggle ROM selection on double-click."""
        item = self.rom_tree.selection()[0] if self.rom_tree.selection() else None
        if item:
            tags = self.rom_tree.item(item, 'tags')
            if tags:
                rom_name = tags[0]
                if rom_name in self.selected_roms:
                    current_value = self.selected_roms[rom_name].get()
                    self.selected_roms[rom_name].set(not current_value)
                    self._update_rom_display(item, not current_value)
    
    def _update_rom_display(self, item, selected: bool):
        """Update the visual display of a ROM's selection state."""
        if selected:
            self.rom_tree.item(item, tags=('selected',))
        else:
            tags = list(self.rom_tree.item(item, 'tags'))
            if 'selected' in tags:
                tags.remove('selected')
            self.rom_tree.item(item, tags=tuple(tags))
        
        # Configure tag appearance
        self.rom_tree.tag_configure('selected', background='lightblue')
    
    def select_all_roms(self):
        """Select all ROMs in the list."""
        for rom_name, var in self.selected_roms.items():
            var.set(True)
        
        # Update visual display
        for item in self.rom_tree.get_children():
            self._update_rom_display(item, True)
    
    def deselect_all_roms(self):
        """Deselect all ROMs in the list."""
        for rom_name, var in self.selected_roms.items():
            var.set(False)
        
        # Update visual display
        for item in self.rom_tree.get_children():
            self._update_rom_display(item, False)
    
    def start_download(self):
        """Start downloading selected ROMs."""
        selected_roms = [rom for rom in self.available_roms 
                        if rom.name in self.selected_roms and self.selected_roms[rom.name].get()]
        
        if not selected_roms:
            messagebox.showwarning("No Selection", "Please select ROMs to download.")
            return
        
        target_path = self.config_manager.get_target_path(self.current_platform)
        if not target_path:
            messagebox.showerror("Configuration Error", 
                               f"Target path not configured for platform: {self.current_platform}")
            return
        
        # Run download in separate thread
        threading.Thread(target=self._download_thread, args=(selected_roms, target_path), daemon=True).start()
    
    def _download_thread(self, roms: List[RomInfo], target_path: Path):
        """Thread function for downloading ROMs."""
        try:
            self.root.after(0, lambda: self.download_button.config(state='disabled'))
            
            def progress_callback(progress: DownloadProgress):
                self.root.after(0, self._update_progress, progress)
            
            def completion_callback(rom: RomInfo, success: bool, error: str):
                if success:
                    self.root.after(0, self.update_status, f"Downloaded: {rom.clean_name}")
                else:
                    self.root.after(0, self.update_status, f"Failed: {rom.clean_name} - {error}")
            
            self.download_manager.download_roms(
                roms, target_path, progress_callback, completion_callback
            )
            
            self.root.after(0, self.update_status, f"Download session completed")
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.root.after(0, self.update_status, f"Download error: {e}")
        finally:
            self.root.after(0, lambda: self.download_button.config(state='normal'))
            self.root.after(0, lambda: self.progress_var.set(0))
    
    def _update_progress(self, progress: DownloadProgress):
        """Update progress bar and status."""
        self.progress_var.set(progress.percentage)
        self.update_status(str(progress))
    
    def update_status(self, message: str):
        """Update the status label."""
        self.status_label.config(text=message)
        logger.info(message)
    
    def update_button_states(self):
        """Update button states based on current application state."""
        has_platform = bool(self.current_platform)
        has_roms = bool(self.available_roms)
        
        self.scan_button.config(state='normal' if has_platform else 'disabled')
        self.select_all_button.config(state='normal' if has_roms else 'disabled')
        self.deselect_all_button.config(state='normal' if has_roms else 'disabled')
        self.download_button.config(state='normal' if has_roms else 'disabled')