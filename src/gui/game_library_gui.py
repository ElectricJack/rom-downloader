"""
Game library GUI with dynamic filtering and game-centric interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import sys
from typing import Dict, Set, List, Optional, Callable
from pathlib import Path

from src.models.game_library import Game, ROM, GameLibrary
from src.state.distributed_state_manager import DistributedStateManager
from src.config.enhanced_config_manager import EnhancedConfigManager
from src.downloader.enhanced_download_manager import EnhancedDownloadManager, DownloadProgress, DownloadResult
from src.processors.game_library_processor import GameLibraryProcessor
from src.scraper.web_scraper import WebScraper, RomInfo
from src.rom_manager.rom_filter import RomFilter
from src.filters.advanced_rom_filter import AdvancedRomFilter, FilterCriteria
from src.gui.managers.tag_filter_manager import TagFilterManager
from src.gui.managers.queue_manager import QueueManager
from src.gui.managers.game_tree_manager import GameTreeManager
from src.gui.managers.installation_status_manager import InstallationStatusManager
from src.gui.managers.download_controller import DownloadController
from src.gui.managers.search_filter_controller import SearchFilterController
from src.gui.managers.tree_event_handler import TreeEventHandler
from src.gui.managers.file_operations_manager import FileOperationsManager
from src.gui.settings_window import SettingsWindow

logger = logging.getLogger(__name__)


class GameLibraryGUI:
    """Game library GUI with dynamic filtering and tree view"""
    
    def __init__(self, root: tk.Tk = None):
        self.root = root or tk.Tk()
        self.root.title("ROM Downloader - Game Library")
        self.root.geometry("1600x800")
        
        # Initialize managers
        self.config_manager = EnhancedConfigManager()
        self.state_manager = DistributedStateManager()
        self.download_manager = EnhancedDownloadManager(self.config_manager)
        self.library_processor = GameLibraryProcessor()
        self.web_scraper = WebScraper()
        self.rom_filter = RomFilter()
        self.advanced_filter = AdvancedRomFilter()
        self.tag_filter_manager = TagFilterManager(self)
        self.queue_manager = QueueManager(self)
        self.game_tree_manager = GameTreeManager(self)
        self.installation_status_manager = InstallationStatusManager(self)
        self.download_controller = DownloadController(self)
        self.search_filter_controller = SearchFilterController(self)
        self.tree_event_handler = TreeEventHandler(self)
        self.file_operations_manager = FileOperationsManager(self)
        
        # GUI state
        self.current_platform = tk.StringVar()
        self.current_platform.trace('w', self.on_platform_change)
        
        self.search_query = tk.StringVar()
        self.search_query.trace('w', self.search_filter_controller.on_search_change)
        
        # UI components
        self.game_tree = None
        self.progress_bar = None
        self.copy_progress_bar = None
        self.status_label = None
        self.copy_status_label = None
        
        # Data
        self.current_games = []
        self._gui_active = True  # Flag to track if GUI is still active
        
        self.setup_ui()
        self.refresh_platform_list()
        self.refresh_network_drive_list()
        
        # Set up managers
        self._setup_managers()
        
        # Set up manager callbacks
        self.tag_filter_manager.set_filters_changed_callback(self.apply_filters_to_tree)
        self.search_filter_controller.set_filters_changed_callback(self.apply_filters_to_tree)
        
        self.restore_last_state()
        
        logger.info("Game library GUI initialized")
    
    def _setup_managers(self):
        """Set up manager dependencies after UI is created"""
        # Set up download controller with UI components and managers
        self.download_controller.set_ui_components(
            self.progress_bar, self.copy_progress_bar,
            self.status_label, self.copy_status_label,
            self.cancel_install_button
        )
        self.download_controller.set_managers(
            self.download_manager, self.state_manager, self.config_manager
        )
    
    def setup_ui(self):
        """Set up the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top section - Platform selection and controls
        self.setup_top_section(main_frame)
        
        # Middle section - Tag filters
        self.tag_filter_manager.setup_tag_filters(main_frame)
        
        # Main content area - Single tree view
        self.setup_main_content(main_frame)
        
        # Bottom section - Progress and status
        self.setup_bottom_section(main_frame)
        
        # Menu bar
        self.setup_menu_bar()
    
    def setup_top_section(self, parent):
        """Set up the top section with platform selection and controls"""
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Platform selection
        ttk.Label(top_frame, text="Platform:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.platform_combo = ttk.Combobox(
            top_frame, 
            textvariable=self.current_platform,
            state="readonly",
            width=30
        )
        self.platform_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Network Drive selection
        ttk.Label(top_frame, text="Network Drive:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.current_network_drive = tk.StringVar()
        self.current_network_drive.trace('w', self.on_network_drive_change)
        
        self.network_drive_combo = ttk.Combobox(
            top_frame,
            textvariable=self.current_network_drive,
            state="readonly",
            width=35
        )
        self.network_drive_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        # Search
        ttk.Label(top_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        
        search_entry = ttk.Entry(top_frame, textvariable=self.search_query, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Buttons
        self.scan_button = ttk.Button(top_frame, text="Scan ROMs", command=self.scan_roms)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.check_installed_button = ttk.Button(top_frame, text="Check Installed", command=self.installation_status_manager.check_installed_roms)
        self.check_installed_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.install_queue_button = ttk.Button(top_frame, text="Install Games in Queue", command=self.download_controller.download_selected)
        self.install_queue_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_queue_button = ttk.Button(top_frame, text="Clear Queue", command=self.clear_selections)
        self.clear_queue_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Cancel Install button (initially disabled)
        self.cancel_install_button = ttk.Button(top_frame, text="Cancel Install", command=self.download_controller.cancel_download, state="disabled")
        self.cancel_install_button.pack(side=tk.LEFT)
    
    
    
    
    def setup_main_content(self, parent):
        """Set up the main content area with single tree view"""
        content_frame = ttk.LabelFrame(parent, text="Games & ROM Variants")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Create treeview with installed column
        columns = ('queued', 'installed', 'size', 'tags', 'item_type', 'game_key', 'variant_key')
        self.game_tree = ttk.Treeview(content_frame, columns=columns, show='tree headings')
        
        # Configure columns
        self.game_tree.heading('#0', text='Name')
        self.game_tree.heading('queued', text='Queued')
        self.game_tree.heading('installed', text='Installed')
        self.game_tree.heading('size', text='Size')
        self.game_tree.heading('tags', text='Tags')
        
        self.game_tree.column('#0', width=400)
        self.game_tree.column('queued', width=80, anchor='center')
        self.game_tree.column('installed', width=80, anchor='center')
        self.game_tree.column('size', width=100, anchor='center')
        self.game_tree.column('tags', width=300)
        self.game_tree.column('item_type', width=0, stretch=False)  # Hidden
        self.game_tree.column('game_key', width=0, stretch=False)   # Hidden
        self.game_tree.column('variant_key', width=0, stretch=False) # Hidden
        
        # Configure tree tag styles
        self.game_tree.tag_configure('installed', background='lightgreen')
        self.game_tree.tag_configure('queued', background='lightblue')
        self.game_tree.tag_configure('queued_installed', background='darkgreen', foreground='white')
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.game_tree.yview)
        tree_scroll_x = ttk.Scrollbar(content_frame, orient=tk.HORIZONTAL, command=self.game_tree.xview)
        self.game_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Pack components
        self.game_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind events through tree event handler
        self.tree_event_handler.bind_events()
        
        # Create context menu
        self.create_context_menu()
    
    def create_context_menu(self):
        """Create right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Add to Queue", command=self.queue_manager.add_to_queue)
        self.context_menu.add_command(label="Remove from Queue", command=self.queue_manager.remove_from_queue)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Add All Variants to Queue", command=self.queue_manager.add_all_variants_to_queue)
        self.context_menu.add_command(label="Remove All Variants from Queue", command=self.queue_manager.remove_all_variants_from_queue)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self.queue_manager.select_all_games)
        self.context_menu.add_command(label="Select None", command=self.queue_manager.select_none_games)
    
    
    
    
    
    
    
    
    
    
    
    def update_game_tree_item(self, game_key: str, platform: str):
        """Update a specific game's tree items without full refresh"""
        # Find the game in current games
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if not game:
            return
        
        # Find the game item in the tree
        game_item = None
        for item_id in self.game_tree.get_children():
            if self.game_tree.set(item_id, 'game_key') == game_key:
                game_item = item_id
                break
        
        if not game_item:
            return
        
        # Get current queue status
        selection = self.state_manager.get_selection(game_key, platform)
        queued_text = "✓" if selection else ""
        
        # Cache variants lookup and installed check
        variants = game.get_variants_for_platform(platform)
        installed_variants = []
        variant_installed_map = {}  # Cache installed status for each variant
        
        for rom in variants:
            is_installed = self.installation_status_manager.is_rom_installed(rom, platform)
            variant_key = rom.create_variant_key()
            variant_installed_map[variant_key] = is_installed
            if is_installed:
                installed_variants.append(rom)
        
        installed_text = "✓" if installed_variants else ""
        
        # Update game item visual styling
        visual_tags = ['game']
        if selection:
            visual_tags.append('queued')
        if installed_variants:
            visual_tags.append('installed')
        if selection and installed_variants:
            visual_tags.append('queued_installed')
        
        # Update game item values and tags
        current_values = list(self.game_tree.item(game_item, 'values'))
        current_values[0] = queued_text  # Queued column
        current_values[1] = installed_text  # Installed column
        self.game_tree.item(game_item, values=tuple(current_values), tags=tuple(visual_tags))
        
        # Update all child ROM variant items
        for child_item in self.game_tree.get_children(game_item):
            child_variant_key = self.game_tree.set(child_item, 'variant_key')
            
            # Check if this specific variant is queued
            variant_queued = ""
            if selection and selection.selected_rom_variant == child_variant_key:
                variant_queued = "✓"
            
            # Use cached installed status
            variant_installed = "✓" if variant_installed_map.get(child_variant_key, False) else ""
            
            # Update variant visual styling
            variant_visual_tags = ['variant']
            if variant_queued:
                variant_visual_tags.append('queued')
            if variant_installed:
                variant_visual_tags.append('installed')
            if variant_queued and variant_installed:
                variant_visual_tags.append('queued_installed')
            
            # Update variant item values and tags
            child_values = list(self.game_tree.item(child_item, 'values'))
            child_values[0] = variant_queued  # Queued column
            child_values[1] = variant_installed  # Installed column
            self.game_tree.item(child_item, values=tuple(child_values), tags=tuple(variant_visual_tags))
    
    def update_game_tree_items_batch(self, game_keys: set, platform: str, skip_installation_check: bool = True):
        """Update multiple game tree items efficiently in batch"""
        if not game_keys:
            return
        
        # Create a lookup map for games to avoid repeated searches
        game_lookup = {}
        for game in self.current_games:
            if game.key in game_keys:
                game_lookup[game.key] = game
        
        # Update each game efficiently
        for game_key in game_keys:
            game = game_lookup.get(game_key)
            if not game:
                continue
                
            # Find the game item in the tree
            game_item = None
            for item_id in self.game_tree.get_children():
                if self.game_tree.set(item_id, 'game_key') == game_key:
                    game_item = item_id
                    break
            
            if not game_item:
                continue
            
            # Get current queue status
            selection = self.state_manager.get_selection(game_key, platform)
            queued_text = "✓" if selection else ""
            
            # For batch operations, skip expensive installation checks to avoid hanging
            if skip_installation_check:
                # Keep existing installed status from tree instead of rechecking
                current_values = list(self.game_tree.item(game_item, 'values'))
                installed_text = current_values[1] if len(current_values) > 1 else ""
                
                # Update game item visual styling (queue status only)
                visual_tags = ['game']
                if selection:
                    visual_tags.append('queued')
                if installed_text == "✓":
                    visual_tags.append('installed')
                if selection and installed_text == "✓":
                    visual_tags.append('queued_installed')
                
                # Update game item values and tags
                current_values[0] = queued_text  # Queued column
                self.game_tree.item(game_item, values=tuple(current_values), tags=tuple(visual_tags))
                
                # Update all child ROM variant items
                for child_item in self.game_tree.get_children(game_item):
                    child_variant_key = self.game_tree.set(child_item, 'variant_key')
                    
                    # Check if this specific variant is queued
                    variant_queued = ""
                    if selection and selection.selected_rom_variant == child_variant_key:
                        variant_queued = "✓"
                    
                    # Keep existing installed status
                    child_values = list(self.game_tree.item(child_item, 'values'))
                    variant_installed = child_values[1] if len(child_values) > 1 else ""
                    
                    # Update variant visual styling
                    variant_visual_tags = ['variant']
                    if variant_queued:
                        variant_visual_tags.append('queued')
                    if variant_installed == "✓":
                        variant_visual_tags.append('installed')
                    if variant_queued and variant_installed == "✓":
                        variant_visual_tags.append('queued_installed')
                    
                    # Update variant item values and tags
                    child_values[0] = variant_queued  # Queued column
                    self.game_tree.item(child_item, values=tuple(child_values), tags=tuple(variant_visual_tags))
            else:
                # Full update with installation checks (slower but accurate)
                variants = game.get_variants_for_platform(platform)
                installed_variants = []
                variant_installed_map = {}  # Cache installed status for each variant
                
                for rom in variants:
                    is_installed = self.installation_status_manager.is_rom_installed(rom, platform)
                    variant_key = rom.create_variant_key()
                    variant_installed_map[variant_key] = is_installed
                    if is_installed:
                        installed_variants.append(rom)
                
                installed_text = "✓" if installed_variants else ""
                
                # Update game item visual styling
                visual_tags = ['game']
                if selection:
                    visual_tags.append('queued')
                if installed_variants:
                    visual_tags.append('installed')
                if selection and installed_variants:
                    visual_tags.append('queued_installed')
                
                # Update game item values and tags
                current_values = list(self.game_tree.item(game_item, 'values'))
                current_values[0] = queued_text  # Queued column
                current_values[1] = installed_text  # Installed column
                self.game_tree.item(game_item, values=tuple(current_values), tags=tuple(visual_tags))
                
                # Update all child ROM variant items
                for child_item in self.game_tree.get_children(game_item):
                    child_variant_key = self.game_tree.set(child_item, 'variant_key')
                    
                    # Check if this specific variant is queued
                    variant_queued = ""
                    if selection and selection.selected_rom_variant == child_variant_key:
                        variant_queued = "✓"
                    
                    # Use cached installed status
                    variant_installed = "✓" if variant_installed_map.get(child_variant_key, False) else ""
                    
                    # Update variant visual styling
                    variant_visual_tags = ['variant']
                    if variant_queued:
                        variant_visual_tags.append('queued')
                    if variant_installed:
                        variant_visual_tags.append('installed')
                    if variant_queued and variant_installed:
                        variant_visual_tags.append('queued_installed')
                    
                    # Update variant item values and tags
                    child_values = list(self.game_tree.item(child_item, 'values'))
                    child_values[0] = variant_queued  # Queued column
                    child_values[1] = variant_installed  # Installed column
                    self.game_tree.item(child_item, values=tuple(child_values), tags=tuple(variant_visual_tags))
    
    def setup_bottom_section(self, parent):
        """Set up the bottom section with progress and status"""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Download progress section
        download_progress_frame = ttk.Frame(bottom_frame)
        download_progress_frame.pack(fill=tk.X, pady=(0, 2))
        
        download_label = ttk.Label(download_progress_frame, text="Download Progress:")
        download_label.pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(download_progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(2, 0))
        
        # Copy progress section  
        copy_progress_frame = ttk.Frame(bottom_frame)
        copy_progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        copy_label = ttk.Label(copy_progress_frame, text="Network Copy Progress:")
        copy_label.pack(anchor=tk.W)
        
        self.copy_progress_bar = ttk.Progressbar(copy_progress_frame, mode='determinate')
        self.copy_progress_bar.pack(fill=tk.X, pady=(2, 0))
        
        # Copy status label
        self.copy_status_label = ttk.Label(copy_progress_frame, text="")
        self.copy_status_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Download status label
        self.status_label = ttk.Label(bottom_frame, text="Ready")
        self.status_label.pack(anchor=tk.W, pady=(5, 0))
    
    def setup_menu_bar(self):
        """Set up the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Platform Config", command=self.file_operations_manager.open_platform_config)
        file_menu.add_command(label="Open ROMs Folder", command=self.file_operations_manager.open_roms_folder)
        file_menu.add_command(label="Open Temp Download Folder", command=self.file_operations_manager.open_temp_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Queue...", command=self.file_operations_manager.export_selections)
        file_menu.add_command(label="Import Queue...", command=self.file_operations_manager.import_selections)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Settings...", command=self.show_settings)
        tools_menu.add_separator()
        tools_menu.add_command(label="Clear Cache", command=self.file_operations_manager.clear_cache)
        tools_menu.add_command(label="Cleanup Temp Files", command=self.file_operations_manager.cleanup_temp_files)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def refresh_platform_list(self):
        """Refresh the platform selection dropdown"""
        platforms = self.config_manager.get_platform_display_names()
        self.platform_combo['values'] = list(platforms.keys())
        
        if platforms and not self.current_platform.get():
            self.current_platform.set(list(platforms.keys())[0])
    
    def refresh_network_drive_list(self):
        """Refresh the network drive selection dropdown"""
        network_drives = self.config_manager.get_network_drive_paths()
        self.network_drive_combo['values'] = network_drives
        
        # Set current drive
        current_drive = self.config_manager.get_current_network_drive_path()
        if current_drive and current_drive in network_drives:
            self.current_network_drive.set(current_drive)
        elif network_drives:
            self.current_network_drive.set(network_drives[0])
            self.config_manager.set_current_network_drive_path(network_drives[0])
    
    def on_network_drive_change(self, *_args):
        """Handle network drive selection change"""
        drive = self.current_network_drive.get()
        if drive:
            try:
                self.config_manager.set_current_network_drive_path(drive)
                self.config_manager.save_config()
                logger.info(f"Changed network drive to: {drive}")
                
                # Clear ROM cache since network drive changed
                self.installation_status_manager.clear_existing_roms_cache()
                
                # Refresh installation status for current platform if any
                platform = self.current_platform.get()
                if platform:
                    self.installation_status_manager.start_background_checking(platform)
            except Exception as e:
                logger.error(f"Error changing network drive: {e}")
                messagebox.showerror("Error", f"Failed to change network drive: {e}")
    
    def restore_last_state(self):
        """Restore the last application state"""
        import time
        start_time = time.time()
        logger.info("=== restore_last_state() started ===")
        
        # Restore last selected platform
        last_platform = self.state_manager.get_last_selected_platform()
        if last_platform:
            available_platforms = self.config_manager.get_platform_display_names()
            if last_platform in available_platforms:
                self.current_platform.set(last_platform)
                logger.info(f"Restored last selected platform: {last_platform}")
            else:
                logger.warning(f"Last selected platform '{last_platform}' not available")
        
        # Refresh the display to show any existing games and selections
        platform = self.current_platform.get()
        if platform:
            tag_start = time.time()
            platform_tags = self.state_manager.get_platform_tags(platform)
            categorized_tags = self.library_processor.categorize_tags(platform_tags) if platform_tags else {}
            self.tag_filter_manager.update_tag_buttons(platform, categorized_tags)
            tag_time = time.time() - tag_start
            logger.info(f"update_tag_buttons() took {tag_time:.2f}s")
            
            refresh_start = time.time()
            self.refresh_game_list()
            refresh_time = time.time() - refresh_start
            logger.info(f"refresh_game_list() took {refresh_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== restore_last_state() completed in {total_time:.2f}s ===")
    
    def on_platform_change(self, *_args):
        """Handle platform selection change"""
        import time
        start_time = time.time()
        
        platform = self.current_platform.get()
        if platform:
            logger.info(f"=== on_platform_change() to {platform} ===")
            
            # Save the last selected platform
            save_start = time.time()
            self.state_manager.set_last_selected_platform(platform)
            save_time = time.time() - save_start
            logger.info(f"set_last_selected_platform() took {save_time:.2f}s")
            
            tag_start = time.time()
            platform_tags = self.state_manager.get_platform_tags(platform)
            categorized_tags = self.library_processor.categorize_tags(platform_tags) if platform_tags else {}
            self.tag_filter_manager.update_tag_buttons(platform, categorized_tags)
            tag_time = time.time() - tag_start
            logger.info(f"update_tag_buttons() took {tag_time:.2f}s")
            
            # Clear existing ROM cache when platform changes
            self.installation_status_manager.clear_existing_roms_cache()
            # Force a full rebuild since platform changed
            self.current_games = []  # This will trigger a rebuild
            
            refresh_start = time.time()
            self.refresh_game_list()
            refresh_time = time.time() - refresh_start
            logger.info(f"refresh_game_list() took {refresh_time:.2f}s")
            
            # Start background installation status checking
            self.installation_status_manager.start_background_checking(platform)
            
            total_time = time.time() - start_time
            logger.info(f"=== on_platform_change() completed in {total_time:.2f}s ===")
    
    
    
    
    
    
    def refresh_game_list(self):
        """Refresh the game list display"""
        self.game_tree_manager.refresh_game_list()

    
    def rebuild_game_tree(self, games: List[Game], platform: str):
        """Rebuild the entire game tree (only when data changes)"""
        self.game_tree_manager.rebuild_game_tree(games, platform)
    
    def apply_filters_to_tree(self):
        """Apply current filters by showing/hiding tree items (fast)"""
        self.game_tree_manager.apply_filters_to_tree()
    
    
    def apply_filters(self, games: List[Game]) -> List[Game]:
        """Apply current filters to game list"""
        return self.search_filter_controller.apply_filters(games)
    
    def game_matches_tags(self, game: Game, filter_tags: Set[str] = None) -> bool:
        """Check if game matches current tag filters using advanced filtering logic"""
        return self.search_filter_controller.game_matches_tags(game, filter_tags)
    
    def rom_matches_tags(self, rom, filter_tags: Set[str] = None) -> bool:
        """Check if ROM variant matches current tag filters using advanced filtering logic"""
        return self.search_filter_controller.rom_matches_tags(rom, filter_tags)
    
    def add_game_to_tree(self, game: Game, platform: str):
        """Add a game and its variants to the treeview"""
        self.game_tree_manager.add_game_to_tree(game, platform)
    

    def _safe_gui_update(self, callback):
        """Safely update GUI from background thread, handling main loop errors"""
        if not self._gui_active:
            return
        
        try:
            self.root.after(0, callback)
        except RuntimeError as e:
            if "main thread is not in main loop" in str(e):
                logger.debug("GUI main loop no longer active, skipping update")
                self._gui_active = False  # Update flag to prevent future attempts
            else:
                logger.error(f"Unexpected GUI update error: {e}")
        except Exception as e:
            logger.error(f"Error updating GUI: {e}")

    
    
    
    def scan_roms(self):
        """Scan for ROMs on the selected platform"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        if self.download_controller.is_downloading():
            messagebox.showwarning("Warning", "Download in progress")
            return
        
        self.update_status("Scanning ROMs...")
        self.progress_bar.configure(mode='indeterminate')
        self.progress_bar.start()
        
        # Run scan in a separate thread
        import threading
        thread = threading.Thread(target=self._scan_roms_thread, args=(platform,))
        thread.daemon = True
        thread.start()
    
    def _scan_roms_thread(self, platform: str):
        """Scan ROMs in a separate thread"""
        try:
            # Check if GUI is still active
            if not self._gui_active:
                return
                
            # Get platform configuration
            platform_config = self.config_manager.get_platform_config(platform)
            if not platform_config:
                self._safe_gui_update(lambda: self.update_status("Platform configuration not found"))
                return
            
            # Scrape ROMs
            url = platform_config['url']
            file_pattern = platform_config.get('file_pattern')
            
            roms = self.web_scraper.scrape_roms(url, file_pattern)
            
            if not roms:
                self._safe_gui_update(lambda: self.update_status("No ROMs found"))
                return
            
            # Process into library
            library = self.library_processor.process_rom_collection(roms, platform)
            
            # Merge with existing library using transaction to batch saves
            with self.state_manager:
                for game in library.games.values():
                    self.state_manager.add_game(game)
            
            # Update UI
            self._safe_gui_update(lambda: self._scan_complete(len(library.games)))
            
        except Exception as e:
            logger.error(f"Error scanning ROMs: {e}")
            self._safe_gui_update(lambda: self.update_status(f"Error: {e}"))
        finally:
            self._safe_gui_update(lambda: self.progress_bar.stop())
            self._safe_gui_update(lambda: self.progress_bar.configure(mode='determinate'))
    
    def _scan_complete(self, count: int):
        """Handle scan completion"""
        self.update_status(f"Scan complete: {count} games found")
        platform = self.current_platform.get()
        platform_tags = self.state_manager.get_platform_tags(platform)
        categorized_tags = self.library_processor.categorize_tags(platform_tags) if platform_tags else {}
        self.tag_filter_manager.update_tag_buttons(platform, categorized_tags)
        self.refresh_game_list()
    
    
    
    
    
    
    
    
    
    def clear_selections(self):
        """Clear all queued items for current platform"""
        platform = self.current_platform.get()
        if not platform:
            return
        
        if messagebox.askyesno("Confirm", "Clear download queue for this platform?"):
            self.state_manager.clear_platform_selections(platform)
            # Use targeted updates instead of full refresh
            self.refresh_selection_display(platform)
    
    def refresh_selection_display(self, platform: str):
        """Refresh only the queue-related display elements (faster than full refresh)"""
        # Update all visible game items
        for item_id in self.game_tree.get_children():
            game_key = self.game_tree.set(item_id, 'game_key')
            if game_key:
                self.update_game_tree_item(game_key, platform)
        
        # Also update any detached items that might be reattached later
        if hasattr(self, '_detached_items'):
            for item_id in self._detached_items:
                try:
                    game_key = self.game_tree.set(item_id, 'game_key')
                    if game_key:
                        # Update queue display for detached item
                        current_values = list(self.game_tree.item(item_id, 'values'))
                        current_values[0] = ""  # Clear queued column
                        
                        # Update visual tags
                        current_tags = list(self.game_tree.item(item_id, 'tags'))
                        # Remove queue-related tags
                        current_tags = [tag for tag in current_tags if tag not in ['queued', 'queued_installed']]
                        if 'installed' in current_tags:
                            current_tags = ['game', 'installed']
                        else:
                            current_tags = ['game']
                        
                        self.game_tree.item(item_id, values=tuple(current_values), tags=tuple(current_tags))
                        
                        # Update child variants too
                        for child_id in self.game_tree.get_children(item_id):
                            child_values = list(self.game_tree.item(child_id, 'values'))
                            child_values[0] = ""  # Clear queued column
                            child_tags = list(self.game_tree.item(child_id, 'tags'))
                            child_tags = [tag for tag in child_tags if tag not in ['queued', 'queued_installed']]
                            if 'installed' in child_tags:
                                child_tags = ['variant', 'installed']
                            else:
                                child_tags = ['variant']
                            self.game_tree.item(child_id, values=tuple(child_values), tags=tuple(child_tags))
                        
                except tk.TclError:
                    # Item no longer exists, ignore
                    pass
    
    def cleanup_detached_items(self):
        """Clean up detached items to prevent memory leaks"""
        if hasattr(self, '_detached_items'):
            self._detached_items.clear()
    
    
    def show_about(self):
        """Show about dialog"""
        about_text = """ROM Downloader - Game Library
        
A tool for downloading and managing ROM collections
with intelligent organization and filtering.

Features:
- Dynamic tag-based filtering
- Game-centric organization with expandable variants
- Installation status verification
- Configurable tool pipelines
- Download queue management
- Multi-platform support

Usage:
- Click on the checkbox in the "Queued" column to add/remove ROMs from download queue
- Right-click on games for queue management options
- Double-click expands/collapses game variants
- Use filters to find specific games quickly
"""
        messagebox.showinfo("About", about_text)
    
    def show_settings(self):
        """Show the settings window"""
        try:
            settings_window = SettingsWindow(self.root, self.config_manager)
            
            # Store original callback for when window closes
            original_destroy = settings_window.window.destroy if settings_window.window else None
            
            def on_settings_close():
                # Refresh dropdowns in case they changed
                self.refresh_platform_list()
                self.refresh_network_drive_list()
                if original_destroy:
                    original_destroy()
            
            settings_window.show()
            
            # Replace destroy method to include our refresh
            if settings_window.window:
                settings_window.window.destroy = on_settings_close
                
        except Exception as e:
            logger.error(f"Error opening settings window: {e}")
            messagebox.showerror("Error", f"Failed to open settings: {e}")
    
    def _set_download_ui_state(self, downloading: bool):
        """Enable/disable UI elements based on download state"""
        # Disable these elements when downloading
        state = "disabled" if downloading else "normal"
        self.platform_combo.config(state="disabled" if downloading else "readonly")
        self.scan_button.config(state=state)
        self.check_installed_button.config(state=state)
        self.install_queue_button.config(state=state)
        self.clear_queue_button.config(state=state)
        
        # Cancel button is opposite - enabled when downloading
        cancel_state = "normal" if downloading else "disabled"
        self.cancel_install_button.config(state=cancel_state)
        
        # Disable queue modifications when downloading
        if hasattr(self, 'tree'):
            # Disable tree interactions during download
            for item in self.tree.get_children():
                self._set_tree_item_state(item, downloading)
    
    def _set_tree_item_state(self, item, downloading: bool):
        """Recursively set tree item state"""
        # This will prevent queue modifications during download
        # The actual checkbox clicking will be handled in the click handler
        for child in self.tree.get_children(item):
            self._set_tree_item_state(child, downloading)
    
    
    def update_status(self, message: str):
        """Update download status label"""
        self.status_label.config(text=message)
        # Download status updated
    
    def update_copy_status(self, message: str):
        """Update copy status label"""
        self.copy_status_label.config(text=message)
        # Copy status updated
    
    def run(self):
        """Start the GUI main loop"""
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle application closing"""
        logger.info("Application closing, saving state...")
        self._gui_active = False  # Stop background threads from updating GUI
        self.state_manager.save_if_dirty()
        self.root.destroy()
    
    def __del__(self):
        """Cleanup when GUI is destroyed"""
        try:
            self.cleanup_detached_items()
            if hasattr(self, 'state_manager'):
                self.state_manager.save_if_dirty()
        except:
            pass