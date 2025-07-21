"""
Settings Window for ROM Downloader

Provides GUI interfaces for:
- Download settings (delay between downloads)
- Platform configuration (editing platforms.json)
- Network paths configuration
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import re
from typing import Dict, Any, Optional
from pathlib import Path

from src.config.enhanced_config_manager import EnhancedConfigManager

logger = logging.getLogger(__name__)


class SettingsWindow:
    """Settings window with tabbed interface for different configuration options"""
    
    def __init__(self, parent, config_manager: EnhancedConfigManager):
        """Initialize the settings window
        
        Args:
            parent: Parent window
            config_manager: Configuration manager instance
        """
        self.parent = parent
        self.config_manager = config_manager
        self.window = None
        self.config_data = {}
        
        # UI components
        self.notebook = None
        
        # Download Settings tab
        self.delay_min_var = tk.IntVar()
        self.delay_max_var = tk.IntVar()
        self.max_concurrent_var = tk.IntVar()
        
        # Network Settings tab
        self.network_drive_var = tk.StringVar()
        self.target_directory_var = tk.StringVar()
        
        # Platform Settings tab
        self.platforms_tree = None
        self.platform_form_frame = None
        self.current_platform_key = None
        
        # Platform form variables
        self.platform_name_var = tk.StringVar()
        self.platform_url_var = tk.StringVar()
        self.platform_folder_var = tk.StringVar()
        self.platform_extensions_var = tk.StringVar()
        self.platform_pattern_var = tk.StringVar()
        self.platform_extract_var = tk.BooleanVar()
    
    def show(self):
        """Show the settings window"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        
        self.window = tk.Toplevel(self.parent)
        self.window.title("Settings")
        self.window.geometry("800x600")
        self.window.grab_set()  # Make window modal
        
        # Load current configuration
        self.load_current_config()
        
        # Create the UI
        self.create_ui()
        
        # Center the window
        self.center_window()
        
        logger.info("Settings window opened")
    
    def center_window(self):
        """Center the window on the parent"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
    
    def load_current_config(self):
        """Load current configuration from config manager"""
        try:
            # Load the platforms.json file directly
            config_path = Path("config/platforms.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            else:
                # Create default config structure
                self.config_data = {
                    "settings": {
                        "network_drive_path": "//BATOCERA/share/roms",
                        "target_directory": "//BATOCERA/share/roms",
                        "download_delay_min": 2,
                        "download_delay_max": 5,
                        "preferred_regions": ["USA", "US", "En", "English"],
                        "max_concurrent_downloads": 1
                    },
                    "platforms": {}
                }
            
            # Populate UI variables
            settings = self.config_data.get("settings", {})
            self.delay_min_var.set(settings.get("download_delay_min", 2))
            self.delay_max_var.set(settings.get("download_delay_max", 5))
            self.max_concurrent_var.set(settings.get("max_concurrent_downloads", 1))
            self.network_drive_var.set(settings.get("network_drive_path", "//BATOCERA/share/roms"))
            self.target_directory_var.set(settings.get("target_directory", "//BATOCERA/share/roms"))
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            messagebox.showerror("Error", f"Failed to load configuration: {e}")
    
    def create_ui(self):
        """Create the main UI with tabbed interface"""
        # Main container
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_download_settings_tab()
        self.create_network_settings_tab()
        self.create_platform_settings_tab()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Buttons
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Apply", command=self.apply_settings).pack(side=tk.RIGHT, padx=(0, 5))
    
    def create_download_settings_tab(self):
        """Create the download settings tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Download")
        
        # Download delay section
        delay_frame = ttk.LabelFrame(tab_frame, text="Download Delays")
        delay_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(delay_frame, text="Minimum delay between downloads (seconds):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        delay_min_spinbox = ttk.Spinbox(delay_frame, from_=1, to=60, textvariable=self.delay_min_var, width=10)
        delay_min_spinbox.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(delay_frame, text="Maximum delay between downloads (seconds):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        delay_max_spinbox = ttk.Spinbox(delay_frame, from_=1, to=60, textvariable=self.delay_max_var, width=10)
        delay_max_spinbox.grid(row=1, column=1, padx=5, pady=5)
        
        # Concurrent downloads section
        concurrent_frame = ttk.LabelFrame(tab_frame, text="Concurrent Downloads")
        concurrent_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(concurrent_frame, text="Maximum concurrent downloads:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        concurrent_spinbox = ttk.Spinbox(concurrent_frame, from_=1, to=10, textvariable=self.max_concurrent_var, width=10)
        concurrent_spinbox.grid(row=0, column=1, padx=5, pady=5)
        
        # Help text
        help_frame = ttk.LabelFrame(tab_frame, text="Help")
        help_frame.pack(fill=tk.X, padx=10, pady=10)
        
        help_text = """Download Delays:
• Minimum/Maximum delay: Random delay between these values will be used between downloads
• This helps avoid overwhelming the download servers
• Recommended: 2-5 seconds

Concurrent Downloads:
• Number of downloads that can run simultaneously
• Higher values download faster but use more bandwidth
• Recommended: 1-3 downloads"""
        
        ttk.Label(help_frame, text=help_text, justify=tk.LEFT).pack(padx=5, pady=5)
    
    def create_network_settings_tab(self):
        """Create the network settings tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Network")
        
        # Network paths section
        paths_frame = ttk.LabelFrame(tab_frame, text="Network Paths")
        paths_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Network drive path
        ttk.Label(paths_frame, text="Network drive path:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        network_entry = ttk.Entry(paths_frame, textvariable=self.network_drive_var, width=50)
        network_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=self.browse_network_drive).grid(row=0, column=2, padx=5, pady=5)
        
        # Target directory
        ttk.Label(paths_frame, text="Target directory:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        target_entry = ttk.Entry(paths_frame, textvariable=self.target_directory_var, width=50)
        target_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=self.browse_target_directory).grid(row=1, column=2, padx=5, pady=5)
        
        # Help text
        help_frame = ttk.LabelFrame(tab_frame, text="Help")
        help_frame.pack(fill=tk.X, padx=10, pady=10)
        
        help_text = """Network Paths:
• Network drive path: Primary network location for ROM storage (e.g., //BATOCERA/share/roms)
• Target directory: Where ROMs will be copied after download
• Both paths can be the same for direct network downloads
• Use UNC paths (//server/share) for network drives
• Use local paths (C:\\ROMs) for local storage

Examples:
• Network: //BATOCERA/share/roms
• Local: C:\\ROMs\\Collection"""
        
        ttk.Label(help_frame, text=help_text, justify=tk.LEFT).pack(padx=5, pady=5)
    
    def create_platform_settings_tab(self):
        """Create the platform configuration tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Platforms")
        
        # Create paned window for tree and form
        paned_window = ttk.PanedWindow(tab_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left side - Platform list
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Platforms:").pack(anchor=tk.W)
        
        # Platform tree
        self.platforms_tree = ttk.Treeview(left_frame, columns=('name', 'url'), show='tree headings')
        self.platforms_tree.heading('#0', text='Key')
        self.platforms_tree.heading('name', text='Name')
        self.platforms_tree.heading('url', text='URL')
        self.platforms_tree.column('#0', width=100)
        self.platforms_tree.column('name', width=150)
        self.platforms_tree.column('url', width=200)
        
        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.platforms_tree.yview)
        self.platforms_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.platforms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind tree selection
        self.platforms_tree.bind('<<TreeviewSelect>>', self.on_platform_select)
        
        # Platform buttons
        platform_buttons_frame = ttk.Frame(left_frame)
        platform_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(platform_buttons_frame, text="Add Platform", command=self.add_platform).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(platform_buttons_frame, text="Delete Platform", command=self.delete_platform).pack(side=tk.LEFT)
        
        # Right side - Platform form
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=2)
        
        self.create_platform_form(right_frame)
        
        # Load platforms into tree
        self.load_platforms_tree()
    
    def create_platform_form(self, parent):
        """Create the platform configuration form"""
        self.platform_form_frame = ttk.LabelFrame(parent, text="Platform Configuration")
        self.platform_form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Platform form fields
        row = 0
        
        ttk.Label(self.platform_form_frame, text="Display Name:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.platform_form_frame, textvariable=self.platform_name_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        ttk.Label(self.platform_form_frame, text="Download URL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.platform_form_frame, textvariable=self.platform_url_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        ttk.Label(self.platform_form_frame, text="Target Folder:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.platform_form_frame, textvariable=self.platform_folder_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        row += 1
        
        ttk.Label(self.platform_form_frame, text="File Extensions:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.platform_form_frame, textvariable=self.platform_extensions_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(self.platform_form_frame, text="(comma-separated, e.g. .zip,.7z,.rvz)", font=('TkDefaultFont', 8)).grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1
        
        ttk.Label(self.platform_form_frame, text="File Pattern:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.platform_form_frame, textvariable=self.platform_pattern_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(self.platform_form_frame, text="(regex pattern)", font=('TkDefaultFont', 8)).grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1
        
        ttk.Checkbutton(self.platform_form_frame, text="Extract archives", variable=self.platform_extract_var).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        row += 1
        
        # Configure column weights
        self.platform_form_frame.columnconfigure(1, weight=1)
        
        # Update button
        ttk.Button(self.platform_form_frame, text="Update Platform", command=self.update_platform).grid(row=row, column=1, pady=10)
    
    def load_platforms_tree(self):
        """Load platforms into the tree view"""
        # Clear existing items
        for item in self.platforms_tree.get_children():
            self.platforms_tree.delete(item)
        
        # Load platforms from config
        platforms = self.config_data.get("platforms", {})
        for key, platform in platforms.items():
            name = platform.get("name", key)
            url = platform.get("url", "")
            self.platforms_tree.insert('', 'end', iid=key, text=key, values=(name, url))
    
    def on_platform_select(self, event):
        """Handle platform selection in tree"""
        selection = self.platforms_tree.selection()
        if not selection:
            return
        
        platform_key = selection[0]
        self.current_platform_key = platform_key
        
        # Load platform data into form
        platforms = self.config_data.get("platforms", {})
        platform = platforms.get(platform_key, {})
        
        self.platform_name_var.set(platform.get("name", ""))
        self.platform_url_var.set(platform.get("url", ""))
        self.platform_folder_var.set(platform.get("target_folder", ""))
        
        # Handle file extensions
        extensions = platform.get("file_extensions", [])
        self.platform_extensions_var.set(", ".join(extensions))
        
        self.platform_pattern_var.set(platform.get("file_pattern", ""))
        self.platform_extract_var.set(platform.get("extract_archives", False))
    
    def add_platform(self):
        """Add a new platform"""
        # Simple dialog to get platform key
        dialog = tk.Toplevel(self.window)
        dialog.title("Add Platform")
        dialog.geometry("300x100")
        dialog.grab_set()
        
        ttk.Label(dialog, text="Platform Key:").pack(pady=5)
        key_var = tk.StringVar()
        key_entry = ttk.Entry(dialog, textvariable=key_var, width=30)
        key_entry.pack(pady=5)
        key_entry.focus()
        
        def confirm():
            key = key_var.get().strip()
            if not key:
                messagebox.showerror("Error", "Platform key cannot be empty")
                return
            
            if key in self.config_data.get("platforms", {}):
                messagebox.showerror("Error", "Platform key already exists")
                return
            
            # Add new platform with default values
            if "platforms" not in self.config_data:
                self.config_data["platforms"] = {}
            
            self.config_data["platforms"][key] = {
                "name": key,
                "url": "",
                "target_folder": key.lower(),
                "file_extensions": [".zip"],
                "file_pattern": ".*\\.zip$",
                "extract_archives": False
            }
            
            # Reload tree and select new platform
            self.load_platforms_tree()
            self.platforms_tree.selection_set(key)
            self.on_platform_select(None)
            
            dialog.destroy()
        
        def cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT)
        
        # Bind Enter key
        key_entry.bind('<Return>', lambda e: confirm())
    
    def delete_platform(self):
        """Delete the selected platform"""
        if not self.current_platform_key:
            messagebox.showwarning("Warning", "Please select a platform to delete")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete platform '{self.current_platform_key}'?"):
            platforms = self.config_data.get("platforms", {})
            if self.current_platform_key in platforms:
                del platforms[self.current_platform_key]
                self.load_platforms_tree()
                self.current_platform_key = None
                
                # Clear form
                self.platform_name_var.set("")
                self.platform_url_var.set("")
                self.platform_folder_var.set("")
                self.platform_extensions_var.set("")
                self.platform_pattern_var.set("")
                self.platform_extract_var.set(False)
    
    def update_platform(self):
        """Update the selected platform with form data"""
        if not self.current_platform_key:
            messagebox.showwarning("Warning", "Please select a platform to update")
            return
        
        # Validate form data
        if not self.platform_name_var.get().strip():
            messagebox.showerror("Error", "Platform name cannot be empty")
            return
        
        if not self.platform_url_var.get().strip():
            messagebox.showerror("Error", "Platform URL cannot be empty")
            return
        
        # Parse file extensions
        extensions_text = self.platform_extensions_var.get().strip()
        extensions = [ext.strip() for ext in extensions_text.split(",") if ext.strip()]
        
        if not extensions:
            messagebox.showerror("Error", "At least one file extension is required")
            return
        
        # Validate regex pattern
        pattern = self.platform_pattern_var.get().strip()
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                messagebox.showerror("Error", f"Invalid regex pattern: {e}")
                return
        
        # Update platform data
        platforms = self.config_data.get("platforms", {})
        platforms[self.current_platform_key] = {
            "name": self.platform_name_var.get().strip(),
            "url": self.platform_url_var.get().strip(),
            "target_folder": self.platform_folder_var.get().strip() or self.current_platform_key.lower(),
            "file_extensions": extensions,
            "file_pattern": pattern,
            "extract_archives": self.platform_extract_var.get()
        }
        
        # Reload tree to show updated data
        self.load_platforms_tree()
        self.platforms_tree.selection_set(self.current_platform_key)
        
        messagebox.showinfo("Success", "Platform updated successfully")
    
    def browse_network_drive(self):
        """Browse for network drive path"""
        path = filedialog.askdirectory(title="Select Network Drive Path", initialdir=self.network_drive_var.get())
        if path:
            self.network_drive_var.set(path)
    
    def browse_target_directory(self):
        """Browse for target directory"""
        path = filedialog.askdirectory(title="Select Target Directory", initialdir=self.target_directory_var.get())
        if path:
            self.target_directory_var.set(path)
    
    def apply_settings(self):
        """Apply settings without closing the window"""
        if self.save_config():
            messagebox.showinfo("Success", "Settings applied successfully")
    
    def save_settings(self):
        """Save settings and close the window"""
        if self.save_config():
            self.window.destroy()
    
    def save_config(self):
        """Save the configuration to file"""
        try:
            # Validate settings
            if self.delay_min_var.get() > self.delay_max_var.get():
                messagebox.showerror("Error", "Minimum delay cannot be greater than maximum delay")
                return False
            
            # Update settings in config data
            settings = self.config_data.setdefault("settings", {})
            settings["download_delay_min"] = self.delay_min_var.get()
            settings["download_delay_max"] = self.delay_max_var.get()
            settings["max_concurrent_downloads"] = self.max_concurrent_var.get()
            settings["network_drive_path"] = self.network_drive_var.get().strip()
            settings["target_directory"] = self.target_directory_var.get().strip()
            
            # Save to file
            config_path = Path("config/platforms.json")
            config_path.parent.mkdir(exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
            # Reload config in config manager
            self.config_manager.reload_config()
            
            logger.info("Settings saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            return False
    
    def cancel(self):
        """Cancel and close the window without saving"""
        self.window.destroy()