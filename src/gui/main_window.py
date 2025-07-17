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
            delay_max=self.config_manager.get_setting("download_delay_max", 5),
            config_manager=self.config_manager
        )
        
        # State variables
        self.available_roms: List[RomInfo] = []
        self.filtered_roms: List[RomInfo] = []
        self.selected_roms: Dict[str, tk.BooleanVar] = {}
        self.current_platform = ""
        self.region_filters: Dict[str, tk.BooleanVar] = {}
        self.existing_roms: set = set()
        self.current_target_path: Optional[Path] = None
        self.current_extract_archives: bool = False
        self.rom_tree_items: Dict[str, str] = {}  # rom.name -> tree item id
        
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
        main_frame.rowconfigure(3, weight=1)
        
        # Platform selection
        ttk.Label(main_frame, text="Platform:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self.platform_var = tk.StringVar()
        self.platform_combo = ttk.Combobox(main_frame, textvariable=self.platform_var, 
                                          values=list(self.config_manager.get_platforms().keys()),
                                          state="readonly")
        self.platform_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 10))
        self.platform_combo.bind('<<ComboboxSelected>>', self.on_platform_selected)
        
        # Filters frame
        filters_frame = ttk.LabelFrame(main_frame, text="Filters", padding="5")
        filters_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Region filter section
        ttk.Label(filters_frame, text="Regions:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        # Initialize region filter checkboxes
        regions = ['USA', 'Europe', 'Japan', 'World', 'English', 'Unknown']
        col = 1
        for region in regions:
            var = tk.BooleanVar()
            # Default to only USA selected
            if region == 'USA':
                var.set(True)
            self.region_filters[region] = var
            
            cb = ttk.Checkbutton(filters_frame, text=region, variable=var, 
                               command=self.apply_region_filter)
            cb.grid(row=0, column=col, sticky=tk.W, padx=(0, 10))
            col += 1
        
        # Content filter section
        ttk.Label(filters_frame, text="Content:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        
        # Initialize content filter checkboxes
        self.ignore_demo_var = tk.BooleanVar()
        self.ignore_demo_var.set(True)  # Default to ignoring demos
        self.ignore_beta_var = tk.BooleanVar()
        self.ignore_beta_var.set(True)  # Default to ignoring betas
        
        ignore_demo_cb = ttk.Checkbutton(filters_frame, text="Ignore Demos", variable=self.ignore_demo_var,
                                       command=self.apply_region_filter)
        ignore_demo_cb.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        
        ignore_beta_cb = ttk.Checkbutton(filters_frame, text="Ignore Betas", variable=self.ignore_beta_var,
                                       command=self.apply_region_filter)
        ignore_beta_cb.grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.scan_button = ttk.Button(control_frame, text="Scan ROMs", command=self.scan_roms)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.select_all_button = ttk.Button(control_frame, text="Select All", command=self.select_all_roms)
        self.select_all_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.deselect_all_button = ttk.Button(control_frame, text="Deselect All", command=self.deselect_all_roms)
        self.deselect_all_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.select_not_installed_button = ttk.Button(control_frame, text="Select Not Installed", command=self.select_not_installed_roms)
        self.select_not_installed_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.delete_button = ttk.Button(control_frame, text="Delete Selected", command=self.delete_selected_roms)
        self.delete_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.download_button = ttk.Button(control_frame, text="Download Selected", command=self.start_download)
        self.download_button.pack(side=tk.RIGHT)
        
        # ROM list frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create treeview for ROM list
        self.rom_tree = ttk.Treeview(list_frame, columns=('selected', 'region', 'size', 'type', 'installed'), show='tree headings')
        self.rom_tree.heading('#0', text='ROM Name')
        self.rom_tree.heading('selected', text='☐')  # Checkbox symbol
        self.rom_tree.heading('region', text='Region')
        self.rom_tree.heading('size', text='Size')
        self.rom_tree.heading('type', text='Type')
        self.rom_tree.heading('installed', text='Installed')
        
        self.rom_tree.column('#0', width=350)
        self.rom_tree.column('selected', width=40, anchor='center')
        self.rom_tree.column('region', width=100)
        self.rom_tree.column('size', width=100)
        self.rom_tree.column('type', width=80)
        self.rom_tree.column('installed', width=70)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rom_tree.yview)
        tree_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.rom_tree.xview)
        self.rom_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        self.rom_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind single-click for checkbox column and double-click to toggle selection
        self.rom_tree.bind('<Button-1>', self.on_tree_click)
        self.rom_tree.bind('<Double-1>', self.toggle_rom_selection)
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Select a platform and click 'Scan ROMs' to begin")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Download progress bar
        ttk.Label(status_frame, text="Download Progress:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        
        # Network copy progress bar
        ttk.Label(status_frame, text="Network Copy Progress:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        self.copy_progress_var = tk.DoubleVar()
        self.copy_progress_bar = ttk.Progressbar(status_frame, variable=self.copy_progress_var, maximum=100)
        self.copy_progress_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        
        # Network copy status label
        self.copy_status_label = ttk.Label(status_frame, text="")
        self.copy_status_label.grid(row=5, column=0, sticky=tk.W, pady=(2, 0))
        
        # Initially disable buttons
        self.update_button_states()
    
    def on_platform_selected(self, event=None):
        """Handle platform selection change."""
        self.current_platform = self.platform_var.get()
        self.update_status(f"Platform selected: {self.current_platform}")
        self.clear_rom_list()
        # Clear cached data for new platform
        self.existing_roms = set()
        self.current_target_path = None
        self.current_extract_archives = False
        self.update_button_states()
        
        # Automatically start scanning for ROMs when platform is selected
        if self.current_platform:
            self.scan_roms()
    
    def scan_roms(self):
        """Scan for available ROMs on the selected platform."""
        if not self.current_platform:
            messagebox.showwarning("No Platform", "Please select a platform first.")
            return
        
        # Run scanning in a separate thread to avoid blocking UI
        threading.Thread(target=self._scan_roms_thread, daemon=True).start()
    
    def _scan_roms_thread(self):
        """Thread function for scanning ROMs."""
        import time
        start_time = time.time()
        
        try:
            logger.info(f"=== Starting ROM scan for platform: {self.current_platform} ===")
            self.update_status("Scanning for ROMs...")
            self.scan_button.config(state='disabled')
            
            # Step 1: Get platform configuration
            logger.info("Step 1: Getting platform configuration...")
            platform_config = self.config_manager.get_platform(self.current_platform)
            if not platform_config:
                logger.error(f"Platform configuration not found for: {self.current_platform}")
                self.update_status("Error: Platform configuration not found")
                return
            
            logger.info(f"Platform config loaded: {platform_config}")
            
            # Step 2: Scrape ROMs from the platform URL
            url = platform_config['url']
            file_pattern = platform_config.get('file_pattern')
            logger.info(f"Step 2: Starting web scraping from URL: {url}")
            logger.info(f"Using file pattern: {file_pattern}")
            
            self.update_status(f"Fetching ROM list from {url}...")
            scrape_start = time.time()
            raw_roms = self.web_scraper.scrape_roms(url, file_pattern)
            scrape_time = time.time() - scrape_start
            logger.info(f"Web scraping completed in {scrape_time:.2f}s")
            
            if not raw_roms:
                logger.warning("No ROMs found from web scraping")
                self.update_status("No ROMs found or unable to connect to the URL")
                return
            
            logger.info(f"Found {len(raw_roms)} raw ROMs from web scraping")
            
            # Step 3: Filter and deduplicate
            self.update_status(f"Found {len(raw_roms)} ROMs, filtering duplicates...")
            logger.info("Step 3: Starting ROM filtering and deduplication...")
            filter_start = time.time()
            filtered_roms = self.rom_filter.filter_and_deduplicate(raw_roms)
            filter_time = time.time() - filter_start
            logger.info(f"ROM filtering completed in {filter_time:.2f}s, {len(filtered_roms)} ROMs after filtering")
            
            # Step 4: Check which ROMs are already downloaded
            logger.info("Step 4: Checking for existing ROMs...")
            self.current_target_path = self.config_manager.get_target_path(self.current_platform)
            if self.current_target_path:
                logger.info(f"Target path: {self.current_target_path}")
                self.current_extract_archives = self.config_manager.should_extract_archives(self.current_platform)
                logger.info(f"Extract archives: {self.current_extract_archives}")
                
                existing_start = time.time()
                logger.info("Starting existing ROM scan with timeout protection...")
                try:
                    # Add timeout protection using threading
                    import threading
                    result_container = {}
                    
                    def scan_with_timeout():
                        try:
                            result_container['roms'] = self.rom_filter.scan_existing_roms(self.current_target_path, self.current_extract_archives)
                            result_container['success'] = True
                        except Exception as e:
                            result_container['error'] = e
                            result_container['success'] = False
                    
                    scan_thread = threading.Thread(target=scan_with_timeout)
                    scan_thread.daemon = True
                    scan_thread.start()
                    scan_thread.join(timeout=30)  # 30 second timeout
                    
                    if scan_thread.is_alive():
                        logger.error("Existing ROM scan timed out after 30 seconds - network drive may be slow or unresponsive")
                        self.existing_roms = set()
                    elif result_container.get('success'):
                        self.existing_roms = result_container['roms']
                        existing_time = time.time() - existing_start
                        logger.info(f"Existing ROM scan completed in {existing_time:.2f}s, found {len(self.existing_roms)} existing ROMs")
                    else:
                        logger.error(f"Existing ROM scan failed: {result_container.get('error')}")
                        self.existing_roms = set()
                        
                except Exception as e:
                    logger.error(f"Error in timeout-protected ROM scan: {e}")
                    self.existing_roms = set()
            else:
                logger.info("No target path configured, skipping existing ROM check")
                self.current_target_path = None
                self.current_extract_archives = False
                self.existing_roms = set()
            
            # Step 5: Update UI
            logger.info("Step 5: Updating UI with ROM list...")
            ui_start = time.time()
            self.root.after(0, self._update_rom_list, filtered_roms)
            ui_time = time.time() - ui_start
            logger.info(f"UI update queued in {ui_time:.2f}s")
            
            total_time = time.time() - start_time
            logger.info(f"=== ROM scan completed successfully in {total_time:.2f}s ===")
            
        except Exception as e:
            logger.error(f"Error scanning ROMs: {e}", exc_info=True)
            self.root.after(0, self.update_status, f"Error scanning ROMs: {e}")
        finally:
            self.root.after(0, lambda: self.scan_button.config(state='normal'))
    
    def _update_rom_list(self, roms: List[RomInfo]):
        """Update the ROM list in the UI (called on main thread)."""
        import time
        start_time = time.time()
        logger.info(f"=== Starting UI ROM list update with {len(roms)} ROMs ===")
        
        self.available_roms = roms
        ui_time = time.time() - start_time
        logger.info(f"ROM list updated in {ui_time:.2f}s, applying region filter...")
        
        filter_start = time.time()
        self.apply_region_filter()
        filter_time = time.time() - filter_start
        logger.info(f"Region filter applied in {filter_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== UI ROM list update completed in {total_time:.2f}s ===")
        
    def apply_region_filter(self):
        """Apply region filtering to the ROM list."""
        import time
        start_time = time.time()
        logger.info("=== Starting region filter application ===")
        
        if not self.available_roms:
            logger.info("No available ROMs to filter")
            return
            
        # Get selected regions
        selected_regions = [region for region, var in self.region_filters.items() if var.get()]
        logger.info(f"Selected regions for filtering: {selected_regions}")
        
        # Filter ROMs by selected regions
        region_start = time.time()
        if selected_regions:
            self.filtered_roms = [rom for rom in self.available_roms if rom.region in selected_regions]
        else:
            self.filtered_roms = self.available_roms
        region_time = time.time() - region_start
        logger.info(f"Region filtering completed in {region_time:.2f}s, {len(self.filtered_roms)} ROMs after region filter")
        
        # Apply content filters (demo/beta)
        content_start = time.time()
        if self.ignore_demo_var.get() or self.ignore_beta_var.get():
            filtered_count_before = len(self.filtered_roms)
            
            def should_ignore_rom(rom):
                name_lower = rom.name.lower()
                clean_name_lower = rom.clean_name.lower()
                
                if self.ignore_demo_var.get():
                    demo_patterns = ['demo', 'kiosk', 'sample', 'promo']
                    if any(pattern in name_lower or pattern in clean_name_lower for pattern in demo_patterns):
                        return True
                
                if self.ignore_beta_var.get():
                    beta_patterns = ['beta', 'alpha', 'prototype', 'test', 'debug']
                    if any(pattern in name_lower or pattern in clean_name_lower for pattern in beta_patterns):
                        return True
                        
                return False
            
            self.filtered_roms = [rom for rom in self.filtered_roms if not should_ignore_rom(rom)]
            filtered_count = filtered_count_before - len(self.filtered_roms)
            logger.info(f"Content filtering removed {filtered_count} demo/beta ROMs")
        
        content_time = time.time() - content_start
        logger.info(f"Content filtering completed in {content_time:.2f}s, {len(self.filtered_roms)} ROMs after content filter")
        
        # Update the display
        logger.info("Clearing existing ROM list display...")
        clear_start = time.time()
        self.clear_rom_list()
        self.selected_roms.clear()
        self.rom_tree_items.clear()
        clear_time = time.time() - clear_start
        logger.info(f"ROM list cleared in {clear_time:.2f}s")
        
        # Skip preloading file sizes/types for performance - just use existing ROM set
        logger.info(f"Using existing ROM set for fast installation checks")
        
        # Add filtered ROMs to the tree
        logger.info(f"Adding {len(self.filtered_roms)} ROMs to tree view...")
        tree_start = time.time()
        
        for i, rom in enumerate(self.filtered_roms):
            if i % 50 == 0:  # Log progress every 50 ROMs
                logger.info(f"Processing ROM {i+1}/{len(self.filtered_roms)}: {rom.clean_name}")
            
            # Check if ROM is installed using fast lookup (no file sizes to avoid network delays)
            is_installed = self._is_rom_installed(rom)
            
            # Determine display values based on installation status
            if is_installed:
                installed_text = "Yes"
                display_size = ""  # Disabled for performance
                display_type = ""  # Disabled for performance
                tags = (rom.name, 'installed')
            else:
                installed_text = "No"
                display_size = rom.size
                display_type = ""  # No type for non-installed games
                tags = (rom.name,)
            
            # Create a tag for each ROM to track selection
            checkbox_symbol = "☑" if self.selected_roms.get(rom.name, tk.BooleanVar()).get() else "☐"
            rom_id = self.rom_tree.insert('', 'end', text=rom.clean_name,
                                         values=(checkbox_symbol, rom.region, display_size, display_type, installed_text),
                                         tags=tags)
            
            # Store the tree item ID for later updates
            self.rom_tree_items[rom.name] = rom_id
            
            # Create boolean variable for selection tracking
            self.selected_roms[rom.name] = tk.BooleanVar()
        
        tree_time = time.time() - tree_start
        logger.info(f"Tree view population completed in {tree_time:.2f}s")
        
        self.update_status(f"Showing {len(self.filtered_roms)} of {len(self.available_roms)} ROMs")
        self.update_button_states()
        
        total_time = time.time() - start_time
        logger.info(f"=== Region filter application completed in {total_time:.2f}s ===")
    
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
        current_tags = list(self.rom_tree.item(item, 'tags'))
        
        if selected:
            if 'selected' not in current_tags:
                current_tags.append('selected')
        else:
            if 'selected' in current_tags:
                current_tags.remove('selected')
        
        self.rom_tree.item(item, tags=tuple(current_tags))
        
        # Update checkbox symbol in the selected column
        current_values = list(self.rom_tree.item(item, 'values'))
        if current_values:
            checkbox_symbol = "☑" if selected else "☐"
            current_values[0] = checkbox_symbol  # First column is the checkbox
            self.rom_tree.item(item, values=tuple(current_values))
        
        # Configure tag appearance
        self.rom_tree.tag_configure('selected', background='lightblue')
        self.rom_tree.tag_configure('installed', background='lightgreen')
    
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
    
    def select_not_installed_roms(self):
        """Select only ROMs that are not installed."""
        for rom in self.filtered_roms:
            if rom.name in self.selected_roms:
                # Check if ROM is installed
                is_installed = self._is_rom_installed(rom)
                # Select only if NOT installed
                self.selected_roms[rom.name].set(not is_installed)
        
        # Update visual display
        for item in self.rom_tree.get_children():
            rom_name = self.rom_tree.item(item, 'text')
            is_selected = rom_name in self.selected_roms and self.selected_roms[rom_name].get()
            self._update_rom_display(item, is_selected)
    
    def on_tree_click(self, event):
        """Handle tree click events, specifically for checkbox column."""
        item = self.rom_tree.identify('item', event.x, event.y)
        column = self.rom_tree.identify('column', event.x, event.y)
        
        # Check if click was on the checkbox column (#1 is first column)
        if item and column == '#1':  # Selected column
            rom_name = self.rom_tree.item(item, 'text')
            if rom_name in self.selected_roms:
                # Toggle selection
                current_value = self.selected_roms[rom_name].get()
                self.selected_roms[rom_name].set(not current_value)
                self._update_rom_display(item, not current_value)
    
    def delete_selected_roms(self):
        """Delete selected ROMs that are installed."""
        # Get selected ROMs that are installed
        selected_installed_roms = []
        for rom in self.filtered_roms:
            if (rom.name in self.selected_roms and 
                self.selected_roms[rom.name].get() and 
                self._is_rom_installed(rom)):
                selected_installed_roms.append(rom)
        
        if not selected_installed_roms:
            messagebox.showwarning("No Selection", 
                                 "Please select installed ROMs to delete.\nOnly installed ROMs can be deleted.")
            return
        
        # Confirm deletion
        rom_names = [rom.clean_name for rom in selected_installed_roms]
        message = f"Are you sure you want to delete {len(rom_names)} ROM(s) from the remote device?\n\n"
        message += "\n".join(rom_names[:10])  # Show first 10
        if len(rom_names) > 10:
            message += f"\n... and {len(rom_names) - 10} more"
        
        if not messagebox.askyesno("Confirm Deletion", message):
            return
        
        # Perform deletion
        deleted_count = 0
        failed_deletions = []
        
        for rom in selected_installed_roms:
            try:
                # Find the actual file on the remote device
                if self.current_target_path:
                    rom_files = list(self.current_target_path.glob(f"{rom.clean_name}.*"))
                    for rom_file in rom_files:
                        if rom_file.is_file():
                            rom_file.unlink()
                            deleted_count += 1
                            logger.info(f"Deleted ROM: {rom_file.name}")
                            break
                    else:
                        failed_deletions.append(rom.clean_name)
            except Exception as e:
                logger.error(f"Failed to delete ROM {rom.clean_name}: {e}")
                failed_deletions.append(rom.clean_name)
        
        # Show results and refresh
        if deleted_count > 0:
            messagebox.showinfo("Deletion Complete", 
                              f"Successfully deleted {deleted_count} ROM(s).")
            # Refresh the ROM list to update installation status
            self.scan_roms()
        
        if failed_deletions:
            messagebox.showerror("Deletion Errors", 
                               f"Failed to delete {len(failed_deletions)} ROM(s):\n" + 
                               "\n".join(failed_deletions[:10]))
    
    def start_download(self):
        """Start downloading selected ROMs."""
        selected_roms = [rom for rom in self.filtered_roms 
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
            
            def completion_callback(rom: RomInfo, success: bool, error: str, final_file_type: str = None):
                if success:
                    self.root.after(0, self.update_status, f"Downloaded: {rom.clean_name}")
                    # Only update to Downloaded if not already handled by extraction callback
                    # This handles the case where no extraction occurs
                    if not self.config_manager.should_extract_archives(self.current_platform):
                        # Update size to final size when download completes (no extraction)
                        if rom.size:
                            try:
                                # Parse size string and convert to bytes for display
                                size_bytes = self._parse_size_string(rom.size)
                                self.root.after(0, self._update_rom_tree_item, rom, 
                                               (size_bytes, size_bytes), "Downloaded", final_file_type)
                            except:
                                self.root.after(0, self._update_rom_tree_item, rom, None, "Downloaded", final_file_type)
                        else:
                            self.root.after(0, self._update_rom_tree_item, rom, None, "Downloaded", final_file_type)
                else:
                    self.root.after(0, self.update_status, f"Failed: {rom.clean_name} - {error}")
                    self.root.after(0, self._update_rom_tree_item, rom, None, "Failed")
            
            def copy_completion_callback(rom: RomInfo, success: bool, error: str):
                if success:
                    self.root.after(0, self.update_status, f"Installed: {rom.clean_name}")
                    self.root.after(0, self._update_rom_tree_item, rom, None, "Installed")
                else:
                    self.root.after(0, self.update_status, f"Copy failed: {rom.clean_name} - {error}")
                    self.root.after(0, self._update_rom_tree_item, rom, None, "Copy Failed")
            
            self.download_manager.download_roms(
                roms, target_path, progress_callback, completion_callback, self.current_platform, copy_completion_callback
            )
            
            self.root.after(0, self.update_status, f"Download session completed")
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            self.root.after(0, self.update_status, f"Download error: {e}")
        finally:
            self.root.after(0, lambda: self.download_button.config(state='normal'))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.copy_progress_var.set(0))
            self.root.after(0, lambda: self.copy_status_label.config(text=""))
    
    def _update_progress(self, progress: DownloadProgress):
        """Update download progress bar and status."""
        if progress.operation == "copying":
            self.copy_progress_var.set(progress.percentage)
            self.copy_status_label.config(text=str(progress))
            # Update ROM tree item for copying status
            self._update_rom_tree_item(progress.rom, status="Copying...")
        elif progress.operation == "extracting":
            self.progress_var.set(0)  # Indeterminate progress for extraction
            self.update_status(f"Extracting {progress.rom.clean_name}...")
            # Update ROM tree item for extraction status
            self._update_rom_tree_item(progress.rom, status="Unarchiving...")
        elif progress.operation == "extracted":
            self.progress_var.set(100)  # Complete extraction
            self.update_status(f"Extracted {progress.rom.clean_name}")
            # Update ROM tree item with final size after extraction and Downloaded status
            size_text = self._format_bytes(progress.current_bytes)
            self._update_rom_tree_item(progress.rom, 
                                     size_progress=(progress.current_bytes, progress.current_bytes),
                                     status="Downloaded")
        else:
            self.progress_var.set(progress.percentage)
            self.update_status(str(progress))
            # Update ROM tree item for download progress
            self._update_rom_tree_item(progress.rom, 
                                      size_progress=(progress.current_bytes, progress.total_bytes),
                                      status="Downloading...")
    
    def _update_rom_tree_item(self, rom: RomInfo, size_progress: tuple = None, status: str = None, file_type: str = None):
        """Update a ROM tree item with new information.
        
        Args:
            rom: ROM information object.
            size_progress: Tuple of (current_bytes, total_bytes) for download progress.
            status: Status text for the installed column.
            file_type: Final file type/extension after extraction.
        """
        if rom.name not in self.rom_tree_items:
            return
        
        item_id = self.rom_tree_items[rom.name]
        current_values = list(self.rom_tree.item(item_id, 'values'))
        
        # Update size column with progress if provided
        if size_progress:
            current_bytes, total_bytes = size_progress
            if total_bytes > 0:
                percentage = (current_bytes / total_bytes) * 100
                size_text = f"{self._format_bytes(current_bytes)}/{self._format_bytes(total_bytes)} ({percentage:.1f}%)"
            else:
                size_text = self._format_bytes(current_bytes)
            current_values[1] = size_text  # Size column
        
        # Update file type column if provided
        if file_type:
            current_values[2] = file_type.upper().replace('.', '')  # Type column, remove dot and uppercase
        
        # Update status column if provided
        if status:
            current_values[3] = status  # Installed column
            
            # If the status is "Installed", add the installed tag and update highlighting
            if status == "Installed":
                current_tags = list(self.rom_tree.item(item_id, 'tags'))
                if 'installed' not in current_tags:
                    current_tags.append('installed')
                self.rom_tree.item(item_id, tags=tuple(current_tags))
        
        self.rom_tree.item(item_id, values=current_values)
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"
    
    def _parse_size_string(self, size_str: str) -> int:
        """Parse a size string like '852.9 MB' back to bytes."""
        if not size_str:
            return 0
        
        try:
            # Remove any extra spaces and split
            parts = size_str.strip().split()
            if len(parts) != 2:
                return 0
            
            value = float(parts[0])
            unit = parts[1].upper()
            
            multipliers = {
                'B': 1,
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024,
                'TB': 1024 * 1024 * 1024 * 1024
            }
            
            return int(value * multipliers.get(unit, 1))
        except:
            return 0
    
    def update_status(self, message: str):
        """Update the status label."""
        self.status_label.config(text=message)
        logger.info(message)
    
    def _is_rom_installed(self, rom: RomInfo) -> bool:
        """Check if a ROM is already installed.
        
        Args:
            rom: ROM information object.
            
        Returns:
            True if the ROM is installed, False otherwise.
        """
        if not self.current_target_path:
            return False
            
        # Use cached existing ROMs set for fast lookup
        normalized_name = self.rom_filter._normalize_name(rom.clean_name)
        return normalized_name in self.existing_roms
    
    def _get_rom_installed_info(self, rom: RomInfo) -> tuple[bool, str, str]:
        """Get detailed information about an installed ROM.
        
        Args:
            rom: ROM information object.
            
        Returns:
            Tuple of (is_installed, file_size, file_type).
        """
        if not self.current_target_path:
            return False, "", ""
        
        return self.rom_filter.get_installed_rom_info(rom, self.current_target_path)
    
    def _get_rom_installed_info_fast(self, rom: RomInfo) -> tuple[bool, str, str]:
        """Get detailed information about an installed ROM using fast lookup.
        
        Args:
            rom: ROM information object.
            
        Returns:
            Tuple of (is_installed, file_size, file_type).
        """
        if not self.current_target_path:
            return False, "", ""
        
        # Use the fast cached approach
        normalized_name = self.rom_filter._normalize_name(rom.clean_name)
        
        # Check if we already have this in our preloaded cache
        if hasattr(self, '_preloaded_roms') and normalized_name in self._preloaded_roms:
            rom_info = self._preloaded_roms[normalized_name]
            return True, rom_info['size'], rom_info['type']
        
        # Fall back to checking if it's in the existing ROMs set (fast)
        if normalized_name in self.existing_roms:
            return True, "", ""  # We know it exists but don't have size/type info
        
        return False, "", ""
    
    def _preload_rom_installation_info(self):
        """Preload installation info for all ROMs in one batch operation."""
        self._preloaded_roms = {}
        
        if not self.current_target_path or not self.current_target_path.exists():
            return
        
        try:
            logger.info(f"Scanning directory for installed ROMs: {self.current_target_path}")
            
            # Get all ROM files in one directory scan
            rom_extensions = {'.rvz', '.zip', '.7z', '.iso', '.gcm', '.bin', '.cue', '.chd'}
            rom_files = []
            
            # Single directory scan to get all ROM files
            for file_path in self.current_target_path.iterdir():
                file_name = file_path.name
                if any(file_name.lower().endswith(ext) for ext in rom_extensions):
                    rom_files.append(file_path)
            
            logger.info(f"Found {len(rom_files)} ROM files, getting file info...")
            
            # Process all ROM files and build the cache
            for i, file_path in enumerate(rom_files):
                if i % 50 == 0 and i > 0:
                    logger.info(f"Processing installed ROM {i}/{len(rom_files)}")
                
                try:
                    # Normalize the name for lookup
                    normalized_name = self.rom_filter._normalize_name(file_path.stem)
                    
                    # Get file size and type
                    size_bytes = file_path.stat().st_size
                    size_str = self._format_bytes(size_bytes)
                    file_type = file_path.suffix.upper().replace('.', '')
                    
                    # Store in preloaded cache
                    self._preloaded_roms[normalized_name] = {
                        'size': size_str,
                        'type': file_type,
                        'filename': file_path.name
                    }
                    
                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not access file {file_path.name}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing file {file_path.name}: {e}")
                    continue
            
            logger.info(f"Preloaded info for {len(self._preloaded_roms)} installed ROMs")
            
        except Exception as e:
            logger.error(f"Error preloading ROM installation info: {e}")
            self._preloaded_roms = {}
    
    def update_button_states(self):
        """Update button states based on current application state."""
        has_platform = bool(self.current_platform)
        has_roms = bool(self.filtered_roms)
        
        self.scan_button.config(state='normal' if has_platform else 'disabled')
        self.select_all_button.config(state='normal' if has_roms else 'disabled')
        self.deselect_all_button.config(state='normal' if has_roms else 'disabled')
        self.select_not_installed_button.config(state='normal' if has_roms else 'disabled')
        self.delete_button.config(state='normal' if has_roms else 'disabled')
        self.download_button.config(state='normal' if has_roms else 'disabled')