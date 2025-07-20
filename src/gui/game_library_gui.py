"""
Game library GUI with dynamic filtering and game-centric interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import subprocess
import sys
from typing import Dict, Set, List, Optional, Callable
from pathlib import Path

from models.game_library import Game, ROM, GameLibrary
from state.distributed_state_manager import DistributedStateManager
from config.enhanced_config_manager import EnhancedConfigManager
from downloader.enhanced_download_manager import EnhancedDownloadManager, DownloadProgress, DownloadResult
from processors.game_library_processor import GameLibraryProcessor
from scraper.web_scraper import WebScraper, RomInfo
from rom_manager.rom_filter import RomFilter
from filters.advanced_rom_filter import AdvancedRomFilter, FilterCriteria
from gui.managers.tag_filter_manager import TagFilterManager
from gui.managers.queue_manager import QueueManager

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
        
        # GUI state
        self.current_platform = tk.StringVar()
        self.current_platform.trace('w', self.on_platform_change)
        
        self.search_query = tk.StringVar()
        self.search_query.trace('w', self.on_search_change)
        
        # UI components
        self.game_tree = None
        self.progress_bar = None
        self.copy_progress_bar = None
        self.status_label = None
        self.copy_status_label = None
        
        # Data
        self.current_games = []
        self.downloading = False
        self.existing_roms = set()  # Cache of installed ROMs
        self._gui_active = True  # Flag to track if GUI is still active
        self._async_update_cancelled = False  # Flag to cancel async updates
        self.installation_count = 0  # Track completed installations
        self.total_queued_count = 0  # Track total ROMs queued for download
        
        self.setup_ui()
        self.refresh_platform_list()
        
        # Set up tag filter manager callback
        self.tag_filter_manager.set_filters_changed_callback(self.apply_filters_to_tree)
        
        self.restore_last_state()
        
        logger.info("Game library GUI initialized")
    
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
        
        # Search
        ttk.Label(top_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        
        search_entry = ttk.Entry(top_frame, textvariable=self.search_query, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Buttons
        self.scan_button = ttk.Button(top_frame, text="Scan ROMs", command=self.scan_roms)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.check_installed_button = ttk.Button(top_frame, text="Check Installed", command=self.check_installed_roms)
        self.check_installed_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.install_queue_button = ttk.Button(top_frame, text="Install Games in Queue", command=self.download_selected)
        self.install_queue_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_queue_button = ttk.Button(top_frame, text="Clear Queue", command=self.clear_selections)
        self.clear_queue_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Cancel Install button (initially disabled)
        self.cancel_install_button = ttk.Button(top_frame, text="Cancel Install", command=self.cancel_download, state="disabled")
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
        
        # Bind events - remove double-click selection, add right-click menu
        self.game_tree.bind('<Button-1>', self.on_tree_click)
        self.game_tree.bind('<Button-3>', self.on_tree_right_click)  # Right-click context menu
        self.game_tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
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
            is_installed = self.is_rom_installed(rom, platform)
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
                    is_installed = self.is_rom_installed(rom, platform)
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
        file_menu.add_command(label="Open Platform Config", command=self.open_platform_config)
        file_menu.add_command(label="Open ROMs Folder", command=self.open_roms_folder)
        file_menu.add_command(label="Open Temp Download Folder", command=self.open_temp_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Queue...", command=self.export_selections)
        file_menu.add_command(label="Import Queue...", command=self.import_selections)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        # Removed Diagnose ROM Detection tool
        tools_menu.add_command(label="Clear Cache", command=self.clear_cache)
        tools_menu.add_command(label="Cleanup Temp Files", command=self.cleanup_temp_files)
        
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
            self.existing_roms.clear()
            # Force a full rebuild since platform changed
            self.current_games = []  # This will trigger a rebuild
            
            refresh_start = time.time()
            self.refresh_game_list()
            refresh_time = time.time() - refresh_start
            logger.info(f"refresh_game_list() took {refresh_time:.2f}s")
            
            total_time = time.time() - start_time
            logger.info(f"=== on_platform_change() completed in {total_time:.2f}s ===")
    
    
    
    
    
    def on_search_change(self, *_args):
        """Handle search text change"""
        # Use fast filtering instead of full refresh
        self.apply_filters_to_tree()
    
    def refresh_game_list(self):
        """Refresh the game list display"""
        import time
        start_time = time.time()
        
        platform = self.current_platform.get()
        if not platform:
            return

        logger.info(f"=== refresh_game_list() started for {platform} ===")

        # Get games for platform
        games_start = time.time()
        games = self.state_manager.get_games_for_platform(platform)
        games_time = time.time() - games_start
        logger.info(f"get_games_for_platform() took {games_time:.2f}s, got {len(games)} games")
        
        # Check if we need to rebuild the tree (data has changed)
        if self.current_games != games:
            rebuild_start = time.time()
            self.rebuild_game_tree(games, platform)
            rebuild_time = time.time() - rebuild_start
            logger.info(f"rebuild_game_tree() took {rebuild_time:.2f}s")
        else:
            # Just apply filters to existing tree (much faster)
            filter_start = time.time()
            self.apply_filters_to_tree()
            filter_time = time.time() - filter_start
            logger.info(f"apply_filters_to_tree() took {filter_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== refresh_game_list() completed in {total_time:.2f}s ===")

    
    def rebuild_game_tree(self, games: List[Game], platform: str):
        """Rebuild the entire game tree (only when data changes)"""
        import time
        start_time = time.time()
        
        logger.info(f"=== rebuild_game_tree() started with {len(games)} games ===")
        
        # Cancel any running async installation updates since tree structure will change
        self._async_update_cancelled = True
        
        # Clear existing items
        clear_start = time.time()
        self.game_tree.delete(*self.game_tree.get_children())
        clear_time = time.time() - clear_start
        logger.info(f"Tree clearing took {clear_time:.2f}s")
        
        # Reset cancellation flag for new async updates
        self._async_update_cancelled = False
        
        # Clear ROM cache since it's platform-specific
        self.existing_roms = set()
        
        # Auto-populate existing ROMs cache and target directory exists
        target_dir = self.config_manager.get_target_directory(platform)
        logger.info(f"Target directory for platform {platform}: {target_dir}")
        
        cache_start = time.time()
        if not self.existing_roms:
            logger.info("ROM cache is empty, will populate asynchronously...")
            if target_dir:
                logger.info(f"Target directory configured: {target_dir}")
                # Start async ROM scanning - don't block the UI
                import threading
                thread = threading.Thread(target=self._async_populate_rom_cache, args=(platform, target_dir))
                thread.daemon = True
                thread.start()
            else:
                logger.warning(f"No target directory configured for platform: {platform}")
                self.existing_roms = set()
        else:
            logger.info(f"ROM cache already populated with {len(self.existing_roms)} entries")
        cache_time = time.time() - cache_start
        logger.info(f"ROM cache setup took {cache_time:.2f}s")

        # Populate tree with all games (no filtering during build)
        populate_start = time.time()
        for i, game in enumerate(games):
            if i % 200 == 0 and i > 0:
                logger.info(f"Added {i}/{len(games)} games to tree...")
            self.add_game_to_tree(game, platform)
        populate_time = time.time() - populate_start
        logger.info(f"Tree population took {populate_time:.2f}s for {len(games)} games")

        self.current_games = games
        
        # Apply filters to the newly built tree
        filter_start = time.time()
        self.apply_filters_to_tree()
        filter_time = time.time() - filter_start
        logger.info(f"Filter application took {filter_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== rebuild_game_tree() completed in {total_time:.2f}s ===")
    
    def apply_filters_to_tree(self):
        """Apply current filters by showing/hiding tree items (fast)"""
        # Get current filter criteria
        filtered_games = self.apply_filters(self.current_games)
        filtered_game_keys = {game.key for game in filtered_games}
        
        # Store detached items to avoid memory leaks
        if not hasattr(self, '_detached_items'):
            self._detached_items = []
        
        # First, reattach any previously detached items
        for item_id in self._detached_items:
            try:
                self.game_tree.reattach(item_id, '', 'end')
            except tk.TclError:
                # Item no longer exists, ignore
                pass
        self._detached_items.clear()
        
        # Now detach items that don't match filters and rebuild variants for visible games
        platform = self.current_platform.get()
        
        for item_id in list(self.game_tree.get_children()):  # Create list copy since we're modifying
            game_key = self.game_tree.set(item_id, 'game_key')
            
            if game_key not in filtered_game_keys:
                # Hide this game by detaching it
                self.game_tree.detach(item_id)
                self._detached_items.append(item_id)
            else:
                # Game is visible - rebuild its variant children with current filters
                self._rebuild_game_variants(item_id, game_key, platform)
        
        self.update_status(f"Showing {len(filtered_games)} games")
    
    def _rebuild_game_variants(self, game_item_id: str, game_key: str, platform: str):
        """Rebuild variant children for a game with current tag filters"""
        try:
            # Find the game object
            game = None
            for g in self.current_games:
                if g.key == game_key:
                    game = g
                    break
            
            if not game:
                return
            
            # Remove all existing variant children
            for child_id in list(self.game_tree.get_children(game_item_id)):
                self.game_tree.delete(child_id)
            
            # Get all variants for this platform
            variants = game.get_variants_for_platform(platform)
            
            # Filter variants based on current tag filters
            filtered_variants = [rom for rom in variants if self.rom_matches_tags(rom)]
            
            # Update the variant count in the game item
            variant_count_text = f"{len(filtered_variants)}/{len(variants)} variants" if len(filtered_variants) != len(variants) else f"{len(variants)} variants"
            current_values = list(self.game_tree.item(game_item_id, 'values'))
            current_values[2] = variant_count_text  # Update variant count column
            self.game_tree.item(game_item_id, values=tuple(current_values))
            
            # Get current game selection
            selection = self.state_manager.get_selection(game_key, platform)
            
            # Add filtered variants as children
            for rom in filtered_variants:
                # Check if this specific variant is queued
                variant_queued = ""
                if selection and selection.selected_rom_variant == rom.create_variant_key():
                    variant_queued = "✓"
                
                # Get installation status from cache if available
                cached_installed = rom.is_installed()
                variant_installed = "✓" if cached_installed is True else ""
                
                # Format tags for this variant
                rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
                
                # Determine visual styling for variant
                variant_visual_tags = ['variant']
                if variant_queued:
                    variant_visual_tags.append('queued')
                if cached_installed is True:
                    variant_visual_tags.append('installed')
                if variant_queued and cached_installed is True:
                    variant_visual_tags.append('queued_installed')
                
                self.game_tree.insert(
                    game_item_id,
                    'end',
                    text=rom.filename,
                    values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                    tags=tuple(variant_visual_tags)
                )
        
        except Exception as e:
            logger.error(f"Error rebuilding variants for game {game_key}: {e}")
    
    def apply_visual_filters(self, visible_game_keys: Set[str]):
        """Apply visual filtering using tags and styling (backup method)"""
        # This method is kept as a backup but not used in the main flow
        for item_id in self.game_tree.get_children():
            game_key = self.game_tree.set(item_id, 'game_key')
            
            # Get current tags and remove any existing filter tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            current_tags = [tag for tag in current_tags if tag != 'filtered_out']
            
            if game_key not in visible_game_keys:
                # This game should be filtered out
                current_tags.append('filtered_out')
                self.game_tree.item(item_id, tags=tuple(current_tags))
                
                # Also filter out child variants
                for child_id in self.game_tree.get_children(item_id):
                    child_tags = list(self.game_tree.item(child_id, 'tags'))
                    child_tags = [tag for tag in child_tags if tag != 'filtered_out']
                    child_tags.append('filtered_out')
                    self.game_tree.item(child_id, tags=tuple(child_tags))
            else:
                # This game should be visible
                self.game_tree.item(item_id, tags=tuple(current_tags))
                
                # Also show child variants
                for child_id in self.game_tree.get_children(item_id):
                    child_tags = list(self.game_tree.item(child_id, 'tags'))
                    child_tags = [tag for tag in child_tags if tag != 'filtered_out']
                    self.game_tree.item(child_id, tags=tuple(child_tags))
        
        # Configure the filtered_out tag to make items barely visible
        self.game_tree.tag_configure('filtered_out', foreground='lightgray', background='')
    
    def apply_filters(self, games: List[Game]) -> List[Game]:
        """Apply current filters to game list"""
        filtered_games = games
        
        # Apply tag filters (both checkbox and custom tags)
        all_active_filters = self.tag_filter_manager.get_active_filters()
        if all_active_filters:
            filtered_games = [
                game for game in filtered_games
                if self.game_matches_tags(game, all_active_filters)
            ]
        
        # Apply search filter
        search_query = self.search_query.get().lower()
        if search_query:
            filtered_games = [
                game for game in filtered_games
                if search_query in game.display_name.lower()
            ]
        
        return filtered_games
    
    def game_matches_tags(self, game: Game, filter_tags: Set[str] = None) -> bool:
        """Check if game matches current tag filters using advanced filtering logic"""
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            filter_tags = self.tag_filter_manager.get_active_filters()
        
        if not filter_tags:
            return True
            
        # Create filter criteria from selected tags
        criteria = self.advanced_filter.create_filter_criteria(filter_tags)
        
        # Check if game matches criteria using all its tags
        game_tags = game.get_all_tags()
        return self.advanced_filter.rom_matches_criteria(game_tags, criteria)
    
    def rom_matches_tags(self, rom, filter_tags: Set[str] = None) -> bool:
        """Check if ROM variant matches current tag filters using advanced filtering logic"""
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            filter_tags = self.tag_filter_manager.get_active_filters()
        
        if not filter_tags:
            return True
            
        # Create filter criteria from selected tags
        criteria = self.advanced_filter.create_filter_criteria(filter_tags)
        
        # Check if ROM matches criteria
        return self.advanced_filter.rom_matches_criteria(rom.tags, criteria)
    
    def add_game_to_tree(self, game: Game, platform: str):
        """Add a game and its variants to the treeview"""
        # Get variants for this platform
        variants = game.get_variants_for_platform(platform)
        if not variants:
            return
        
        # Check if any variant is queued
        selection = self.state_manager.get_selection(game.key, platform)
        queued_text = "✓" if selection else ""
        
        # Skip installation checking during initial tree population to avoid blocking
        # Installation status will be updated asynchronously after ROM cache is populated
        installed_text = ""
        
        # Filter variants based on active tag filters first
        filtered_variants = [rom for rom in variants if self.rom_matches_tags(rom)]
        
        # Get tags for display with grouping
        tags = game.get_all_tags()
        if tags:
            # Use the processor to categorize and format tags
            categorized_tags = self.library_processor.categorize_tags(tags)
            tags_text = self.library_processor.format_tag_groups_compact(categorized_tags)
        else:
            tags_text = ""
        
        # Determine visual styling (installation status will be updated later)
        visual_tags = ['game']
        if selection:
            visual_tags.append('queued')
        
        # Show filtered vs total variant count
        variant_count_text = f"{len(filtered_variants)}/{len(variants)} variants" if len(filtered_variants) != len(variants) else f"{len(variants)} variants"
        
        # Insert game item
        game_item = self.game_tree.insert(
            '',
            'end',
            text=game.display_name,
            values=(queued_text, installed_text, variant_count_text, tags_text, 'game', game.key, ''),
            tags=tuple(visual_tags)
        )
        
        # Add filtered ROM variants as children
        for rom in filtered_variants:
            # Check if this specific variant is queued
            variant_queued = ""
            if selection and selection.selected_rom_variant == rom.create_variant_key():
                variant_queued = "✓"
            
            # Skip installation checking during initial tree population to avoid blocking
            variant_installed = ""
            
            # Format tags for this variant
            rom_tags = ", ".join(sorted(rom.tags)) if rom.tags else ""
            
            # Determine visual styling for variant (installation status will be updated later)
            variant_visual_tags = ['variant']
            if variant_queued:
                variant_visual_tags.append('queued')
            
            self.game_tree.insert(
                game_item,
                'end',
                text=rom.filename,
                values=(variant_queued, variant_installed, rom.size, rom_tags, 'variant', game.key, rom.create_variant_key()),
                tags=tuple(variant_visual_tags)
            )
    
    def is_rom_installed(self, rom: ROM, platform: str) -> bool:
        """Check if a ROM is installed on the target drive"""
        # First check if we have cached installation status
        cached_status = rom.is_installed()
        if cached_status is not None:
            return cached_status
        
        target_dir = self.config_manager.get_target_directory(platform)
        if not target_dir:
            return False
        
        # Check if target directory exists
        try:
            dir_exists = target_dir.exists()
            if not dir_exists:
                return False
        except Exception as e:
            logger.error(f"Error checking target directory existence: {e}")
            return False
        
        # Use existing ROM cache for fast lookup if available
        if self.existing_roms:
            result = self._precise_rom_match(rom.filename, self.existing_roms)
            
            # Cache the result for future use
            rom.set_installed(result)
            return result
        
        # Fallback to direct checking if cache is empty
        # Create a RomInfo object from ROM for compatibility with RomFilter
        rom_info = RomInfo(
            name=rom.filename,
            url=rom.url,
            size=rom.size
        )
        
        result = self.rom_filter.is_rom_installed(rom_info, target_dir)
        
        # Cache the result for future use
        rom.set_installed(result)
        return result
    
    def _precise_rom_match(self, rom_filename: str, existing_roms: set) -> bool:
        """
        Perform precise ROM matching using multiple strategies to avoid false positives.
        
        Args:
            rom_filename: The ROM filename to check (e.g., "007 - Everything or Nothing (Japan).zip")
            existing_roms: Set of existing ROM stems (case-insensitive, no extensions)
        
        Returns:
            True if the ROM is found, False otherwise
        """
        # Get the stem (filename without extension)
        stem = rom_filename
        if '.' in stem:
            stem = '.'.join(stem.split('.')[:-1])
        
        # Strategy 1: Exact match (case-insensitive)
        precise_name = stem.lower().strip()
        if precise_name in existing_roms:
            return True
        
        # Strategy 2: Use the same normalization as the existing_roms set
        normalized_name = self.rom_filter._normalize_name(stem)
        if normalized_name in existing_roms:
            return True
        
        # Strategy 3: Check if any existing ROM matches this one with different extension
        # This handles cases like .zip vs .rvz for the same game
        for existing_rom in existing_roms:
            if self._are_same_rom_different_format(normalized_name, existing_rom):
                return True
        
        return False
    
    def _basic_normalize_preserving_regions(self, name: str) -> str:
        """
        Normalize ROM name while preserving regional and language information.
        This is less aggressive than the original _normalize_name().
        """
        import re
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Normalize spaces and punctuation, but preserve regional info
        normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces to single
        normalized = re.sub(r'[_\-]+', ' ', normalized)  # Underscores/dashes to spaces
        normalized = normalized.strip()
        
        return normalized
    
    def _are_same_rom_different_format(self, rom1: str, rom2: str) -> bool:
        """
        Check if two ROM names represent the same game but in different formats.
        This is a very conservative check to avoid false positives.
        """
        # Only consider them the same if they're very similar
        # This is intentionally strict to avoid false matches
        return rom1 == rom2
    
    def check_installed_roms(self):
        """Scan target directory for installed ROMs and refresh display"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return

        target_dir = self.config_manager.get_target_directory(platform)
        if not target_dir:
            messagebox.showwarning("Warning", f"No target directory configured for platform: {platform}")
            return

        self.update_status("Scanning for installed ROMs...")
        self.progress_bar.configure(mode='indeterminate')
        self.progress_bar.start()

        # Run scan in a separate thread
        import threading
        thread = threading.Thread(target=self._check_installed_thread, args=(platform, target_dir))
        thread.daemon = True
        thread.start()
    
    # Removed diagnose_installation_detection method
    
    def _check_installed_thread(self, platform: str, target_dir: Path):
        """Check installed ROMs in a separate thread"""
        try:
            # Check if GUI is still active
            if not self._gui_active:
                return
                
            # Scan existing ROMs
            self.existing_roms = self.rom_filter.scan_existing_roms(target_dir)
            
            # Update UI (if GUI still active)
            self._safe_gui_update(lambda: self._check_installed_complete(len(self.existing_roms)))
            
        except Exception as e:
            logger.error(f"Error checking installed ROMs: {e}")
            self._safe_gui_update(lambda: self.update_status(f"Error: {e}"))
        finally:
            self._safe_gui_update(lambda: self.progress_bar.stop())
            self._safe_gui_update(lambda: self.progress_bar.configure(mode='determinate'))

    def _async_populate_rom_cache(self, platform: str, target_dir: Path):
        """Populate ROM cache asynchronously without blocking the UI"""
        try:
            logger.info(f"Starting async ROM cache population for {platform}")
            
            # Check if GUI is still active
            if not self._gui_active:
                logger.info("GUI no longer active, cancelling ROM cache population")
                return
            
            # Check if directory exists
            dir_exists = target_dir.exists()
            logger.info(f"Target directory exists: {dir_exists}")
            
            if dir_exists:
                self._safe_gui_update(lambda: self.update_status("Checking for installed ROMs..."))
                logger.info("Starting ROM cache population...")
                
                # Scan existing ROMs
                existing_roms = self.rom_filter.scan_existing_roms(target_dir)
                
                # Update cache and UI on main thread (if GUI still active)
                self._safe_gui_update(lambda: self._update_rom_cache(existing_roms, platform))
                
            else:
                logger.warning(f"Target directory does not exist: {target_dir}")
                self._safe_gui_update(lambda: self.update_status("Ready"))
                
        except Exception as e:
            logger.error(f"Failed to scan existing ROMs: {e}", exc_info=True)
            self._safe_gui_update(lambda: self.update_status("Ready"))

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

    def _update_rom_cache(self, existing_roms: set, platform: str):
        """Update ROM cache and refresh display (called on main thread)"""
        self.existing_roms = existing_roms
        logger.info(f"Updated ROM cache: {len(self.existing_roms)} ROMs found")
        
        # Log first few entries for debugging
        if self.existing_roms:
            sample_roms = list(self.existing_roms)[:5]
            logger.info(f"Sample cached ROM names: {sample_roms}")
        
        # Bulk update installation cache for all games/ROMs
        self._bulk_update_installation_cache(platform)
        
        # Schedule fast tree visual update using cached data
        import threading
        thread = threading.Thread(target=self._async_update_tree_from_cache)
        thread.daemon = True
        thread.start()
        self.update_status("Ready")
    
    def _bulk_update_installation_cache(self, platform: str):
        """Bulk update installation cache for all games using directory scan results"""
        if not self.current_games or not self.existing_roms:
            return
            
        total_roms = 0
        cached_roms = 0
        
        for game in self.current_games:
            # Clear existing cache for this platform
            game.clear_installation_cache_for_platform(platform)
            
            # Update cache for all variants using precise matching
            for rom in game.get_variants_for_platform(platform):
                total_roms += 1
                
                # Use the new precise matching logic
                is_installed = self._precise_rom_match(rom.filename, self.existing_roms)
                
                # Cache the result
                rom.set_installed(is_installed)
                if is_installed:
                    cached_roms += 1
        
        logger.info(f"Cached installation status for {total_roms} ROMs, {cached_roms} installed")
    
    def _async_update_tree_from_cache(self):
        """Fast tree update using cached installation data"""
        try:
            if not self._gui_active or not self.current_games or self._async_update_cancelled:
                return
            
            platform = self.current_platform.get()
            if not platform:
                return
            
            # Get all tree items to update
            tree_items = list(self.game_tree.get_children())
            total_items = len(tree_items)
            
            # Process in larger chunks since we're using cached data
            chunk_size = 100  # Larger chunks since no I/O
            processed = 0
            
            for i in range(0, total_items, chunk_size):
                if not self._gui_active or self._async_update_cancelled:
                    logger.info("Async tree cache update cancelled")
                    break
                
                chunk = tree_items[i:i + chunk_size]
                
                # Process this chunk using cached data
                updates = []
                for item_id in chunk:
                    try:
                        # Check if item still exists
                        if not self.game_tree.exists(item_id):
                            continue
                            
                        game_key = self.game_tree.set(item_id, 'game_key')
                        if game_key:
                            # Find the game object
                            game = None
                            for g in self.current_games:
                                if g.key == game_key:
                                    game = g
                                    break
                            
                            if game:
                                # Use cached installation data
                                game_update = self._prepare_cached_game_update(item_id, game, platform)
                                if game_update:
                                    updates.append(game_update)
                                
                                # Prepare updates for child variants using cache
                                for child_item in self.game_tree.get_children(item_id):
                                    variant_update = self._prepare_cached_variant_update(child_item, game, platform)
                                    if variant_update:
                                        updates.append(variant_update)
                    except Exception as e:
                        logger.error(f"Error preparing cached update for tree item {item_id}: {e}")
                
                # Schedule GUI updates on main thread
                if updates:
                    self._safe_gui_update(lambda: self._apply_tree_updates(updates))
                
                processed += len(chunk)
                
                # Smaller delay since we're using cached data
                import time
                time.sleep(0.005)  # 5ms vs 10ms
            
            logger.info(f"Completed cached tree installation status update for {processed} items")
            
        except Exception as e:
            logger.error(f"Error in cached tree installation status update: {e}")
    
    def _prepare_cached_game_update(self, item_id: str, game, platform: str):
        """Prepare game update using cached installation data"""
        try:
            if not self.game_tree.exists(item_id):
                return None
                
            # Only check installation status for filtered variants (same logic as tree building)
            variants = game.get_variants_for_platform(platform)
            filtered_variants = [rom for rom in variants if self.rom_matches_tags(rom)]
            
            # Check if any of the visible/filtered variants are installed
            has_installed = any(rom.is_installed() is True for rom in filtered_variants)
            installed_text = "✓" if has_installed else ""
            
            # Determine visual tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            new_tags = [tag for tag in current_tags if tag not in ['installed', 'queued_installed']]
            
            if has_installed:
                new_tags.append('installed')
                if 'queued' in current_tags:
                    new_tags.append('queued_installed')
            
            return {
                'item_id': item_id,
                'type': 'game',
                'installed_text': installed_text,
                'tags': tuple(new_tags)
            }
        except Exception as e:
            logger.error(f"Error preparing cached game update for {item_id}: {e}")
            return None
    
    def _prepare_cached_variant_update(self, item_id: str, game, platform: str):
        """Prepare variant update using cached installation data"""
        try:
            if not self.game_tree.exists(item_id):
                return None
                
            variant_key = self.game_tree.set(item_id, 'variant_key')
            if not variant_key:
                return None
            
            # Only look through filtered variants (same as tree building logic)
            variants = game.get_variants_for_platform(platform)
            filtered_variants = [rom for rom in variants if self.rom_matches_tags(rom)]
            
            # Find the ROM variant and use cached status
            for rom in filtered_variants:
                if rom.create_variant_key() == variant_key:
                    is_installed = rom.is_installed()
                    if is_installed is None:
                        return None  # Cache not populated
                    
                    installed_text = "✓" if is_installed else ""
                    
                    # Determine visual tags
                    current_tags = list(self.game_tree.item(item_id, 'tags'))
                    new_tags = [tag for tag in current_tags if tag not in ['installed', 'queued_installed']]
                    
                    if is_installed:
                        new_tags.append('installed')
                        if 'queued' in current_tags:
                            new_tags.append('queued_installed')
                    
                    return {
                        'item_id': item_id,
                        'type': 'variant',
                        'installed_text': installed_text,
                        'tags': tuple(new_tags)
                    }
            
            return None
        except Exception as e:
            logger.error(f"Error preparing cached variant update for {item_id}: {e}")
            return None
    
    def _async_update_tree_installation_status(self):
        """Update tree installation status asynchronously in chunks"""
        try:
            if not self._gui_active or not self.current_games or self._async_update_cancelled:
                return
            
            platform = self.current_platform.get()
            if not platform:
                return
            
            # Get all tree items to update
            tree_items = list(self.game_tree.get_children())
            total_items = len(tree_items)
            
            # Process in chunks to avoid blocking
            chunk_size = 50  # Process 50 games at a time
            processed = 0
            
            for i in range(0, total_items, chunk_size):
                if not self._gui_active or self._async_update_cancelled:
                    logger.info("Async tree update cancelled")
                    break
                
                chunk = tree_items[i:i + chunk_size]
                
                # Process this chunk
                updates = []
                for item_id in chunk:
                    try:
                        # Check if item still exists (may have been deleted during platform change)
                        if not self.game_tree.exists(item_id):
                            continue
                            
                        game_key = self.game_tree.set(item_id, 'game_key')
                        if game_key:
                            # Find the game object
                            game = None
                            for g in self.current_games:
                                if g.key == game_key:
                                    game = g
                                    break
                            
                            if game:
                                # Prepare update data for this game and its variants
                                game_update = self._prepare_game_installation_update(item_id, game, platform)
                                if game_update:
                                    updates.append(game_update)
                                
                                # Prepare updates for child variants
                                for child_item in self.game_tree.get_children(item_id):
                                    variant_update = self._prepare_variant_installation_update(child_item, game, platform)
                                    if variant_update:
                                        updates.append(variant_update)
                    except Exception as e:
                        logger.error(f"Error preparing update for tree item {item_id}: {e}")
                
                # Schedule GUI updates on main thread
                if updates:
                    self._safe_gui_update(lambda: self._apply_tree_updates(updates))
                
                processed += len(chunk)
                
                # Small delay between chunks to keep GUI responsive
                import time
                time.sleep(0.01)
            
            logger.info(f"Completed async tree installation status update for {processed} items")
            
        except Exception as e:
            logger.error(f"Error in async tree installation status update: {e}")
    
    def _prepare_game_installation_update(self, item_id: str, game, platform: str):
        """Prepare installation status update data for a game item"""
        try:
            # Check if item still exists
            if not self.game_tree.exists(item_id):
                return None
                
            variants = game.get_variants_for_platform(platform)
            installed_variants = []
            for rom in variants:
                if self.is_rom_installed(rom, platform):
                    installed_variants.append(rom)
            
            installed_text = "✓" if installed_variants else ""
            
            # Determine visual tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            new_tags = [tag for tag in current_tags if tag not in ['installed', 'queued_installed']]
            
            if installed_variants:
                new_tags.append('installed')
                if 'queued' in current_tags:
                    new_tags.append('queued_installed')
            
            return {
                'item_id': item_id,
                'type': 'game',
                'installed_text': installed_text,
                'tags': tuple(new_tags)
            }
        except Exception as e:
            logger.error(f"Error preparing game update for {item_id}: {e}")
            return None
    
    def _prepare_variant_installation_update(self, item_id: str, game, platform: str):
        """Prepare installation status update data for a variant item"""
        try:
            # Check if item still exists
            if not self.game_tree.exists(item_id):
                return None
                
            variant_key = self.game_tree.set(item_id, 'variant_key')
            if not variant_key:
                return None
            
            # Find the ROM variant
            variants = game.get_variants_for_platform(platform)
            rom_variant = None
            for rom in variants:
                if rom.create_variant_key() == variant_key:
                    rom_variant = rom
                    break
            
            if not rom_variant:
                return None
            
            is_installed = self.is_rom_installed(rom_variant, platform)
            installed_text = "✓" if is_installed else ""
            
            # Determine visual tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            new_tags = [tag for tag in current_tags if tag not in ['installed', 'queued_installed']]
            
            if is_installed:
                new_tags.append('installed')
                if 'queued' in current_tags:
                    new_tags.append('queued_installed')
            
            return {
                'item_id': item_id,
                'type': 'variant',
                'installed_text': installed_text,
                'tags': tuple(new_tags)
            }
        except Exception as e:
            logger.error(f"Error preparing variant update for {item_id}: {e}")
            return None
    
    def _apply_tree_updates(self, updates):
        """Apply a batch of tree updates on the main thread"""
        try:
            for update in updates:
                if not self._gui_active:
                    break
                
                item_id = update['item_id']
                if not self.game_tree.exists(item_id):
                    continue
                
                # Update the installed column
                current_values = list(self.game_tree.item(item_id, 'values'))
                current_values[1] = update['installed_text']  # Installed column
                
                # Apply the update
                self.game_tree.item(item_id, values=tuple(current_values), tags=update['tags'])
                
        except Exception as e:
            logger.error(f"Error applying tree updates: {e}")
    
    def _update_existing_tree_items_installation_status(self):
        """Update installation status of existing tree items without full refresh"""
        if not self.current_games:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Update all game items in the tree
        for item_id in self.game_tree.get_children():
            try:
                game_key = self.game_tree.set(item_id, 'game_key')
                if game_key:
                    # Find the game object
                    game = None
                    for g in self.current_games:
                        if g.key == game_key:
                            game = g
                            break
                    
                    if game:
                        # Update the game item
                        self._update_game_item_installation_status(item_id, game, platform)
                        
                        # Update child variant items
                        for child_item in self.game_tree.get_children(item_id):
                            self._update_variant_item_installation_status(child_item, game, platform)
            except Exception as e:
                logger.error(f"Error updating tree item {item_id}: {e}")
    
    def _update_game_item_installation_status(self, item_id: str, game, platform: str):
        """Update installation status for a game item"""
        try:
            # Check if any variants are installed
            variants = game.get_variants_for_platform(platform)
            installed_variants = []
            for rom in variants:
                if self.is_rom_installed(rom, platform):
                    installed_variants.append(rom)
            
            # Update installed column
            current_values = list(self.game_tree.item(item_id, 'values'))
            current_values[1] = "✓" if installed_variants else ""  # Installed column
            
            # Update visual tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            if installed_variants:
                if 'installed' not in current_tags:
                    current_tags.append('installed')
            else:
                if 'installed' in current_tags:
                    current_tags.remove('installed')
            
            # Check for queued_installed combination
            if "queued" in current_tags and installed_variants:
                if 'queued_installed' not in current_tags:
                    current_tags.append('queued_installed')
            else:
                if 'queued_installed' in current_tags:
                    current_tags.remove('queued_installed')
            
            self.game_tree.item(item_id, values=tuple(current_values), tags=tuple(current_tags))
        except Exception as e:
            logger.error(f"Error updating game item installation status: {e}")
    
    def _update_variant_item_installation_status(self, item_id: str, game, platform: str):
        """Update installation status for a variant item"""
        try:
            variant_key = self.game_tree.set(item_id, 'variant_key')
            if not variant_key:
                return
            
            # Find the ROM variant
            variants = game.get_variants_for_platform(platform)
            rom_variant = None
            for rom in variants:
                if rom.create_variant_key() == variant_key:
                    rom_variant = rom
                    break
            
            if not rom_variant:
                return
            
            # Check if this variant is installed
            is_installed = self.is_rom_installed(rom_variant, platform)
            
            # Update installed column
            current_values = list(self.game_tree.item(item_id, 'values'))
            current_values[1] = "✓" if is_installed else ""  # Installed column
            
            # Update visual tags
            current_tags = list(self.game_tree.item(item_id, 'tags'))
            if is_installed:
                if 'installed' not in current_tags:
                    current_tags.append('installed')
            else:
                if 'installed' in current_tags:
                    current_tags.remove('installed')
            
            # Check for queued_installed combination
            if "queued" in current_tags and is_installed:
                if 'queued_installed' not in current_tags:
                    current_tags.append('queued_installed')
            else:
                if 'queued_installed' in current_tags:
                    current_tags.remove('queued_installed')
            
            self.game_tree.item(item_id, values=tuple(current_values), tags=tuple(current_tags))
        except Exception as e:
            logger.error(f"Error updating variant item installation status: {e}")
    
    def _check_installed_complete(self, count: int):
        """Handle installed ROM check completion"""
        self.update_status(f"Found {count} installed ROMs")
        self.refresh_game_list()
    
    def on_tree_click(self, event):
        """Handle tree click - only toggle queue on checkbox column click"""
        region = self.game_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.game_tree.identify_column(event.x)
            if column == '#1':  # Queued column
                self.toggle_queue_status(event)
    
    def toggle_queue_status(self, event):
        """Toggle queue status for game or variant"""
        # Prevent queue modifications during download
        if self.downloading:
            return
            
        item = self.game_tree.identify_row(event.y)
        if not item:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        try:
            item_type = self.game_tree.set(item, 'item_type')
            game_key = self.game_tree.set(item, 'game_key')
            variant_key = self.game_tree.set(item, 'variant_key')
        except:
            return
        
        if item_type == 'game':
            self.queue_manager.toggle_game_queue_status(game_key, platform)
        elif item_type == 'variant':
            # Variants cannot be queued individually - ignore click
            return
    
    
    
    def on_tree_right_click(self, event):
        """Handle right-click context menu"""
        # Prevent context menu during download
        if self.downloading:
            return
            
        item = self.game_tree.identify_row(event.y)
        if item:
            self.context_menu.post(event.x_root, event.y_root)
    
    def on_tree_select(self, event):
        """Handle tree selection (for expanding/collapsing)"""
        pass  # We don't need special handling for selection changes
    
    def scan_roms(self):
        """Scan for ROMs on the selected platform"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        if self.downloading:
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
    
    def download_selected(self):
        """Download queued ROMs"""
        platform = self.current_platform.get()
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
        import threading
        thread = threading.Thread(target=self._download_thread, args=(roms_to_download, platform))
        thread.daemon = True
        thread.start()
    
    def _download_thread(self, roms: List[ROM], platform: str):
        """Download ROMs in a separate thread"""
        try:
            # Check if GUI is still active
            if not self._gui_active:
                return
            
            # Initialize tracking variables
            self.installation_count = 0
            self.total_queued_count = len(roms)
                
            def progress_callback(rom: ROM, progress: DownloadProgress):
                self._safe_gui_update(lambda: self._update_download_progress(rom, progress))
            
            def completion_callback(rom: ROM, result: DownloadResult):
                self._safe_gui_update(lambda: self._update_download_completion(rom, result))
            
            def copy_progress_callback(rom: ROM, progress: DownloadProgress):
                self._safe_gui_update(lambda: self._update_copy_progress(rom, progress))
            
            def copy_completion_callback(rom: ROM, result: DownloadResult):
                self._safe_gui_update(lambda: self._update_copy_completion(rom, result))
            
            # Start download with separate copy callbacks
            results = self.download_manager.download_roms(
                roms, platform, progress_callback, completion_callback,
                copy_progress_callback, copy_completion_callback
            )
            
            # Wait for all copies to complete, then show final results
            self._safe_gui_update(lambda: self.update_status("Downloads complete, waiting for all copies to finish..."))
            
            # Wait for all pending copies to complete
            all_copies_complete = self.download_manager.wait_for_all_copies_complete(timeout=300)  # 5 minute timeout
            
            if all_copies_complete:
                self._safe_gui_update(lambda: self._installation_complete())
            else:
                # Timeout occurred, show warning
                self._safe_gui_update(lambda: self._installation_timeout_warning())
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            self._safe_gui_update(lambda: self.update_status(f"Download error: {e}"))
        finally:
            self.downloading = False
            self._safe_gui_update(lambda: self._set_download_ui_state(downloading=False))
    
    def _update_download_progress(self, rom: ROM, progress: DownloadProgress):
        """Update download progress in UI"""
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
        # Use the dedicated copy progress bar
        self.copy_progress_bar['value'] = progress.percentage
        self.update_copy_status(f"Copying {rom.clean_name} - {progress.percentage:.1f}% ({progress.speed_formatted})")
    
    def _update_copy_completion(self, rom: ROM, result: DownloadResult):
        """Update copy completion in UI"""
        if result.success:
            self.copy_progress_bar['value'] = 100  # Show completion briefly
            self.update_copy_status(f"Installed: {rom.clean_name}")
            self.installation_count += 1
            
            # Remove ROM from selection queue after successful installation
            platform = self.current_platform.get()
            if platform:
                # Find the game key for this ROM
                for game in self.current_games:
                    for variant_key, variant_rom in game.variants.items():
                        if variant_rom.filename == rom.filename:
                            # Remove from queue
                            self.state_manager.remove_selection(game.game_key, platform)
                            logger.info(f"Removed {game.game_key} from queue after successful installation")
                            break
            
            # Refresh display to update installed status and queue status after copy completes
            self.refresh_game_list()
        else:
            self.copy_progress_bar['value'] = 0  # Reset on failure
            self.update_copy_status(f"Installation failed: {rom.clean_name} - {result.error_message}")
    
    def _installation_complete(self):
        """Handle installation completion"""
        self.progress_bar['value'] = 0
        self.copy_progress_bar['value'] = 0
        self.update_status(f"Installation complete: {self.installation_count}/{self.total_queued_count} successful")
        self.update_copy_status("")  # Clear copy status
        messagebox.showinfo("Installation Complete", f"Successfully installed {self.installation_count} out of {self.total_queued_count} ROMs")
        
        # Refresh installed ROM cache
        platform = self.current_platform.get()
        if platform:
            self.check_installed_roms()
    
    def _installation_timeout_warning(self):
        """Handle installation timeout warning"""
        self.progress_bar['value'] = 0
        self.copy_progress_bar['value'] = 0
        self.update_status(f"Installation timeout: {self.installation_count}/{self.total_queued_count} completed")
        self.update_copy_status("")  # Clear copy status
        messagebox.showwarning("Installation Timeout", 
                              f"Installation process timed out. {self.installation_count} out of {self.total_queued_count} ROMs completed.\n"
                              "Some copies may still be in progress.")
        
        # Refresh installed ROM cache
        platform = self.current_platform.get()
        if platform:
            self.check_installed_roms()
    
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
    
    def export_selections(self):
        """Export download queue to file"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                self.state_manager.export_selections(platform, Path(filename))
                messagebox.showinfo("Success", "Download queue exported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export queue: {e}")
    
    def import_selections(self):
        """Import download queue from file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                success = self.state_manager.import_selections(Path(filename))
                if success:
                    messagebox.showinfo("Success", "Download queue imported successfully")
                    self.refresh_game_list()
                else:
                    messagebox.showerror("Error", "Failed to import queue")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import queue: {e}")
    
    def clear_cache(self):
        """Clear application cache"""
        if messagebox.askyesno("Confirm", "Clear all cached data?"):
            # Clear state manager cache for current platform
            if self.state_manager.platform_library:
                self.state_manager.platform_library.games.clear()
                self.state_manager.platform_library.tag_registry.clear()
                self.state_manager.platform_dirty = True
            
            # Clear installed ROM cache
            self.existing_roms.clear()
            
            self.refresh_game_list()
            self.update_status("Cache cleared")
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        self.download_manager.cleanup_temp_files()
        self.update_status("Temporary files cleaned up")
    
    def open_platform_config(self):
        """Open the platform configuration file."""
        config_file = self.config_manager.config_file
        try:
            if sys.platform.startswith('win'):
                subprocess.run(['start', str(config_file)], shell=True, check=True)
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', str(config_file)], check=True)
            else:
                subprocess.run(['xdg-open', str(config_file)], check=True)
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open config file: {config_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config file: {e}")
    
    def open_roms_folder(self):
        """Open the ROMs folder for the currently selected platform."""
        current_platform = self.current_platform.get()
        if not current_platform:
            messagebox.showwarning("No Platform", "Please select a platform first.")
            return
        
        # Get the target path for the current platform
        target_path = self.config_manager.get_target_directory(current_platform)
        if not target_path:
            messagebox.showerror("Configuration Error", 
                               f"Target path not configured for platform: {current_platform}")
            return
        
        # Ensure the directory exists
        target_path.mkdir(parents=True, exist_ok=True)
        
        try:
            if sys.platform.startswith('win'):
                subprocess.run(['explorer', str(target_path)], check=True)
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', str(target_path)], check=True)
            else:
                subprocess.run(['xdg-open', str(target_path)], check=True)
            
            logger.info(f"Opened ROMs folder: {target_path}")
            
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open ROMs folder: {target_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open ROMs folder: {e}")
    
    def open_temp_folder(self):
        """Open the temporary download folder."""
        temp_folder = self.download_manager.temp_dir
        
        # Ensure the temp directory exists
        temp_folder.mkdir(parents=True, exist_ok=True)
        
        try:
            if sys.platform.startswith('win'):
                subprocess.run(['explorer', str(temp_folder)], check=True)
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', str(temp_folder)], check=True)
            else:
                subprocess.run(['xdg-open', str(temp_folder)], check=True)
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Could not open temp folder: {temp_folder}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open temp folder: {e}")
    
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
    
    def cancel_download(self):
        """Cancel ongoing download"""
        if hasattr(self, 'download_manager') and self.download_manager:
            self.download_manager.cancel_downloads()
            self.update_status("Cancelling download...")
    
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