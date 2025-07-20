"""
Tag Filter Manager for the ROM Downloader GUI

Handles all tag-related filtering functionality including:
- Dynamic tag filter buttons 
- Custom tag input with auto-completion
- Tag categorization and management
- Active tag state tracking
"""

import tkinter as tk
from tkinter import ttk
from typing import Set, Dict, Callable, Optional, List
import logging

logger = logging.getLogger(__name__)


class TagFilterManager:
    """Manages tag filtering functionality for the game library GUI"""
    
    def __init__(self, parent_gui):
        """Initialize the tag filter manager
        
        Args:
            parent_gui: Reference to the main GameLibraryGUI instance
        """
        self.parent_gui = parent_gui
        
        # UI components
        self.tag_frame: Optional[ttk.LabelFrame] = None
        self.tag_groups_container: Optional[ttk.Frame] = None
        self.custom_tag_frame: Optional[ttk.LabelFrame] = None
        self.custom_tag_entry: Optional[ttk.Entry] = None
        self.custom_tag_var: Optional[tk.StringVar] = None
        self.add_tag_button: Optional[ttk.Button] = None
        self.active_tags_frame: Optional[ttk.Frame] = None
        self.completion_frame: Optional[ttk.Frame] = None
        self.completion_listbox: Optional[tk.Listbox] = None
        self.clear_filters_button: Optional[ttk.Button] = None
        
        # Group frames
        self.language_group_frame: Optional[ttk.LabelFrame] = None
        self.country_group_frame: Optional[ttk.LabelFrame] = None
        self.other_group_frame: Optional[ttk.LabelFrame] = None
        
        # State tracking
        self.tag_buttons: Dict[str, ttk.Checkbutton] = {}
        self.tag_variables: Dict[str, tk.BooleanVar] = {}
        self.active_tag_filters: Set[str] = set()
        self.custom_tag_filters: Set[str] = set()
        self.active_tag_buttons: Dict[str, ttk.Frame] = {}
        self.available_other_tags: Set[str] = set()
        self.completion_visible: bool = False
        
        # Callbacks
        self.on_filters_changed: Optional[Callable] = None
    
    def setup_tag_filters(self, parent: ttk.Widget) -> None:
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
    
    def setup_custom_tag_input(self) -> None:
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
    
    def on_custom_tag_change(self, *_args) -> None:
        """Handle custom tag input change"""
        self.update_auto_completion()
    
    def on_tag_entry_keyrelease(self, event) -> None:
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
    
    def on_completion_select(self, event=None) -> None:
        """Handle selection from completion listbox"""
        self.select_completion()
    
    def navigate_completion(self, direction: str) -> None:
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
    
    def select_completion(self) -> None:
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
    
    def update_auto_completion(self) -> None:
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
    
    def show_completion(self, matches: List[str]) -> None:
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
    
    def hide_completion(self, event=None) -> None:
        """Hide auto-completion listbox"""
        if self.completion_visible:
            self.completion_frame.pack_forget()
            self.completion_visible = False
    
    def add_custom_tag(self) -> None:
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
            self._notify_filters_changed()
    
    def create_active_tag_button(self, tag: str) -> None:
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
    
    def remove_custom_tag(self, tag: str) -> None:
        """Remove custom tag from filters"""
        if tag in self.custom_tag_filters:
            self.custom_tag_filters.discard(tag)
            self.active_tag_filters.discard(tag)
            
            # Remove button
            if tag in self.active_tag_buttons:
                self.active_tag_buttons[tag].destroy()
                del self.active_tag_buttons[tag]
            
            self._notify_filters_changed()
    
    def clear_custom_tags(self) -> None:
        """Clear all custom tag filters"""
        self.custom_tag_filters.clear()
        self.custom_tag_var.set("")
        self.hide_completion()
        
        # Remove all active tag buttons
        for button_frame in self.active_tag_buttons.values():
            button_frame.destroy()
        self.active_tag_buttons.clear()
    
    def update_tag_buttons(self, platform: str, categorized_tags: Dict[str, Set[str]]) -> None:
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
        
        if not categorized_tags:
            return
        
        # Store available other tags for auto-completion
        self.available_other_tags = categorized_tags.get('other', set())
        
        # Create tag group frames
        current_column = 0
        
        # Configure grid column weights for horizontal distribution
        self.tag_groups_container.grid_columnconfigure(0, weight=1)
        self.tag_groups_container.grid_columnconfigure(1, weight=1)
        self.tag_groups_container.grid_columnconfigure(2, weight=1)
        
        # Language tags
        if categorized_tags.get('language'):
            self.language_group_frame = ttk.LabelFrame(self.tag_groups_container, text="Languages")
            self.language_group_frame.grid(row=0, column=current_column, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=2)
            self.create_tag_buttons(self.language_group_frame, categorized_tags['language'])
            current_column += 1
        
        # Country/Region tags
        if categorized_tags.get('country'):
            self.country_group_frame = ttk.LabelFrame(self.tag_groups_container, text="Regions")
            self.country_group_frame.grid(row=0, column=current_column, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=2)
            self.create_tag_buttons(self.country_group_frame, categorized_tags['country'])
            current_column += 1
        
        # Custom tag input (replaces Other group)
        if self.available_other_tags:
            self.custom_tag_frame.grid(row=0, column=current_column, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=2)
            # Update the label to show count
            tag_count = len(self.available_other_tags)
            self.custom_tag_frame.configure(text=f"Additional Tags ({tag_count} available - type to filter)")
    
    def create_tag_buttons(self, parent_frame: ttk.LabelFrame, tags: Set[str]) -> None:
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
    
    def on_tag_filter_change(self, tag: str) -> None:
        """Handle tag filter button toggle"""
        if self.tag_variables[tag].get():
            self.active_tag_filters.add(tag)
        else:
            self.active_tag_filters.discard(tag)
        
        self._notify_filters_changed()
    
    def clear_tag_filters(self) -> None:
        """Clear all active tag filters"""
        self.active_tag_filters.clear()
        
        # Clear all tag button states
        for var in self.tag_variables.values():
            var.set(False)
        
        # Clear custom tags
        self.clear_custom_tags()
        
        self._notify_filters_changed()
    
    def get_active_filters(self) -> Set[str]:
        """Get the currently active tag filters"""
        return self.active_tag_filters.copy()
    
    def set_filters_changed_callback(self, callback: Callable) -> None:
        """Set the callback to call when filters change"""
        self.on_filters_changed = callback
    
    def _notify_filters_changed(self) -> None:
        """Notify that filters have changed"""
        if self.on_filters_changed:
            self.on_filters_changed()