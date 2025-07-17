"""
Game library GUI with dynamic filtering and game-centric interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from typing import Dict, Set, List, Optional, Callable
from pathlib import Path

from models.game_library import Game, ROM, GameLibrary
from state.transactional_state_manager import TransactionalStateManager
from config.enhanced_config_manager import EnhancedConfigManager
from downloader.enhanced_download_manager import EnhancedDownloadManager, DownloadProgress, DownloadResult
from processors.game_library_processor import GameLibraryProcessor
from scraper.web_scraper import WebScraper

logger = logging.getLogger(__name__)


class GameLibraryGUI:
    """Game library GUI with dynamic filtering"""
    
    def __init__(self, root: tk.Tk = None):
        self.root = root or tk.Tk()
        self.root.title("ROM Downloader - Game Library")
        self.root.geometry("1200x800")
        
        # Initialize managers
        self.config_manager = EnhancedConfigManager()
        self.state_manager = TransactionalStateManager()
        self.download_manager = EnhancedDownloadManager(self.config_manager)
        self.library_processor = GameLibraryProcessor()
        self.web_scraper = WebScraper()
        
        # GUI state
        self.current_platform = tk.StringVar()
        self.current_platform.trace('w', self.on_platform_change)
        
        self.active_tag_filters = set()
        self.search_query = tk.StringVar()
        self.search_query.trace('w', self.on_search_change)
        
        # UI components
        self.tag_buttons = {}
        self.game_tree = None
        self.variant_list = None
        self.progress_bar = None
        self.status_label = None
        
        # Data
        self.current_games = []
        self.downloading = False
        
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
        
        # Main content area
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
        ttk.Button(top_frame, text="Download Selected", command=self.download_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(top_frame, text="Clear Selections", command=self.clear_selections).pack(side=tk.LEFT)
    
    def setup_tag_filters(self, parent):
        """Set up dynamic tag filter buttons"""
        self.tag_frame = ttk.LabelFrame(parent, text="Filter by Tags")
        self.tag_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Container for tag buttons
        self.tag_container = ttk.Frame(self.tag_frame)
        self.tag_container.pack(fill=tk.X, padx=5, pady=5)
    
    def setup_main_content(self, parent):
        """Set up the main content area"""
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        content_frame.grid_columnconfigure(0, weight=2)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Game list (left side)
        self.setup_game_list(content_frame)
        
        # Variant details (right side)
        self.setup_variant_details(content_frame)
    
    def setup_game_list(self, parent):
        """Set up the game list treeview"""
        game_frame = ttk.LabelFrame(parent, text="Games")
        game_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Configure grid
        game_frame.grid_rowconfigure(0, weight=1)
        game_frame.grid_columnconfigure(0, weight=1)
        
        # Create treeview
        columns = ('selected', 'variants', 'tags')
        self.game_tree = ttk.Treeview(game_frame, columns=columns, show='tree headings')
        
        # Configure columns
        self.game_tree.heading('#0', text='Game')
        self.game_tree.heading('selected', text='Selected')
        self.game_tree.heading('variants', text='Variants')
        self.game_tree.heading('tags', text='Tags')
        
        self.game_tree.column('#0', width=300)
        self.game_tree.column('selected', width=80, anchor='center')
        self.game_tree.column('variants', width=80, anchor='center')
        self.game_tree.column('tags', width=200)
        
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(game_frame, orient=tk.VERTICAL, command=self.game_tree.yview)
        tree_scroll_x = ttk.Scrollbar(game_frame, orient=tk.HORIZONTAL, command=self.game_tree.xview)
        self.game_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        # Pack components
        self.game_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        tree_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind events
        self.game_tree.bind('<Button-1>', self.on_game_click)
        self.game_tree.bind('<Double-Button-1>', self.on_game_double_click)
        self.game_tree.bind('<<TreeviewSelect>>', self.on_game_select)
    
    def setup_variant_details(self, parent):
        """Set up the variant details panel"""
        details_frame = ttk.LabelFrame(parent, text="ROM Variants")
        details_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        details_frame.grid_rowconfigure(0, weight=1)
        details_frame.grid_columnconfigure(0, weight=1)
        
        # Variant list
        variant_columns = ('filename', 'size', 'tags')
        self.variant_list = ttk.Treeview(details_frame, columns=variant_columns, show='headings')
        
        # Configure columns
        self.variant_list.heading('filename', text='Filename')
        self.variant_list.heading('size', text='Size')
        self.variant_list.heading('tags', text='Tags')
        
        self.variant_list.column('filename', width=200)
        self.variant_list.column('size', width=80)
        self.variant_list.column('tags', width=150)
        
        # Scrollbar
        variant_scroll = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.variant_list.yview)
        self.variant_list.configure(yscrollcommand=variant_scroll.set)
        
        # Pack components
        self.variant_list.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        variant_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind events
        self.variant_list.bind('<Double-Button-1>', self.on_variant_select)
    
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
        file_menu.add_command(label="Export Selections...", command=self.export_selections)
        file_menu.add_command(label="Import Selections...", command=self.import_selections)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
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
            self.update_tag_buttons(platform)
            self.refresh_game_list()
    
    def on_platform_change(self, *args):
        """Handle platform selection change"""
        platform = self.current_platform.get()
        if platform:
            # Save the last selected platform
            self.state_manager.set_last_selected_platform(platform)
            self.update_tag_buttons(platform)
            self.refresh_game_list()
    
    def update_tag_buttons(self, platform: str):
        """Update tag filter buttons for the selected platform"""
        # Clear existing buttons
        for button in self.tag_buttons.values():
            button.destroy()
        self.tag_buttons.clear()
        self.active_tag_filters.clear()
        
        # Get tags for this platform
        tags = self.state_manager.get_platform_tags(platform)
        if not tags:
            return
        
        # Create toggle buttons for each tag
        for i, tag in enumerate(sorted(tags)):
            var = tk.BooleanVar()
            button = ttk.Checkbutton(
                self.tag_container,
                text=tag,
                variable=var,
                command=lambda t=tag, v=var: self.toggle_tag_filter(t, v)
            )
            button.grid(row=i // 8, column=i % 8, padx=2, pady=2, sticky=tk.W)
            self.tag_buttons[tag] = button
    
    def toggle_tag_filter(self, tag: str, var: tk.BooleanVar):
        """Toggle tag filter on/off"""
        if var.get():
            self.active_tag_filters.add(tag)
        else:
            self.active_tag_filters.discard(tag)
        
        self.refresh_game_list()
    
    def on_search_change(self, *args):
        """Handle search query change"""
        self.refresh_game_list()
    
    def refresh_game_list(self):
        """Refresh the game list with current filters"""
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Clear existing items
        self.game_tree.delete(*self.game_tree.get_children())
        
        # Get games for platform
        games = self.state_manager.get_games_for_platform(platform)
        
        # Apply filters
        filtered_games = self.apply_filters(games)
        
        # Populate tree
        for game in filtered_games:
            self.add_game_to_tree(game, platform)
        
        self.current_games = filtered_games
        self.update_status(f"Showing {len(filtered_games)} games")
    
    def apply_filters(self, games: List[Game]) -> List[Game]:
        """Apply current filters to game list"""
        filtered_games = games
        
        # Apply tag filters
        if self.active_tag_filters:
            filtered_games = [
                game for game in filtered_games
                if self.game_matches_tags(game)
            ]
        
        # Apply search filter
        search_query = self.search_query.get().lower()
        if search_query:
            filtered_games = [
                game for game in filtered_games
                if search_query in game.display_name.lower()
            ]
        
        return filtered_games
    
    def game_matches_tags(self, game: Game) -> bool:
        """Check if game matches current tag filters"""
        game_tags = game.get_all_tags()
        return any(tag in game_tags for tag in self.active_tag_filters)
    
    def add_game_to_tree(self, game: Game, platform: str):
        """Add a game to the treeview"""
        # Check if game is selected
        selection = self.state_manager.get_selection(game.key, platform)
        selected_text = "✓" if selection else ""
        
        # Get variant count
        variant_count = len(game.get_variants_for_platform(platform))
        
        # Get tags for display
        tags = sorted(game.get_all_tags())
        tags_text = ", ".join(tags[:5])  # Show first 5 tags
        if len(tags) > 5:
            tags_text += "..."
        
        # Insert item
        item = self.game_tree.insert(
            '',
            'end',
            text=game.display_name,
            values=(selected_text, variant_count, tags_text),
            tags=('selected' if selection else 'unselected',)
        )
        
        # Store game reference
        self.game_tree.set(item, 'game_key', game.key)
    
    def on_game_click(self, event):
        """Handle game tree click"""
        region = self.game_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.game_tree.identify_column(event.x, event.y)
            if column == '#1':  # Selected column
                self.toggle_game_selection(event)
    
    def on_game_double_click(self, event):
        """Handle game tree double-click"""
        self.toggle_game_selection(event)
    
    def toggle_game_selection(self, event):
        """Toggle game selection"""
        item = self.game_tree.identify_row(event.y)
        if not item:
            return
        
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Get game key
        try:
            game_key = self.game_tree.set(item, 'game_key')
        except:
            return
        
        # Find game
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if not game:
            return
        
        # Toggle selection
        current_selection = self.state_manager.get_selection(game_key, platform)
        
        if current_selection:
            # Remove selection
            if f"{platform}:{game_key}" in self.state_manager.library.selections:
                del self.state_manager.library.selections[f"{platform}:{game_key}"]
                self.state_manager.dirty = True
        else:
            # Add selection - pick best variant
            variants = game.get_variants_for_platform(platform)
            if variants:
                best_variant = game.get_best_variant(platform, self.config_manager.get_preferred_regions())
                if best_variant:
                    variant_key = best_variant.create_variant_key()
                    self.state_manager.select_rom_variant(game_key, platform, variant_key)
        
        # Refresh display
        self.refresh_game_list()
    
    def on_game_select(self, event):
        """Handle game selection in tree"""
        selection = self.game_tree.selection()
        if not selection:
            self.variant_list.delete(*self.variant_list.get_children())
            return
        
        item = selection[0]
        game_key = self.game_tree.set(item, 'game_key')
        
        # Find game
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if game:
            self.show_game_variants(game)
    
    def show_game_variants(self, game: Game):
        """Show variants for the selected game"""
        platform = self.current_platform.get()
        if not platform:
            return
        
        # Clear existing items
        self.variant_list.delete(*self.variant_list.get_children())
        
        # Get variants for this platform
        variants = game.get_variants_for_platform(platform)
        
        # Add variants to list
        for rom in variants:
            tags_text = ", ".join(sorted(rom.tags))
            self.variant_list.insert(
                '',
                'end',
                values=(rom.filename, rom.size, tags_text)
            )
    
    def on_variant_select(self, event):
        """Handle variant selection"""
        selection = self.variant_list.selection()
        if not selection:
            return
        
        # Get selected variant
        item = selection[0]
        filename = self.variant_list.item(item)['values'][0]
        
        # Find the game and variant
        game_selection = self.game_tree.selection()
        if not game_selection:
            return
        
        game_item = game_selection[0]
        game_key = self.game_tree.set(game_item, 'game_key')
        
        # Find game
        game = None
        for g in self.current_games:
            if g.key == game_key:
                game = g
                break
        
        if not game:
            return
        
        # Find variant
        platform = self.current_platform.get()
        variants = game.get_variants_for_platform(platform)
        
        selected_rom = None
        for rom in variants:
            if rom.filename == filename:
                selected_rom = rom
                break
        
        if selected_rom:
            # Select this variant
            variant_key = selected_rom.create_variant_key()
            self.state_manager.select_rom_variant(game_key, platform, variant_key)
            self.refresh_game_list()
    
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
            # Get platform configuration
            platform_config = self.config_manager.get_platform_config(platform)
            if not platform_config:
                self.root.after(0, lambda: self.update_status("Platform configuration not found"))
                return
            
            # Scrape ROMs
            url = platform_config['url']
            file_pattern = platform_config.get('file_pattern')
            
            roms = self.web_scraper.scrape_roms(url, file_pattern)
            
            if not roms:
                self.root.after(0, lambda: self.update_status("No ROMs found"))
                return
            
            # Process into library
            library = self.library_processor.process_rom_collection(roms, platform)
            
            # Merge with existing library using transaction to batch saves
            with self.state_manager:
                for game in library.games.values():
                    self.state_manager.add_game(game)
            
            # Update UI
            self.root.after(0, lambda: self._scan_complete(len(library.games)))
            
        except Exception as e:
            logger.error(f"Error scanning ROMs: {e}")
            self.root.after(0, lambda: self.update_status(f"Error: {e}"))
        finally:
            self.root.after(0, lambda: self.progress_bar.stop())
            self.root.after(0, lambda: self.progress_bar.configure(mode='determinate'))
    
    def _scan_complete(self, count: int):
        """Handle scan completion"""
        self.update_status(f"Scan complete: {count} games found")
        self.update_tag_buttons(self.current_platform.get())
        self.refresh_game_list()
    
    def download_selected(self):
        """Download selected ROMs"""
        platform = self.current_platform.get()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return
        
        if self.downloading:
            messagebox.showwarning("Warning", "Download already in progress")
            return
        
        # Get selected ROMs
        selected_roms = self.state_manager.get_selected_roms(platform)
        
        if not selected_roms:
            messagebox.showinfo("Info", "No ROMs selected for download")
            return
        
        # Confirm download
        if not messagebox.askyesno("Confirm Download", f"Download {len(selected_roms)} ROMs?"):
            return
        
        self.downloading = True
        self.update_status("Starting download...")
        
        # Start download in separate thread
        import threading
        thread = threading.Thread(target=self._download_thread, args=(selected_roms, platform))
        thread.daemon = True
        thread.start()
    
    def _download_thread(self, roms: List[ROM], platform: str):
        """Download ROMs in a separate thread"""
        try:
            def progress_callback(rom: ROM, progress: DownloadProgress):
                self.root.after(0, lambda: self._update_download_progress(rom, progress))
            
            def completion_callback(rom: ROM, result: DownloadResult):
                self.root.after(0, lambda: self._update_download_completion(rom, result))
            
            # Start download
            results = self.download_manager.download_roms(
                roms, platform, progress_callback, completion_callback
            )
            
            # Show results
            successful = sum(1 for r in results if r.success)
            self.root.after(0, lambda: self._download_complete(successful, len(results)))
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            self.root.after(0, lambda: self.update_status(f"Download error: {e}"))
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
        else:
            self.update_status(f"Failed: {rom.filename} - {result.error_message}")
    
    def _download_complete(self, successful: int, total: int):
        """Handle download completion"""
        self.progress_bar['value'] = 0
        self.update_status(f"Download complete: {successful}/{total} successful")
        messagebox.showinfo("Download Complete", f"Downloaded {successful} out of {total} ROMs")
    
    def clear_selections(self):
        """Clear all selections for current platform"""
        platform = self.current_platform.get()
        if not platform:
            return
        
        if messagebox.askyesno("Confirm", "Clear all selections for this platform?"):
            self.state_manager.clear_platform_selections(platform)
            self.refresh_game_list()
    
    def export_selections(self):
        """Export selections to file"""
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
                messagebox.showinfo("Success", "Selections exported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export selections: {e}")
    
    def import_selections(self):
        """Import selections from file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                success = self.state_manager.import_selections(Path(filename))
                if success:
                    messagebox.showinfo("Success", "Selections imported successfully")
                    self.refresh_game_list()
                else:
                    messagebox.showerror("Error", "Failed to import selections")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import selections: {e}")
    
    def clear_cache(self):
        """Clear application cache"""
        if messagebox.askyesno("Confirm", "Clear all cached data?"):
            # Clear state manager cache
            self.state_manager.library.games.clear()
            self.state_manager.library.tag_registry.clear()
            self.state_manager.dirty = True
            
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
- Game-centric organization
- Configurable tool pipelines
- Persistent selections
- Multi-platform support
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
        self.state_manager.save_if_dirty()
        self.root.destroy()
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'state_manager'):
            self.state_manager.save_if_dirty()