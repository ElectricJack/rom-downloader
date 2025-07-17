"""
Game library GUI with dynamic filtering and game-centric interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from typing import Dict, Set, List, Optional, Callable
from pathlib import Path

from models.game_library import Game, ROM, GameLibrary
from state.distributed_state_manager import DistributedStateManager
from config.enhanced_config_manager import EnhancedConfigManager
from downloader.enhanced_download_manager import EnhancedDownloadManager, DownloadProgress, DownloadResult
from processors.game_library_processor import GameLibraryProcessor
from scraper.web_scraper import WebScraper, RomInfo
from rom_manager.rom_filter import RomFilter

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
        
        # GUI state
        self.current_platform = tk.StringVar()
        self.current_platform.trace('w', self.on_platform_change)
        
        self.active_tag_filters = set()
        self.search_query = tk.StringVar()
        self.search_query.trace('w', self.on_search_change)
        
        # UI components
        self.tag_buttons = {}
        self.tag_variables = {}
        self.game_tree = None
        self.progress_bar = None
        self.status_label = None
        
        # Data
        self.current_games = []
        self.downloading = False
        self.existing_roms = set()  # Cache of installed ROMs
        self._gui_active = True  # Flag to track if GUI is still active
        self._async_update_cancelled = False  # Flag to cancel async updates
        
        self.setup_ui()
        self.refresh_platform_list()
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
        self.setup_tag_filters(main_frame)
        
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
        ttk.Button(top_frame, text="Scan ROMs", command=self.scan_roms).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(top_frame, text="Check Installed", command=self.check_installed_roms).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(top_frame, text="Download Queue", command=self.download_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(top_frame, text="Clear Queue", command=self.clear_selections).pack(side=tk.LEFT)
    
    def setup_tag_filters(self, parent):
        """Set up dynamic tag filter buttons"""
        self.tag_frame = ttk.LabelFrame(parent, text="Filter by Tags")
        self.tag_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Top row with clear button
        button_row = ttk.Frame(self.tag_frame)
        button_row.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        self.clear_filters_button = ttk.Button(
            button_row, 
            text="Clear All Filters", 
            command=self.clear_tag_filters
        )
        self.clear_filters_button.pack(side=tk.LEFT)
        
        # Container for tag groups
        self.tag_groups_container = ttk.Frame(self.tag_frame)
        self.tag_groups_container.pack(fill=tk.X, padx=5, pady=5)
        
        # Individual group containers
        self.language_group_frame = None
        self.country_group_frame = None
        self.other_group_frame = None
        
        # Custom tag input setup
        self.setup_custom_tag_input()
    
    def setup_custom_tag_input(self):
        """Set up the custom tag input field with auto-completion"""
        # Custom tag input frame
        self.custom_tag_frame = ttk.LabelFrame(self.tag_groups_container, text="Additional Tags (type to filter)")
        
        # Input frame
        input_frame = ttk.Frame(self.custom_tag_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Tag input field
        self.custom_tag_var = tk.StringVar()
        self.custom_tag_var.trace('w', self.on_custom_tag_change)
        
        self.custom_tag_entry = ttk.Entry(
            input_frame, 
            textvariable=self.custom_tag_var,
            font=('TkDefaultFont', 9)
        )
        self.custom_tag_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Add button
        self.add_tag_button = ttk.Button(
            input_frame,
            text="Add",
            command=self.add_custom_tag,
            width=8
        )
        self.add_tag_button.pack(side=tk.RIGHT)
        
        # Active custom tags display
        self.active_tags_frame = ttk.Frame(self.custom_tag_frame)
        self.active_tags_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Auto-completion listbox (initially hidden)
        self.completion_frame = ttk.Frame(self.custom_tag_frame)
        self.completion_listbox = tk.Listbox(
            self.completion_frame,
            height=6,
            font=('TkDefaultFont', 8)
        )
        self.completion_listbox.pack(fill=tk.X, padx=5)
        
        # Bind events for auto-completion
        self.custom_tag_entry.bind('<KeyRelease>', self.on_tag_entry_keyrelease)
        self.custom_tag_entry.bind('<FocusOut>', self.hide_completion)
        self.custom_tag_entry.bind('<Return>', self.on_tag_entry_return)
        self.custom_tag_entry.bind('<Tab>', self.on_tag_entry_tab)
        self.completion_listbox.bind('<Double-Button-1>', self.on_completion_select)
        self.completion_listbox.bind('<Return>', self.on_completion_select)
        
        # Track state
        self.custom_tag_filters = set()
        self.available_other_tags = set()
        self.active_tag_buttons = {}
        self.completion_visible = False
    
    def on_custom_tag_change(self, *args):
        """Handle custom tag input change"""
        self.update_auto_completion()
    
    def on_tag_entry_keyrelease(self, event):
        """Handle key release in tag entry"""
        if event.keysym in ('Up', 'Down'):
            self.navigate_completion(event.keysym)
        elif event.keysym == 'Escape':
            self.hide_completion()
        else:
            self.update_auto_completion()
    
    def on_tag_entry_return(self, event):
        """Handle Enter key in tag entry"""
        if self.completion_visible and self.completion_listbox.curselection():
            self.select_completion()
        else:
            self.add_custom_tag()
        return 'break'
    
    def on_tag_entry_tab(self, event):
        """Handle Tab key in tag entry"""
        if self.completion_visible and self.completion_listbox.curselection():
            self.select_completion()
            return 'break'
    
    def on_completion_select(self, event=None):
        """Handle selection from completion listbox"""
        self.select_completion()
    
    def navigate_completion(self, direction):
        """Navigate through completion options"""
        if not self.completion_visible:
            return
        
        current = self.completion_listbox.curselection()
        size = self.completion_listbox.size()
        
        if size == 0:
            return
        
        if not current:
            # No selection, select first or last
            new_index = 0 if direction == 'Down' else size - 1
        else:
            current_index = current[0]
            if direction == 'Down':
                new_index = (current_index + 1) % size
            else:
                new_index = (current_index - 1) % size
        
        self.completion_listbox.selection_clear(0, tk.END)
        self.completion_listbox.selection_set(new_index)
        self.completion_listbox.see(new_index)
    
    def select_completion(self):
        """Select the highlighted completion"""
        if not self.completion_visible:
            return
        
        selection = self.completion_listbox.curselection()
        if selection:
            tag = self.completion_listbox.get(selection[0])
            self.custom_tag_var.set(tag)
            self.hide_completion()
            # Focus back to entry and position cursor at end
            self.custom_tag_entry.focus_set()
            self.custom_tag_entry.icursor(tk.END)
    
    def update_auto_completion(self):
        """Update auto-completion suggestions"""
        current_text = self.custom_tag_var.get().strip().lower()
        
        if len(current_text) < 1:
            self.hide_completion()
            return
        
        # Find matching tags
        matches = []
        for tag in self.available_other_tags:
            if (tag.lower().startswith(current_text) and 
                tag.lower() not in {t.lower() for t in self.custom_tag_filters}):
                matches.append(tag)
        
        # Sort matches - exact matches first, then alphabetically
        matches.sort(key=lambda x: (not x.lower().startswith(current_text), x.lower()))
        
        if matches:
            self.show_completion(matches[:10])  # Show top 10 matches
        else:
            self.hide_completion()
    
    def show_completion(self, matches):
        """Show auto-completion listbox with matches"""
        self.completion_listbox.delete(0, tk.END)
        for match in matches:
            self.completion_listbox.insert(tk.END, match)
        
        if not self.completion_visible:
            self.completion_frame.pack(fill=tk.X, pady=(0, 5))
            self.completion_visible = True
        
        # Auto-select first item
        if matches:
            self.completion_listbox.selection_set(0)
    
    def hide_completion(self, event=None):
        """Hide auto-completion listbox"""
        if self.completion_visible:
            self.completion_frame.pack_forget()
            self.completion_visible = False
    
    def add_custom_tag(self):
        """Add custom tag to filters"""
        tag_text = self.custom_tag_var.get().strip()
        if not tag_text:
            return
        
        # Find the exact tag name (case-insensitive match)
        exact_tag = None
        for available_tag in self.available_other_tags:
            if available_tag.lower() == tag_text.lower():
                exact_tag = available_tag
                break
        
        # Use exact tag if found, otherwise use typed text
        tag_to_add = exact_tag if exact_tag else tag_text
        
        if tag_to_add and tag_to_add not in self.custom_tag_filters:
            self.custom_tag_filters.add(tag_to_add)
            self.active_tag_filters.add(tag_to_add)
            self.create_active_tag_button(tag_to_add)
            self.custom_tag_var.set("")
            self.hide_completion()
            self.refresh_game_list()
    
    def create_active_tag_button(self, tag):
        """Create a button for an active custom tag"""
        button_frame = ttk.Frame(self.active_tags_frame)
        button_frame.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Tag label
        label = ttk.Label(
            button_frame, 
            text=tag,
            background='lightblue',
            padding=(4, 2)
        )
        label.pack(side=tk.LEFT)
        
        # Remove button
        remove_btn = ttk.Button(
            button_frame,
            text="×",
            width=3,
            command=lambda t=tag: self.remove_custom_tag(t)
        )
        remove_btn.pack(side=tk.LEFT)
        
        self.active_tag_buttons[tag] = button_frame
    
    def remove_custom_tag(self, tag):
        """Remove custom tag from filters"""
        if tag in self.custom_tag_filters:
            self.custom_tag_filters.discard(tag)
            self.active_tag_filters.discard(tag)
            
            # Remove button
            if tag in self.active_tag_buttons:
                self.active_tag_buttons[tag].destroy()
                del self.active_tag_buttons[tag]
            
            self.refresh_game_list()
    
    def clear_custom_tags(self):
        """Clear all custom tag filters"""
        self.custom_tag_filters.clear()
        self.custom_tag_var.set("")
        self.hide_completion()
        
        # Remove all active tag buttons
        for button_frame in self.active_tag_buttons.values():
            button_frame.destroy()
        self.active_tag_buttons.clear()
    
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
        self.context_menu.add_command(label="Add to Queue", command=self.add_to_queue)
        self.context_menu.add_command(label="Remove from Queue", command=self.remove_from_queue)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Add All Variants to Queue", command=self.add_all_variants_to_queue)
        self.context_menu.add_command(label="Remove All Variants from Queue", command=self.remove_all_variants_from_queue)
    
    def add_to_queue(self):
        """Add selected items to download queue via context menu"""
        selections = self.game_tree.selection()
        if not selections:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Track which games were modified for batch updates
        modified_games = set()
        
        # Process all selected items
        for item in selections:
            try:
                item_type = self.game_tree.set(item, 'item_type')
                game_key = self.game_tree.set(item, 'game_key')
                variant_key = self.game_tree.set(item, 'variant_key')
            except:
                continue
            
            if item_type == 'game':
                if self.add_game_to_queue_batch(game_key, platform):
                    modified_games.add(game_key)
            elif item_type == 'variant':
                if self.add_variant_to_queue_batch(game_key, platform, variant_key):
                    modified_games.add(game_key)
        
        # Save once after all operations
        if self.state_manager.selections_dirty:
            self.state_manager.save_selections()
        
        # Update all modified games
        for game_key in modified_games:
            self.update_game_tree_item(game_key, platform)
    
    def add_game_to_queue_batch(self, game_key: str, platform: str) -> bool:
        """Add a game to download queue (batch operation, returns True if modified)"""
        # Find game
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if not game:
            return False
        
        # Check if already queued
        current_selection = self.state_manager.get_selection(game_key, platform)
        if current_selection:
            return False  # Already queued
        
        # Add to queue - pick best variant
        variants = game.get_variants_for_platform(platform)
        if variants:
            best_variant = game.get_best_variant(platform, self.config_manager.get_preferred_regions())
            if best_variant:
                variant_key = best_variant.create_variant_key()
                self.state_manager.select_rom_variant(game_key, platform, variant_key)
                return True
        
        return False
    
    def add_variant_to_queue_batch(self, game_key: str, platform: str, variant_key: str) -> bool:
        """Add a specific variant to download queue (batch operation, returns True if modified)"""
        # Check if already queued with this variant
        current_selection = self.state_manager.get_selection(game_key, platform)
        if current_selection and current_selection.selected_rom_variant == variant_key:
            return False  # Already queued with this variant
        
        self.state_manager.select_rom_variant(game_key, platform, variant_key)
        return True
    
    def remove_from_queue(self):
        """Remove selected items from download queue via context menu"""
        selections = self.game_tree.selection()
        if not selections:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Process all selected items
        for item in selections:
            try:
                item_type = self.game_tree.set(item, 'item_type')
                game_key = self.game_tree.set(item, 'game_key')
                variant_key = self.game_tree.set(item, 'variant_key')
            except:
                continue
            
            if item_type in ['game', 'variant']:
                # Remove from queue regardless of whether it's game or variant level
                selection_key = f"{platform}:{game_key}"
                if selection_key in self.state_manager.selections:
                    del self.state_manager.selections[selection_key]
                    self.state_manager.selections_dirty = True
                    # Don't save after each item - save once at the end
        
        # Save selections once after processing all items
        if self.state_manager.selections_dirty:
            self.state_manager.save_selections()
            
            # Update all affected items
            processed_games = set()
            for item in selections:
                try:
                    game_key = self.game_tree.set(item, 'game_key')
                    if game_key and game_key not in processed_games:
                        self.update_game_tree_item(game_key, platform)
                        processed_games.add(game_key)
                except:
                    continue
    
    def add_all_variants_to_queue(self):
        """Add all variants of selected games to queue"""
        selections = self.game_tree.selection()
        if not selections:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Process all selected items
        processed_games = set()
        for item in selections:
            try:
                game_key = self.game_tree.set(item, 'game_key')
                if game_key and game_key not in processed_games:
                    self.add_game_to_queue(game_key, platform)
                    processed_games.add(game_key)
            except:
                continue
    
    def remove_all_variants_from_queue(self):
        """Remove all variants of selected games from queue"""
        # This is the same as regular remove for our current implementation
        self.remove_from_queue()
    
    def add_game_to_queue(self, game_key: str, platform: str):
        """Add a game to download queue (selects best variant)"""
        if self.add_game_to_queue_batch(game_key, platform):
            self.state_manager.save_selections()
            self.update_game_tree_item(game_key, platform)
    
    def add_variant_to_queue(self, game_key: str, platform: str, variant_key: str):
        """Add a specific variant to download queue"""
        if self.add_variant_to_queue_batch(game_key, platform, variant_key):
            self.state_manager.save_selections()
            self.update_game_tree_item(game_key, platform)
    
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
    
    def setup_bottom_section(self, parent):
        """Set up the bottom section with progress and status"""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(bottom_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.status_label = ttk.Label(bottom_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)
    
    def setup_menu_bar(self):
        """Set up the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Queue...", command=self.export_selections)
        file_menu.add_command(label="Import Queue...", command=self.import_selections)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Diagnose ROM Detection", command=self.diagnose_installation_detection)
        tools_menu.add_separator()
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
            self.update_tag_buttons(platform)
            tag_time = time.time() - tag_start
            logger.info(f"update_tag_buttons() took {tag_time:.2f}s")
            
            refresh_start = time.time()
            self.refresh_game_list()
            refresh_time = time.time() - refresh_start
            logger.info(f"refresh_game_list() took {refresh_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"=== restore_last_state() completed in {total_time:.2f}s ===")
    
    def on_platform_change(self, *args):
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
            self.update_tag_buttons(platform)
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
    
    def update_tag_buttons(self, platform: str):
        """Update tag filter buttons for the selected platform"""
        # Clear existing buttons and groups
        for button in self.tag_buttons.values():
            button.destroy()
        self.tag_buttons.clear()
        self.tag_variables.clear()
        
        # Clear custom tag filters
        self.clear_custom_tags()
        
        if self.language_group_frame:
            self.language_group_frame.destroy()
        if self.country_group_frame:
            self.country_group_frame.destroy()
        if self.other_group_frame:
            self.other_group_frame.destroy()
        
        # Get tags for platform
        platform_tags = self.state_manager.get_platform_tags(platform)
        if not platform_tags:
            return
        
        # Categorize tags
        categorized_tags = self.library_processor.categorize_tags(platform_tags)
        
        # Store available other tags for auto-completion
        self.available_other_tags = categorized_tags.get('other', set())
        
        # Create tag group frames
        current_row = 0
        
        # Language tags
        if categorized_tags.get('language'):
            self.language_group_frame = ttk.LabelFrame(self.tag_groups_container, text="Languages")
            self.language_group_frame.grid(row=current_row, column=0, sticky=(tk.W, tk.E), padx=(0, 5), pady=2)
            self.create_tag_buttons(self.language_group_frame, categorized_tags['language'])
            current_row += 1
        
        # Country/Region tags
        if categorized_tags.get('country'):
            self.country_group_frame = ttk.LabelFrame(self.tag_groups_container, text="Regions")
            self.country_group_frame.grid(row=current_row, column=0, sticky=(tk.W, tk.E), padx=(0, 5), pady=2)
            self.create_tag_buttons(self.country_group_frame, categorized_tags['country'])
            current_row += 1
        
        # Custom tag input (replaces Other group)
        if self.available_other_tags:
            self.custom_tag_frame.grid(row=current_row, column=0, sticky=(tk.W, tk.E), padx=(0, 5), pady=2)
            # Update the label to show count
            tag_count = len(self.available_other_tags)
            self.custom_tag_frame.configure(text=f"Additional Tags ({tag_count} available - type to filter)")
    
    def create_tag_buttons(self, parent_frame: ttk.LabelFrame, tags: Set[str]):
        """Create toggle buttons for a set of tags"""
        # Sort tags for consistent display
        sorted_tags = sorted(tags)
        
        # Create buttons in rows
        row = 0
        col = 0
        max_cols = 6
        
        for tag in sorted_tags:
            var = tk.BooleanVar()
            self.tag_variables[tag] = var
            
            button = ttk.Checkbutton(
                parent_frame,
                text=tag,
                variable=var,
                command=lambda t=tag: self.on_tag_filter_change(t)
            )
            button.grid(row=row, column=col, sticky=tk.W, padx=2, pady=1)
            
            self.tag_buttons[tag] = button
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def on_tag_filter_change(self, tag: str):
        """Handle tag filter button toggle"""
        if self.tag_variables[tag].get():
            self.active_tag_filters.add(tag)
        else:
            self.active_tag_filters.discard(tag)
        
        # Use fast filtering instead of full refresh
        self.apply_filters_to_tree()
    
    def clear_tag_filters(self):
        """Clear all active tag filters"""
        self.active_tag_filters.clear()
        
        # Clear all tag button states
        for var in self.tag_variables.values():
            var.set(False)
        
        # Clear custom tags
        self.clear_custom_tags()
        
        # Use fast filtering instead of full refresh
        self.apply_filters_to_tree()
    
    def on_search_change(self, *args):
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
        
        # Now detach items that don't match filters
        for item_id in list(self.game_tree.get_children()):  # Create list copy since we're modifying
            game_key = self.game_tree.set(item_id, 'game_key')
            
            if game_key not in filtered_game_keys:
                # Hide this game by detaching it
                self.game_tree.detach(item_id)
                self._detached_items.append(item_id)
        
        self.update_status(f"Showing {len(filtered_games)} games")
    
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
        all_active_filters = self.active_tag_filters.union(self.custom_tag_filters) if hasattr(self, 'custom_tag_filters') else self.active_tag_filters
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
        """Check if game matches current tag filters"""
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            all_filters = self.active_tag_filters.copy()
            if hasattr(self, 'custom_tag_filters'):
                all_filters.update(self.custom_tag_filters)
            filter_tags = all_filters
        
        if not filter_tags:
            return True
            
        game_tags = game.get_all_tags()
        # Game must have ALL selected tags (AND logic)
        return all(any(tag.lower() == game_tag.lower() for game_tag in game_tags) for tag in filter_tags)
    
    def rom_matches_tags(self, rom, filter_tags: Set[str] = None) -> bool:
        """Check if ROM variant matches current tag filters"""
        if filter_tags is None:
            # Use all active filters (both checkbox and custom)
            all_filters = self.active_tag_filters.copy()
            if hasattr(self, 'custom_tag_filters'):
                all_filters.update(self.custom_tag_filters)
            filter_tags = all_filters
        
        if not filter_tags:
            return True
            
        rom_tags = rom.tags
        # ROM must have ALL selected tags (AND logic)
        return all(any(tag.lower() == rom_tag.lower() for rom_tag in rom_tags) for tag in filter_tags)
    
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
            # Normalize the ROM filename for comparison (same logic as scan_existing_roms)
            # Remove last extension first, then normalize
            stem = rom.filename
            if '.' in stem:
                stem = '.'.join(stem.split('.')[:-1])  # Remove last extension
            
            normalized_name = self.rom_filter._normalize_name(stem)
            result = normalized_name in self.existing_roms
            
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
    
    def diagnose_installation_detection(self):
        """Diagnose why installed ROM detection might not be working"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        logger.info("=" * 50)
        logger.info("DIAGNOSTIC: ROM Installation Detection")
        logger.info("=" * 50)
        
        # Check target directory configuration
        target_dir = self.config_manager.get_target_directory(platform)
        logger.info(f"Platform: {platform}")
        logger.info(f"Configured target directory: {target_dir}")
        
        if not target_dir:
            logger.error("No target directory configured!")
            messagebox.showerror("Diagnostic Result", f"No target directory configured for platform: {platform}")
            return
        
        # Check if directory exists
        try:
            dir_exists = target_dir.exists()
            logger.info(f"Target directory exists: {dir_exists}")
            
            if not dir_exists:
                logger.error(f"Target directory does not exist: {target_dir}")
                messagebox.showerror("Diagnostic Result", 
                    f"Target directory does not exist:\n{target_dir}\n\n"
                    f"Please either:\n"
                    f"1. Create this directory and put some ROMs in it, or\n"
                    f"2. Update your configuration to point to the correct ROM directory")
                return
        except Exception as e:
            logger.error(f"Error checking directory: {e}")
            messagebox.showerror("Diagnostic Result", f"Error accessing target directory: {e}")
            return
        
        # Check directory permissions and contents
        try:
            logger.info("Checking directory accessibility...")
            entries = list(target_dir.iterdir())
            logger.info(f"Directory is accessible, contains {len(entries)} entries")
            
            # Count ROM files
            rom_extensions = {'.rvz', '.zip', '.7z', '.iso', '.gcm', '.bin', '.cue', '.chd'}
            rom_files = [e for e in entries if e.suffix.lower() in rom_extensions and not e.name.startswith('.')]
            logger.info(f"Found {len(rom_files)} potential ROM files")
            
            if rom_files:
                logger.info("Sample ROM files found:")
                for rom_file in rom_files[:5]:  # Show first 5
                    logger.info(f"  - {rom_file.name}")
                    
                # Test normalization on first ROM
                if rom_files:
                    test_rom = rom_files[0]
                    stem = test_rom.name
                    if '.' in stem:
                        stem = '.'.join(stem.split('.')[:-1])
                    normalized = self.rom_filter._normalize_name(stem)
                    logger.info(f"Test normalization: '{test_rom.name}' -> '{normalized}'")
            
            # Check cache status
            logger.info(f"Current ROM cache size: {len(self.existing_roms)}")
            if self.existing_roms:
                sample_cache = list(self.existing_roms)[:5]
                logger.info(f"Sample cache entries: {sample_cache}")
            
            messagebox.showinfo("Diagnostic Result",
                f"Directory check completed!\n\n"
                f"Target directory: {target_dir}\n"
                f"Directory exists: {dir_exists}\n"
                f"Total entries: {len(entries)}\n"
                f"ROM files found: {len(rom_files)}\n"
                f"Cache entries: {len(self.existing_roms)}\n\n"
                f"Check the console output for detailed logging.")
                
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            messagebox.showerror("Diagnostic Result", f"Permission denied accessing directory: {e}")
        except Exception as e:
            logger.error(f"Error scanning directory: {e}", exc_info=True)
            messagebox.showerror("Diagnostic Result", f"Error scanning directory: {e}")
        
        logger.info("=" * 50)
    
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
            
            # Update cache for all variants
            for rom in game.get_variants_for_platform(platform):
                total_roms += 1
                
                # Normalize ROM filename for comparison (same logic as existing)
                stem = rom.filename
                if '.' in stem:
                    stem = '.'.join(stem.split('.')[:-1])  # Remove last extension
                
                normalized_name = self.rom_filter._normalize_name(stem)
                is_installed = normalized_name in self.existing_roms
                
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
                
            # Use cached installation status
            has_installed = game.has_installed_variants(platform)
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
            
            # Find the ROM variant and use cached status
            variants = game.get_variants_for_platform(platform)
            for rom in variants:
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
            self.toggle_game_queue(game_key, platform)
        elif item_type == 'variant':
            # Variants cannot be queued individually - ignore click
            return
    
    def toggle_game_queue(self, game_key: str, platform: str):
        """Toggle queue status for a game (auto-select best variant)"""
        # Find game
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if not game:
            return
        
        # Toggle queue status
        current_selection = self.state_manager.get_selection(game_key, platform)
        
        if current_selection:
            # Remove from queue
            selection_key = f"{platform}:{game_key}"
            if selection_key in self.state_manager.selections:
                del self.state_manager.selections[selection_key]
                self.state_manager.selections_dirty = True
                self.state_manager.save_selections()
        else:
            # Add to queue - pick best variant
            variants = game.get_variants_for_platform(platform)
            if variants:
                best_variant = game.get_best_variant(platform, self.config_manager.get_preferred_regions())
                if best_variant:
                    variant_key = best_variant.create_variant_key()
                    self.state_manager.select_rom_variant(game_key, platform, variant_key)
        
        # Update only the affected tree items instead of full refresh
        self.update_game_tree_item(game_key, platform)
    
    def toggle_variant_queue(self, game_key: str, platform: str, variant_key: str):
        """Toggle queue status for a specific variant"""
        current_selection = self.state_manager.get_selection(game_key, platform)
        
        if current_selection and current_selection.selected_rom_variant == variant_key:
            # Remove this variant from queue
            selection_key = f"{platform}:{game_key}"
            if selection_key in self.state_manager.selections:
                del self.state_manager.selections[selection_key]
                self.state_manager.selections_dirty = True
                self.state_manager.save_selections()
        else:
            # Add this variant to queue
            self.state_manager.select_rom_variant(game_key, platform, variant_key)
        
        # Update only the affected tree items instead of full refresh
        self.update_game_tree_item(game_key, platform)
    
    def on_tree_right_click(self, event):
        """Handle right-click context menu"""
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
        self.update_tag_buttons(self.current_platform.get())
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
        
        # Filter out already installed ROMs
        roms_to_download = []
        already_installed = []
        
        for rom in selected_roms:
            if self.is_rom_installed(rom, platform):
                already_installed.append(rom.filename)
            else:
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
        self.update_status("Starting download...")
        
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
                
            def progress_callback(rom: ROM, progress: DownloadProgress):
                self._safe_gui_update(lambda: self._update_download_progress(rom, progress))
            
            def completion_callback(rom: ROM, result: DownloadResult):
                self._safe_gui_update(lambda: self._update_download_completion(rom, result))
            
            # Start download
            results = self.download_manager.download_roms(
                roms, platform, progress_callback, completion_callback
            )
            
            # Show results
            successful = sum(1 for r in results if r.success)
            self._safe_gui_update(lambda: self._download_complete(successful, len(results)))
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            self._safe_gui_update(lambda: self.update_status(f"Download error: {e}"))
        finally:
            self.downloading = False
    
    def _update_download_progress(self, rom: ROM, progress: DownloadProgress):
        """Update download progress in UI"""
        self.progress_bar['value'] = progress.percentage
        self.update_status(f"Downloading {rom.filename} - {progress.percentage:.1f}% ({progress.speed_formatted})")
    
    def _update_download_completion(self, rom: ROM, result: DownloadResult):
        """Update download completion in UI"""
        if result.success:
            self.update_status(f"Downloaded: {rom.filename}")
            # Refresh display to update installed status
            self.refresh_game_list()
        else:
            self.update_status(f"Failed: {rom.filename} - {result.error_message}")
    
    def _download_complete(self, successful: int, total: int):
        """Handle download completion"""
        self.progress_bar['value'] = 0
        self.update_status(f"Download complete: {successful}/{total} successful")
        messagebox.showinfo("Download Complete", f"Downloaded {successful} out of {total} ROMs")
        
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
    
    def update_status(self, message: str):
        """Update status label"""
        self.status_label.config(text=message)
        logger.info(f"Status: {message}")
    
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