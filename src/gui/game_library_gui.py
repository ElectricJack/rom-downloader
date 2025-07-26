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
from src.utils.rom_utils import get_rom_utils

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
        self.rom_utils = get_rom_utils()
        
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
    
    def _get_platform_key_from_display_name(self, display_name: str) -> Optional[str]:
        """Convert display name back to platform key"""
        platforms = self.config_manager.get_platform_display_names()
        for key, name in platforms.items():
            if name == display_name:
                return key
        return None
    
    def get_current_platform_key(self) -> Optional[str]:
        """Get the current platform key (for use by manager classes)"""
        display_name = self.current_platform.get()
        if display_name:
            return self._get_platform_key_from_display_name(display_name)
        return None
    
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
        
        # Configure tree tag styles - order matters for precedence
        self.game_tree.tag_configure('installed', background='lightgreen')
        self.game_tree.tag_configure('queued', background='lightblue')
        self.game_tree.tag_configure('queued_installed', background='darkgreen', foreground='white')
        # Configure installed_only LAST so it has highest precedence
        self.game_tree.tag_configure('installed_only', background='orange', foreground='black')
        
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
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Reveal in File Explorer", command=self.reveal_in_file_explorer)
        self.context_menu.add_command(label="Uninstall", command=self.uninstall_rom)
        
        # Store menu indices for dynamic enabling/disabling
        self.add_to_queue_index = 0
        self.remove_from_queue_index = 1
        self.add_all_variants_index = 3
        self.remove_all_variants_index = 4
        self.reveal_in_explorer_index = self.context_menu.index("end") - 1  # -1 because we added uninstall after
        self.uninstall_index = self.context_menu.index("end")
    
    def update_context_menu_state(self, item_id: str):
        """Update context menu items based on selected item's installation status"""
        try:
            # Get all selected items
            selected_items = self.game_tree.selection()
            
            if len(selected_items) > 1:
                # Multiple items selected - handle bulk operations
                self._update_context_menu_for_bulk_selection(selected_items)
            else:
                # Single item selected - use existing logic
                self._update_context_menu_for_single_selection(item_id)
                
        except Exception as e:
            logger.error(f"Error updating context menu state: {e}")
            # Default to disabled on error
            self.context_menu.entryconfig(self.add_to_queue_index, state="disabled")
            self.context_menu.entryconfig(self.remove_from_queue_index, state="disabled")
            self.context_menu.entryconfig(self.add_all_variants_index, state="disabled")
            self.context_menu.entryconfig(self.remove_all_variants_index, state="disabled")
            self.context_menu.entryconfig(self.reveal_in_explorer_index, state="disabled")
            self.context_menu.entryconfig(self.uninstall_index, state="disabled")
            self._reveal_target_info = None
    
    def _update_context_menu_for_single_selection(self, item_id: str):
        """Update context menu for single item selection"""
        # Get item details
        item_details = self.tree_event_handler.get_item_details(item_id)
        item_type = item_details.get('item_type')
        game_key = item_details.get('game_key')
        variant_key = item_details.get('variant_key')
        
        # Determine if reveal should be enabled and get the target variant
        reveal_in_explorer_enabled, target_variant_info = self._determine_reveal_target(item_id, item_type, item_details)
        
        # Determine if queue actions should be enabled
        add_to_queue_enabled, remove_from_queue_enabled = self._determine_queue_actions_state(
            item_type, game_key, variant_key
        )
        
        # Determine if uninstall should be enabled (same logic as reveal - only for installed ROMs)
        uninstall_enabled = reveal_in_explorer_enabled
        
        # Update menu item states
        self.context_menu.entryconfig(self.add_to_queue_index, state="normal" if add_to_queue_enabled else "disabled")
        self.context_menu.entryconfig(self.remove_from_queue_index, state="normal" if remove_from_queue_enabled else "disabled")
        self.context_menu.entryconfig(self.add_all_variants_index, state="normal" if add_to_queue_enabled else "disabled")
        self.context_menu.entryconfig(self.remove_all_variants_index, state="normal" if remove_from_queue_enabled else "disabled")
        
        if reveal_in_explorer_enabled:
            self.context_menu.entryconfig(self.reveal_in_explorer_index, state="normal")
            # Store the target variant info for use in reveal_in_file_explorer
            self._reveal_target_info = target_variant_info
        else:
            self.context_menu.entryconfig(self.reveal_in_explorer_index, state="disabled")
            self._reveal_target_info = None
            
        # Update uninstall menu text and state for single selection
        self.context_menu.entryconfig(self.uninstall_index, label="Uninstall", state="normal" if uninstall_enabled else "disabled")
    
    def _update_context_menu_for_bulk_selection(self, selected_items: list):
        """Update context menu for multiple item selection"""
        # Disable reveal for bulk selection (only works for single items)
        self.context_menu.entryconfig(self.reveal_in_explorer_index, state="disabled")
        self._reveal_target_info = None
        
        # Check queue operations and installation status for bulk selection
        platform = self.get_current_platform_key()
        if not platform:
            # If no platform, disable everything
            self.context_menu.entryconfig(self.add_to_queue_index, state="disabled")
            self.context_menu.entryconfig(self.remove_from_queue_index, state="disabled")
            self.context_menu.entryconfig(self.add_all_variants_index, state="disabled")
            self.context_menu.entryconfig(self.remove_all_variants_index, state="disabled")
            self.context_menu.entryconfig(self.uninstall_index, label="Uninstall", state="disabled")
            return
        
        # Analyze selected items for queue and uninstall capabilities
        queueable_games = 0
        removable_games = 0
        installed_count = 0
        
        for item_id in selected_items:
            try:
                item_details = self.tree_event_handler.get_item_details(item_id)
                item_type = item_details.get('item_type')
                game_key = item_details.get('game_key')
                
                if item_type == 'game' and game_key:
                    # Check queue status for this game
                    is_queued = self.queue_manager.is_game_queued(game_key, platform)
                    
                    # Find the game to check if it has queueable variants
                    game = None
                    for g in self.current_games:
                        if g.key == game_key:
                            game = g
                            break
                    
                    if game:
                        # Check if game has downloadable variants
                        variants = game.get_variants_for_platform(platform)
                        queueable_variants = [
                            rom for rom in variants 
                            if not rom.is_installed_only and rom.is_installed() is not True
                        ]
                        
                        # Can add to queue if not queued and has queueable variants
                        if not is_queued and len(queueable_variants) > 0:
                            queueable_games += 1
                        
                        # Can remove from queue if currently queued
                        if is_queued:
                            removable_games += 1
                        
                        # Check if game has installed variants for uninstall
                        installed_variants = self._get_installed_variants_info(item_id)
                        if installed_variants:
                            installed_count += 1
                
                elif item_type == 'variant':
                    # For individual variants, check installation status
                    installed_status = self.game_tree.set(item_id, 'installed')
                    if installed_status == "✓":
                        installed_count += 1
                        
            except Exception as e:
                logger.error(f"Error analyzing item {item_id}: {e}")
                continue
        
        # Update queue operation states
        self.context_menu.entryconfig(self.add_to_queue_index, 
                                    state="normal" if queueable_games > 0 else "disabled")
        self.context_menu.entryconfig(self.remove_from_queue_index, 
                                    state="normal" if removable_games > 0 else "disabled")
        self.context_menu.entryconfig(self.add_all_variants_index, 
                                    state="normal" if queueable_games > 0 else "disabled")
        self.context_menu.entryconfig(self.remove_all_variants_index, 
                                    state="normal" if removable_games > 0 else "disabled")
        
        # Update uninstall state
        if installed_count > 0:
            self.context_menu.entryconfig(self.uninstall_index, 
                                        label=f"Uninstall ({installed_count} installed items)", 
                                        state="normal")
        else:
            self.context_menu.entryconfig(self.uninstall_index, 
                                        label="Uninstall", 
                                        state="disabled")
    
    def _count_installed_games_in_selection(self, selected_items: list) -> int:
        """Count how many selected items have installed ROMs"""
        installed_count = 0
        
        for item_id in selected_items:
            try:
                item_details = self.tree_event_handler.get_item_details(item_id)
                item_type = item_details.get('item_type')
                
                if item_type == 'game':
                    # Check if the game has any installed variants
                    installed_variants = self._get_installed_variants_info(item_id)
                    if installed_variants:
                        installed_count += 1
                # Note: Don't count individual variants as "games" for the counter
                        
            except Exception as e:
                logger.error(f"Error checking installation status for {item_id}: {e}")
                continue
                
        return installed_count
    
    def _determine_queue_actions_state(self, item_type: str, game_key: str, variant_key: str) -> tuple[bool, bool]:
        """Determine if queue actions should be enabled for the selected item
        
        Returns:
            tuple: (add_to_queue_enabled, remove_from_queue_enabled)
        """
        try:
            platform = self.get_current_platform_key()
            if not platform or not game_key:
                return False, False
            
            # Find the game
            game = None
            for g in self.current_games:
                if g.key == game_key:
                    game = g
                    break
            
            if not game:
                return False, False
            
            # Check if game is currently queued
            is_queued = self.queue_manager.is_game_queued(game_key, platform)
            
            if item_type == 'variant' and variant_key:
                # For specific variant - check if this variant can be queued/dequeued
                rom_variant = game.variants.get(variant_key)
                if not rom_variant:
                    return False, False
                
                # Cannot queue installed or installed-only ROMs
                if rom_variant.is_installed() is True or rom_variant.is_installed_only:
                    return False, is_queued  # Can only remove if queued
                
                # Can add if not queued, can remove if queued
                return not is_queued, is_queued
            
            else:
                # For game level - check if any variants can be queued
                variants = game.get_variants_for_platform(platform)
                queueable_variants = [
                    rom for rom in variants 
                    if not rom.is_installed_only and rom.is_installed() is not True
                ]
                
                # Can add to queue if there are queueable variants and not already queued
                can_add = len(queueable_variants) > 0 and not is_queued
                
                # Can remove if queued
                can_remove = is_queued
                
                return can_add, can_remove
                
        except Exception as e:
            logger.error(f"Error determining queue actions state: {e}")
            return False, False
    
    def _determine_reveal_target(self, item_id: str, item_type: str, item_details: dict) -> tuple[bool, Optional[dict]]:
        """Determine if reveal should be enabled and which variant to target
        
        Returns:
            (enabled: bool, target_variant_info: dict or None)
            target_variant_info contains game_key, variant_key for the target variant
        """
        try:
            if item_type == 'variant':
                # Case: Variant selected
                # Enable only if this specific variant is installed
                installed_status = self.game_tree.set(item_id, 'installed')
                if installed_status == "✓":
                    return True, {
                        'game_key': item_details.get('game_key'),
                        'variant_key': item_details.get('variant_key'),
                        'item_id': item_id
                    }
                else:
                    return False, None
                    
            elif item_type == 'game':
                # Case: Game (parent) selected
                # Enable if ANY variant is installed, target the first installed variant
                installed_variants = self._get_installed_variants_info(item_id)
                if installed_variants:
                    # Use the first installed variant
                    first_installed = installed_variants[0]
                    return True, first_installed
                else:
                    return False, None
            
            # Other cases: disabled
            return False, None
            
        except Exception as e:
            logger.error(f"Error determining reveal target: {e}")
            return False, None
    
    def _get_installed_variants_info(self, game_item_id: str) -> List[dict]:
        """Get information about all installed variants for a game
        
        Returns:
            List of dicts with game_key, variant_key, item_id for installed variants
        """
        installed_variants = []
        try:
            children = self.game_tree.get_children(game_item_id)
            for child in children:
                installed_status = self.game_tree.set(child, 'installed')
                if installed_status == "✓":
                    child_details = self.tree_event_handler.get_item_details(child)
                    if child_details.get('variant_key'):
                        installed_variants.append({
                            'game_key': child_details.get('game_key'),
                            'variant_key': child_details.get('variant_key'),
                            'item_id': child
                        })
            return installed_variants
        except Exception as e:
            logger.error(f"Error getting installed variants info for {game_item_id}: {e}")
            return []
    
    def reveal_in_file_explorer(self):
        """Reveal the selected ROM file in File Explorer using intelligent variant selection"""
        try:
            # Use the target variant info determined during context menu update
            if not hasattr(self, '_reveal_target_info') or not self._reveal_target_info:
                messagebox.showwarning("No Target", "No installed ROM variant to reveal.")
                return
            
            target_info = self._reveal_target_info
            game_key = target_info.get('game_key')
            variant_key = target_info.get('variant_key')
            
            if not game_key or not variant_key:
                messagebox.showerror("Error", "Could not determine ROM details for reveal.")
                return
            
            display_name = self.current_platform.get()
            platform = self._get_platform_key_from_display_name(display_name) if display_name else None
            
            if not platform:
                messagebox.showerror("Error", "Could not determine current platform.")
                return
            
            # Get the ROM file path for the target variant
            rom_file_path = self._get_installed_rom_path(game_key, variant_key, platform)
            if rom_file_path:
                self._open_in_explorer(rom_file_path, platform)
                logger.info(f"Revealing ROM variant {variant_key} of game {game_key} in explorer")
            else:
                messagebox.showerror("Error", "Could not locate the installed ROM file.")
            
        except Exception as e:
            logger.error(f"Error revealing ROM in explorer: {e}")
            messagebox.showerror("Error", f"An error occurred while trying to reveal the ROM in explorer: {e}")
    
    def _get_installed_rom_path(self, game_key: str, variant_key: str, platform: str) -> Optional[Path]:
        """Get the installed ROM file path using cached filename information"""
        try:
            # Find the game in current games
            game = None
            for g in self.current_games:
                if g.key == game_key:
                    game = g
                    break
                    
            if not game:
                logger.warning(f"Game not found: {game_key}")
                return None
            
            # Find the specific ROM variant using variant_key
            rom = None
            for rom_variant in game.variants.values():
                if rom_variant.create_variant_key() == variant_key:
                    rom = rom_variant
                    break
            
            if not rom:
                logger.warning(f"ROM variant not found: {variant_key}")
                return None
            
            # Get the cached installed filename
            installed_filename = rom.get_installed_filename()
            if installed_filename:
                target_dir = self.config_manager.get_target_directory(platform)
                if target_dir:
                    return target_dir / installed_filename
            
            logger.warning(f"No cached installed filename for ROM {rom.filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting installed ROM path: {e}")
            return None
    
    def _open_in_explorer(self, rom_file_path: Optional[Path], platform: str):
        """Open the ROM file or platform folder in explorer"""
        import subprocess
        import os
        
        logger.info(f"Opening ROM in explorer: {rom_file_path}")
        
        if rom_file_path and rom_file_path.exists():
            # Open explorer and select the specific file
            if os.name == 'nt':  # Windows
                try:
                    # Use explorer.exe with /select parameter to highlight the file
                    logger.info(f"Running: explorer.exe /select, {rom_file_path}")
                    result = subprocess.run(['explorer.exe', '/select,', str(rom_file_path)], 
                                          capture_output=True, text=True, timeout=10)
                    
                    # Don't use check=True - explorer.exe can return non-zero even when successful
                    if result.returncode == 0:
                        logger.info("Successfully opened explorer with file selected")
                        return
                    else:
                        logger.warning(f"Explorer returned code {result.returncode}, stderr: {result.stderr}")
                        # Still try fallback only if there was a real error
                        if "cannot find" in result.stderr.lower() or "not found" in result.stderr.lower():
                            logger.info("File not found, trying fallback to parent folder")
                            folder_path = rom_file_path.parent
                            subprocess.run(['explorer.exe', str(folder_path)], timeout=10)
                        else:
                            # Explorer opened but returned non-zero (this is normal), don't do fallback
                            logger.info("Explorer likely opened successfully despite non-zero return code")
                            return
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
                    logger.error(f"Error opening explorer with /select: {e}")
                    # Fallback to opening the parent folder
                    try:
                        folder_path = rom_file_path.parent
                        logger.info(f"Fallback: opening parent folder {folder_path}")
                        subprocess.run(['explorer.exe', str(folder_path)], timeout=10)
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
                        messagebox.showerror("Error", f"Could not open file explorer: {e}")
            else:
                # For non-Windows systems, just open the containing folder
                try:
                    folder_path = rom_file_path.parent
                    subprocess.run(['xdg-open', str(folder_path)], timeout=10)
                except Exception as e:
                    logger.error(f"Error opening file manager: {e}")
                    messagebox.showerror("Error", f"Could not open file manager: {e}")
        else:
            logger.warning(f"ROM file does not exist: {rom_file_path}")
            # If we can't find the specific ROM file, just open the platform's ROM folder
            target_dir = self.config_manager.get_target_directory(platform)
            if target_dir and target_dir.exists():
                try:
                    if os.name == 'nt':  # Windows
                        subprocess.run(['explorer.exe', str(target_dir)], timeout=10)
                    else:
                        subprocess.run(['xdg-open', str(target_dir)], timeout=10)
                except Exception as e:
                    logger.error(f"Error opening platform folder: {e}")
                    messagebox.showerror("Error", f"Could not open platform folder: {e}")
            else:
                messagebox.showerror("Error", f"ROM folder does not exist: {target_dir}")
    
    def _delete_cue_and_bin_files(self, rom_file_path: Path) -> List[Path]:
        """Delete a cue file and all its associated bin files
        
        Args:
            rom_file_path: Path to the ROM file (could be .cue or .bin)
            
        Returns:
            List of successfully deleted files
        """
        deleted_files = []
        
        if rom_file_path.suffix.lower() == '.cue':
            # For .cue files, find and delete associated .bin files
            parent_dir = rom_file_path.parent
            stem = rom_file_path.stem
            
            # Find all associated .bin files (e.g., game.bin, game (Track 1).bin, etc.)
            bin_files = list(parent_dir.glob(f"{stem}*.bin"))
            
            # Delete the .cue file first
            rom_file_path.unlink()
            deleted_files.append(rom_file_path)
            logger.info(f"Deleted cue file: {rom_file_path}")
            
            # Delete all associated .bin files
            for bin_file in bin_files:
                if bin_file.exists():
                    bin_file.unlink()
                    deleted_files.append(bin_file)
                    logger.info(f"Deleted associated bin file: {bin_file}")
        
        elif rom_file_path.suffix.lower() == '.bin':
            # For .bin files, check if there's a corresponding .cue file
            cue_file = rom_file_path.with_suffix('.cue')
            if cue_file.exists():
                # If there's a .cue file, delete both .cue and all .bin files
                deleted_files = self._delete_cue_and_bin_files(cue_file)
            else:
                # Just delete the .bin file if no .cue exists
                rom_file_path.unlink()
                deleted_files.append(rom_file_path)
                logger.info(f"Deleted bin file: {rom_file_path}")
        
        else:
            # For other file types, just delete the single file
            rom_file_path.unlink()
            deleted_files.append(rom_file_path)
            logger.info(f"Deleted ROM file: {rom_file_path}")
        
        return deleted_files

    def uninstall_rom(self):
        """Uninstall the selected ROM file(s) - handles both single and bulk selection"""
        selected_items = self.game_tree.selection()
        
        if len(selected_items) > 1:
            self._bulk_uninstall_roms(selected_items)
        else:
            self._single_uninstall_rom()
    
    def _single_uninstall_rom(self):
        """Uninstall a single selected ROM file"""
        from tkinter import messagebox
        
        try:
            # Use the target variant info determined during context menu update
            if not hasattr(self, '_reveal_target_info') or not self._reveal_target_info:
                messagebox.showwarning("No Target", "No installed ROM variant to uninstall.")
                return
            
            target_info = self._reveal_target_info
            game_key = target_info.get('game_key')
            variant_key = target_info.get('variant_key')
            
            if not game_key or not variant_key:
                messagebox.showerror("Error", "Could not determine ROM details for uninstall.")
                return
            
            display_name = self.current_platform.get()
            platform = self._get_platform_key_from_display_name(display_name) if display_name else None
            
            if not platform:
                messagebox.showerror("Error", "Could not determine current platform.")
                return
            
            # Find the game and ROM variant
            game = None
            for g in self.current_games:
                if g.key == game_key:
                    game = g
                    break
            
            if not game:
                messagebox.showerror("Error", "Could not find the game.")
                return
            
            # Find the specific ROM variant using variant_key
            rom = None
            for rom_variant in game.variants.values():
                if rom_variant.create_variant_key() == variant_key:
                    rom = rom_variant
                    break
            
            if not rom:
                messagebox.showerror("Error", "Could not find the ROM variant.")
                return
            
            # Get the ROM file path
            rom_file_path = self._get_installed_rom_path(game_key, variant_key, platform)
            if not rom_file_path or not rom_file_path.exists():
                messagebox.showerror("Error", "Could not locate the ROM file to uninstall.")
                return
            
            # Confirm uninstall
            rom_name = rom.clean_name or rom.filename
            
            # Check if this is a cue/bin set and inform user
            confirmation_message = f"Are you sure you want to uninstall:\n\n{rom_name}"
            if rom_file_path.suffix.lower() == '.cue':
                # Count associated bin files
                parent_dir = rom_file_path.parent
                stem = rom_file_path.stem
                bin_files = list(parent_dir.glob(f"{stem}*.bin"))
                if bin_files:
                    confirmation_message += f"\n\nThis will also delete {len(bin_files)} associated BIN file(s)."
            elif rom_file_path.suffix.lower() == '.bin':
                cue_file = rom_file_path.with_suffix('.cue')
                if cue_file.exists():
                    confirmation_message += f"\n\nThis will also delete the associated CUE file and any other BIN files."
            
            confirmation_message += f"\n\nThis action cannot be undone."
            
            if not messagebox.askyesno("Confirm Uninstall", confirmation_message):
                return
            
            # Perform the uninstall
            try:
                deleted_files = self._delete_cue_and_bin_files(rom_file_path)
                
                # Update ROM state to reflect uninstalled status
                rom.set_installed(False, None)
                
                # Remove from existing ROMs cache
                if hasattr(self, 'installation_status_manager'):
                    self.installation_status_manager.clear_existing_roms_cache()
                
                # Update the tree display for this game
                self.update_game_tree_item(game_key, platform)
                
                # Show success message with count of deleted files
                self._show_uninstall_success_message([deleted_files], [rom_name])
                
                logger.info(f"ROM uninstalled successfully: {rom_name} ({len(deleted_files)} files deleted)")
                
            except Exception as delete_error:
                logger.error(f"Error deleting ROM file: {delete_error}")
                messagebox.showerror("Error", f"Failed to delete ROM file: {delete_error}")
            
        except Exception as e:
            logger.error(f"Error uninstalling ROM: {e}")
            messagebox.showerror("Error", f"An error occurred while trying to uninstall the ROM: {e}")
    
    def _bulk_uninstall_roms(self, selected_items: list):
        """Uninstall multiple selected ROM files"""
        from tkinter import messagebox
        
        try:
            display_name = self.current_platform.get()
            platform = self._get_platform_key_from_display_name(display_name) if display_name else None
            
            if not platform:
                messagebox.showerror("Error", "Could not determine current platform.")
                return
            
            # Collect all installed variants from selected items
            variants_to_uninstall = []
            
            for item_id in selected_items:
                try:
                    item_details = self.tree_event_handler.get_item_details(item_id)
                    item_type = item_details.get('item_type')
                    game_key = item_details.get('game_key')
                    
                    if item_type == 'game':
                        # Get all installed variants for this game
                        installed_variants = self._get_installed_variants_info(item_id)
                        for variant_info in installed_variants:
                            variants_to_uninstall.append(variant_info)
                    elif item_type == 'variant':
                        # Check if this specific variant is installed
                        installed_status = self.game_tree.set(item_id, 'installed')
                        if installed_status == "✓":
                            variant_key = item_details.get('variant_key')
                            variants_to_uninstall.append({
                                'game_key': game_key,
                                'variant_key': variant_key,
                                'item_id': item_id
                            })
                            
                except Exception as e:
                    logger.error(f"Error processing item {item_id}: {e}")
                    continue
            
            if not variants_to_uninstall:
                messagebox.showwarning("No ROMs", "No installed ROMs found in selection.")
                return
            
            # Confirm bulk uninstall
            game_names = []
            for variant_info in variants_to_uninstall:
                game_key = variant_info.get('game_key')
                # Find the game to get its display name
                for game in self.current_games:
                    if game.key == game_key:
                        game_names.append(game.display_name)
                        break
            
            unique_games = list(set(game_names))
            confirmation_message = f"Are you sure you want to uninstall {len(variants_to_uninstall)} ROM variant(s) from {len(unique_games)} game(s)?"
            
            if len(unique_games) <= 5:
                confirmation_message += "\n\nGames:\n" + "\n".join([f"• {name}" for name in unique_games[:5]])
            else:
                confirmation_message += f"\n\nGames:\n" + "\n".join([f"• {name}" for name in unique_games[:5]])
                confirmation_message += f"\n• ... and {len(unique_games) - 5} more"
            
            confirmation_message += "\n\nThis action cannot be undone."
            
            if not messagebox.askyesno("Confirm Bulk Uninstall", confirmation_message):
                return
            
            # Perform bulk uninstall
            all_deleted_files = []
            successfully_uninstalled_names = []
            failed_uninstalls = []
            
            for variant_info in variants_to_uninstall:
                try:
                    game_key = variant_info.get('game_key')
                    variant_key = variant_info.get('variant_key')
                    
                    # Find the game and ROM variant
                    game = None
                    for g in self.current_games:
                        if g.key == game_key:
                            game = g
                            break
                    
                    if not game:
                        failed_uninstalls.append(f"Game not found: {game_key}")
                        continue
                    
                    # Find the specific ROM variant
                    rom = None
                    for rom_variant in game.variants.values():
                        if rom_variant.create_variant_key() == variant_key:
                            rom = rom_variant
                            break
                    
                    if not rom:
                        failed_uninstalls.append(f"ROM variant not found: {variant_key}")
                        continue
                    
                    # Get the ROM file path
                    rom_file_path = self._get_installed_rom_path(game_key, variant_key, platform)
                    if not rom_file_path or not rom_file_path.exists():
                        failed_uninstalls.append(f"File not found: {rom.clean_name or rom.filename}")
                        continue
                    
                    # Delete the ROM and associated files
                    deleted_files = self._delete_cue_and_bin_files(rom_file_path)
                    all_deleted_files.append(deleted_files)
                    
                    # Update ROM state
                    rom.set_installed(False, None)
                    
                    # Update tree display
                    self.update_game_tree_item(game_key, platform)
                    
                    successfully_uninstalled_names.append(rom.clean_name or rom.filename)
                    
                    logger.info(f"ROM uninstalled successfully: {rom.clean_name or rom.filename} ({len(deleted_files)} files deleted)")
                    
                except Exception as e:
                    logger.error(f"Error uninstalling ROM {variant_info}: {e}")
                    failed_uninstalls.append(f"Error: {str(e)}")
                    continue
            
            # Remove from existing ROMs cache
            if hasattr(self, 'installation_status_manager'):
                self.installation_status_manager.clear_existing_roms_cache()
            
            # Show results
            self._show_bulk_uninstall_results(all_deleted_files, successfully_uninstalled_names, failed_uninstalls)
            
        except Exception as e:
            logger.error(f"Error in bulk uninstall: {e}")
            messagebox.showerror("Error", f"An error occurred during bulk uninstall: {e}")
    
    def _show_uninstall_success_message(self, deleted_files_list: list, rom_names: list):
        """Show success message for uninstall operation"""
        from tkinter import messagebox
        
        if len(deleted_files_list) == 1:
            # Single ROM uninstall
            deleted_files = deleted_files_list[0]
            rom_name = rom_names[0]
            
            if len(deleted_files) > 1:
                if len(deleted_files) <= 10:
                    file_list = "\n".join([f"• {f.name}" for f in deleted_files])
                    messagebox.showinfo("Success", f"Successfully uninstalled {rom_name}\n\nDeleted files:\n{file_list}")
                else:
                    messagebox.showinfo("Success", f"Successfully uninstalled {rom_name}\n\nDeleted {len(deleted_files)} files.")
            else:
                messagebox.showinfo("Success", f"Successfully uninstalled {rom_name}")
    
    def _show_bulk_uninstall_results(self, all_deleted_files: list, successfully_uninstalled_names: list, failed_uninstalls: list):
        """Show results of bulk uninstall operation"""
        from tkinter import messagebox
        
        total_files_deleted = sum(len(deleted_files) for deleted_files in all_deleted_files)
        success_count = len(successfully_uninstalled_names)
        
        message = f"Bulk uninstall completed!\n\n"
        message += f"Successfully uninstalled: {success_count} ROM(s)\n"
        message += f"Total files deleted: {total_files_deleted}"
        
        if failed_uninstalls:
            message += f"\n\nFailed uninstalls ({len(failed_uninstalls)}):\n"
            message += "\n".join([f"• {failure}" for failure in failed_uninstalls[:5]])
            if len(failed_uninstalls) > 5:
                message += f"\n• ... and {len(failed_uninstalls) - 5} more"
        
        if success_count > 0:
            messagebox.showinfo("Bulk Uninstall Results", message)
        else:
            messagebox.showerror("Bulk Uninstall Failed", message)
    
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
        

        # Download status label
        self.status_label = ttk.Label(bottom_frame, text="Ready")
        self.status_label.pack(anchor=tk.W, pady=(5, 0))


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
        # Use display names for dropdown but maintain order from config
        display_names = [platforms[key] for key in platforms.keys()]
        self.platform_combo['values'] = display_names
        
        if platforms and not self.current_platform.get():
            # Set using display name of first platform
            first_key = list(platforms.keys())[0]
            self.current_platform.set(platforms[first_key])
    
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
                display_name = self.current_platform.get()
                if display_name:
                    platform = self._get_platform_key_from_display_name(display_name)
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
                # Convert platform key to display name for the dropdown
                display_name = available_platforms[last_platform]
                self.current_platform.set(display_name)
                logger.info(f"Restored last selected platform: {last_platform} ({display_name})")
            else:
                logger.warning(f"Last selected platform '{last_platform}' not available")
        
        # Refresh the display to show any existing games and selections
        display_name = self.current_platform.get()
        if display_name:
            # Convert display name back to platform key
            platform = self._get_platform_key_from_display_name(display_name)
            
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
        
        display_name = self.current_platform.get()
        if display_name:
            # Convert display name back to platform key
            platform = self._get_platform_key_from_display_name(display_name)
            
            if not platform:
                logger.warning(f"Could not find platform key for display name: {display_name}")
                return
                
            logger.info(f"=== on_platform_change() to {platform} ({display_name}) ===")
            
            # Load platform library in state manager to prepare for ROM operations
            load_start = time.time()
            self.state_manager.load_platform_library(platform)
            load_time = time.time() - load_start
            logger.info(f"load_platform_library() took {load_time:.2f}s")
            
            # Save the last selected platform (using the key)
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
        display_name = self.current_platform.get()
        if not display_name:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        platform = self._get_platform_key_from_display_name(display_name)
        if not platform:
            messagebox.showerror("Error", f"Invalid platform: {display_name}")
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
            
            # Scan for installed-only ROMs and merge them in
            self._safe_gui_update(lambda: self.update_status("Scanning for installed-only ROMs..."))
            try:
                target_directory = self.config_manager.get_target_directory(platform)
                if target_directory:
                    # Get normalized names of online ROMs to exclude them
                    online_rom_names = {self.rom_utils.normalize_rom_name(rom.clean_name) for rom in roms}
                    
                    # Debug logging to help troubleshoot matching issues
                    logger.debug(f"Platform {platform}: {len(roms)} online ROMs, {len(online_rom_names)} unique normalized names")
                    if roms:
                        sample_roms = roms[:3]
                        for rom in sample_roms:
                            normalized = self.rom_utils.normalize_rom_name(rom.clean_name)
                            logger.debug(f"  Online ROM: '{rom.clean_name}' -> '{normalized}'")
                    logger.debug(f"  Sample normalized names: {list(online_rom_names)[:5]}")
                    
                    # Scan for installed-only ROMs
                    installed_only_roms = self.rom_filter.scan_installed_only_roms(
                        target_directory, platform, online_rom_names
                    )
                    
                    if installed_only_roms:
                        logger.info(f"Found {len(installed_only_roms)} installed-only ROMs")
                        # Merge installed-only ROMs into the library
                        library = self.library_processor.merge_installed_only_roms(
                            library, installed_only_roms, platform
                        )
            except Exception as e:
                logger.error(f"Error scanning for installed-only ROMs: {e}")
            
            # Merge with existing library using transaction to batch saves
            with self.state_manager:
                for game in library.games.values():
                    self.state_manager.add_game(game)
            
            # Update UI and automatically check installed ROMs
            self._safe_gui_update(lambda: self._scan_complete_with_installation_check(len(library.games), platform))
            
        except Exception as e:
            logger.error(f"Error scanning ROMs: {e}")
            self._safe_gui_update(lambda: self.update_status(f"Error: {e}"))
        finally:
            self._safe_gui_update(lambda: self.progress_bar.stop())
            self._safe_gui_update(lambda: self.progress_bar.configure(mode='determinate'))
    
    def _scan_complete_with_installation_check(self, count: int, platform: str):
        """Handle scan completion and automatically check installed ROMs"""
        self.update_status(f"Scan complete: {count} games found. Checking installed ROMs...")
        
        # Update tag buttons
        platform_tags = self.state_manager.get_platform_tags(platform)
        categorized_tags = self.library_processor.categorize_tags(platform_tags) if platform_tags else {}
        self.tag_filter_manager.update_tag_buttons(platform, categorized_tags)
        
        # Automatically check for installed ROMs
        self.installation_status_manager.check_installed_roms()
        
    def _scan_complete(self, count: int):
        """Handle scan completion (legacy method, kept for compatibility)"""
        self.update_status(f"Scan complete: {count} games found")
        display_name = self.current_platform.get()
        platform = self._get_platform_key_from_display_name(display_name) if display_name else None
        if platform:
            platform_tags = self.state_manager.get_platform_tags(platform)
            categorized_tags = self.library_processor.categorize_tags(platform_tags) if platform_tags else {}
            self.tag_filter_manager.update_tag_buttons(platform, categorized_tags)
            self.refresh_game_list()
    
    def clear_selections(self):
        """Clear all queued items for current platform"""
        display_name = self.current_platform.get()
        if not display_name:
            return
        
        platform = self._get_platform_key_from_display_name(display_name)
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