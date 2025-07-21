"""
Installation Status Manager for tracking ROM installation status.

This module provides the InstallationStatusManager class which handles:
- Checking if ROMs are installed on target drives
- Caching installation status for performance
- Asynchronous installation status updates
- Tree view installation status synchronization
"""

import logging
import threading
import time
from pathlib import Path
from typing import Dict, Set, List, Optional, Callable

from src.models.game_library import Game, ROM
from src.scraper.web_scraper import RomInfo
from src.rom_manager.rom_filter import RomFilter

logger = logging.getLogger(__name__)


class InstallationStatusManager:
    """
    Manages ROM installation status checking and caching.
    
    This class handles the complex logic of determining whether ROMs are installed,
    caching results for performance, and updating the UI asynchronously.
    """
    
    def __init__(self, gui):
        """
        Initialize the Installation Status Manager.
        
        Args:
            gui: The GameLibraryGUI instance that owns this manager
        """
        self.gui = gui
        self.existing_roms: Set[str] = set()
        self._async_update_cancelled = False
        # New: Efficient filename lookup maps
        self._normalized_to_actual: Dict[str, str] = {}  # normalized_name -> actual_filename
        self._actual_files_cache: Dict[str, str] = {}    # actual_filename.lower() -> actual_filename
        
    @property
    def config_manager(self):
        """Access to config manager through GUI."""
        return self.gui.config_manager
    
    @property
    def rom_filter(self) -> RomFilter:
        """Access to ROM filter through GUI."""
        return self.gui.rom_filter
    
    @property
    def current_games(self) -> List[Game]:
        """Access to current games through GUI."""
        return self.gui.current_games
    
    @property
    def game_tree(self):
        """Access to game tree through GUI."""
        return self.gui.game_tree
    
    @property
    def _gui_active(self) -> bool:
        """Check if GUI is still active."""
        return self.gui._gui_active
    
    def is_rom_installed(self, rom: ROM, platform: str) -> bool:
        """
        Check if a ROM is installed on the target drive.
        
        Args:
            rom: The ROM object to check
            platform: The platform name
            
        Returns:
            True if ROM is installed, False otherwise
        """
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
            result, installed_filename = self._precise_rom_match_with_filename(rom.filename, self.existing_roms, target_dir)
            
            # Cache the result and actual filename for future use
            rom.set_installed(result, installed_filename)
            return result
        
        # Fallback to direct checking if cache is empty
        # Create a RomInfo object from ROM for compatibility with RomFilter
        rom_info = RomInfo(
            name=rom.filename,
            url=rom.url,
            size=rom.size
        )
        
        result = self.rom_filter.is_rom_installed(rom_info, target_dir)
        
        # Cache the result for future use (no filename for fallback method)
        rom.set_installed(result, "unknown" if result else None)
        return result
    
    def _precise_rom_match_with_filename(self, rom_filename: str, existing_roms: set, target_dir: Path) -> tuple[bool, Optional[str]]:
        """
        Perform precise ROM matching and return both result and actual installed filename.
        Uses cached filename lookup for O(1) performance instead of directory scanning.
        
        Args:
            rom_filename: The ROM filename to check (e.g., "007 - Everything or Nothing (Japan).zip")
            existing_roms: Set of existing ROM stems (case-insensitive, no extensions)
            target_dir: Target directory (used for cache validation)
        
        Returns:
            Tuple of (is_found: bool, installed_filename: Optional[str])
        """
        # Get the stem (filename without extension)
        stem = rom_filename
        if '.' in stem:
            stem = '.'.join(stem.split('.')[:-1])
        
        # Try different matching strategies using cached lookups
        candidates = [
            stem.lower().strip(),  # Strategy 1: Exact match
            self.rom_filter._normalize_name(stem)  # Strategy 2: Normalized match
        ]
        
        for candidate in candidates:
            if candidate in existing_roms:
                # Use cached lookup instead of directory scanning
                actual_filename = self._normalized_to_actual.get(candidate)
                if actual_filename:
                    return True, actual_filename
        
        # Strategy 3: Check for same ROM different format
        normalized_name = self.rom_filter._normalize_name(stem)
        for existing_rom in existing_roms:
            if self._are_same_rom_different_format(normalized_name, existing_rom):
                actual_filename = self._normalized_to_actual.get(existing_rom)
                if actual_filename:
                    return True, actual_filename
        
        return False, None
    
    def _build_filename_cache(self, target_dir: Path):
        """Build efficient lookup maps by scanning directory once"""
        self._normalized_to_actual.clear()
        self._actual_files_cache.clear()
        
        try:
            rom_extensions = {'.rvz', '.zip', '.7z', '.iso', '.gcm', '.bin', '.cue', '.chd', 
                             '.n64', '.z64', '.v64', '.nes', '.sfc', '.smc', '.gba', '.gbc', '.gb', 
                             '.nds', '.vb', '.pce', '.a26', '.a52', '.a78', '.cdi', '.gdi', '.wux', '.wud'}
            
            logger.info(f"Building filename cache from {target_dir}")
            file_count = 0
            
            # Single directory scan to build all lookup maps
            for file_path in target_dir.iterdir():
                if file_path.is_file() and any(file_path.name.lower().endswith(ext) for ext in rom_extensions):
                    file_count += 1
                    actual_filename = file_path.name
                    file_stem = file_path.stem
                    
                    # Build normalized name lookup
                    file_normalized = self.rom_filter._normalize_name(file_stem)
                    self._normalized_to_actual[file_normalized] = actual_filename
                    
                    # Also add case-insensitive direct lookup
                    self._actual_files_cache[actual_filename.lower()] = actual_filename
                        
            logger.info(f"Built filename cache: {file_count} ROM files found")
                        
        except Exception as e:
            logger.error(f"Error building filename cache: {e}")
            self._normalized_to_actual.clear()
            self._actual_files_cache.clear()
    
    def _precise_rom_match(self, rom_filename: str, existing_roms: set) -> bool:
        """
        Perform precise ROM matching using multiple strategies to avoid false positives.
        This is a wrapper around _precise_rom_match_with_filename for backward compatibility.
        
        Args:
            rom_filename: The ROM filename to check (e.g., "007 - Everything or Nothing (Japan).zip")
            existing_roms: Set of existing ROM stems (case-insensitive, no extensions)
        
        Returns:
            True if the ROM is found, False otherwise
        """
        # For backward compatibility, delegate to the new method but ignore the filename
        # This is used in tests where target_dir is not available
        result, _ = self._precise_rom_match_with_filename(rom_filename, existing_roms, Path("."))
        return result
    
    def _are_same_rom_different_format(self, rom1: str, rom2: str) -> bool:
        """
        Check if two ROM names represent the same game but in different formats.
        This is a very conservative check to avoid false positives.
        
        Args:
            rom1: First ROM name
            rom2: Second ROM name
            
        Returns:
            True if they represent the same ROM in different formats
        """
        # Only consider them the same if they're very similar
        # This is intentionally strict to avoid false matches
        return rom1 == rom2
    
    def check_installed_roms(self):
        """Scan target directory for installed ROMs and refresh display."""
        from tkinter import messagebox
        
        platform = self.gui.get_current_platform_key()
        if not platform:
            messagebox.showwarning("Warning", "Please select a platform first")
            return

        target_dir = self.config_manager.get_target_directory(platform)
        if not target_dir:
            messagebox.showwarning("Warning", f"No target directory configured for platform: {platform}")
            return

        self.gui.update_status("Scanning for installed ROMs...")
        self.gui.progress_bar.configure(mode='indeterminate')
        self.gui.progress_bar.start()

        # Run scan in a separate thread
        thread = threading.Thread(target=self._check_installed_thread, args=(platform, target_dir))
        thread.daemon = True
        thread.start()
    
    def _check_installed_thread(self, platform: str, target_dir: Path):
        """Check installed ROMs in a separate thread."""
        try:
            # Check if GUI is still active
            if not self._gui_active:
                return
                
            # Scan existing ROMs
            self.existing_roms = self.rom_filter.scan_existing_roms(target_dir)
            
            # Update UI (if GUI still active)
            self.gui._safe_gui_update(lambda: self._check_installed_complete(len(self.existing_roms)))
            
        except Exception as e:
            logger.error(f"Error checking installed ROMs: {e}")
            self.gui._safe_gui_update(lambda: self.gui.update_status(f"Error: {e}"))
        finally:
            self.gui._safe_gui_update(lambda: self.gui.progress_bar.stop())
            self.gui._safe_gui_update(lambda: self.gui.progress_bar.configure(mode='determinate'))

    def _async_populate_rom_cache(self, platform: str, target_dir: Path):
        """Populate ROM cache asynchronously without blocking the UI."""
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
                self.gui._safe_gui_update(lambda: self.gui.update_status("Checking for installed ROMs..."))
                logger.info("Starting ROM cache population...")
                
                # Build filename lookup cache first (single directory scan)
                self._build_filename_cache(target_dir)
                
                # Scan existing ROMs (this should now be much faster)
                existing_roms = self.rom_filter.scan_existing_roms(target_dir)
                
                # Update cache and UI on main thread (if GUI still active)
                self.gui._safe_gui_update(lambda: self._update_rom_cache(existing_roms, platform))
                
            else:
                logger.warning(f"Target directory does not exist: {target_dir}")
                self.gui._safe_gui_update(lambda: self.gui.update_status("Ready"))
                
        except Exception as e:
            logger.error(f"Failed to scan existing ROMs: {e}", exc_info=True)
            self.gui._safe_gui_update(lambda: self.gui.update_status("Ready"))

    def _update_rom_cache(self, existing_roms: set, platform: str):
        """Update ROM cache and refresh display (called on main thread)."""
        self.existing_roms = existing_roms
        logger.info(f"Updated ROM cache: {len(self.existing_roms)} ROMs found")
        
        # Log first few entries for debugging
        if self.existing_roms:
            sample_roms = list(self.existing_roms)[:5]
            logger.info(f"Sample cached ROM names: {sample_roms}")
        
        # Bulk update installation cache for all games/ROMs
        self._bulk_update_installation_cache(platform)
        
        # Schedule fast tree visual update using cached data
        thread = threading.Thread(target=self._async_update_tree_from_cache)
        thread.daemon = True
        thread.start()
        self.gui.update_status("Ready")
    
    def _bulk_update_installation_cache(self, platform: str):
        """Bulk update installation cache for all games using directory scan results."""
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
                
                # Use the new precise matching logic with filename detection
                target_dir = self.config_manager.get_target_directory(platform)
                is_installed, installed_filename = self._precise_rom_match_with_filename(rom.filename, self.existing_roms, target_dir)
                
                # Cache the result and actual filename
                rom.set_installed(is_installed, installed_filename)
                if is_installed:
                    cached_roms += 1
        
        logger.info(f"Cached installation status for {total_roms} ROMs, {cached_roms} installed")
        
        # Mark platform as dirty so installation status gets saved to state file
        if hasattr(self.gui, 'state_manager') and self.gui.state_manager:
            self.gui.state_manager.platform_dirty = True
            logger.debug("Marked platform as dirty for state persistence")
    
    def _async_update_tree_from_cache(self):
        """Fast tree update using cached installation data."""
        try:
            if not self._gui_active or not self.current_games or self._async_update_cancelled:
                return
            
            platform = self.gui.get_current_platform_key()
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
                    self.gui._safe_gui_update(lambda: self._apply_tree_updates(updates))
                
                processed += len(chunk)
                
                # Smaller delay since we're using cached data
                time.sleep(0.005)  # 5ms vs 10ms
            
            logger.info(f"Completed cached tree installation status update for {processed} items")
            
        except Exception as e:
            logger.error(f"Error in cached tree installation status update: {e}")
    
    def _prepare_cached_game_update(self, item_id: str, game, platform: str):
        """Prepare game update using cached installation data."""
        try:
            if not self.game_tree.exists(item_id):
                return None
                
            # Only check installation status for filtered variants (same logic as tree building)
            variants = game.get_variants_for_platform(platform)
            filtered_variants = [rom for rom in variants if self.gui.rom_matches_tags(rom)]
            
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
        """Prepare variant update using cached installation data."""
        try:
            if not self.game_tree.exists(item_id):
                return None
                
            variant_key = self.game_tree.set(item_id, 'variant_key')
            if not variant_key:
                return None
            
            # Only look through filtered variants (same as tree building logic)
            variants = game.get_variants_for_platform(platform)
            filtered_variants = [rom for rom in variants if self.gui.rom_matches_tags(rom)]
            
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
        """Update tree installation status asynchronously in chunks."""
        try:
            if not self._gui_active or not self.current_games or self._async_update_cancelled:
                return
            
            platform = self.gui.get_current_platform_key()
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
                    self.gui._safe_gui_update(lambda: self._apply_tree_updates(updates))
                
                processed += len(chunk)
                
                # Small delay between chunks to keep GUI responsive
                time.sleep(0.01)
            
            logger.info(f"Completed async tree installation status update for {processed} items")
            
        except Exception as e:
            logger.error(f"Error in async tree installation status update: {e}")
    
    def _prepare_game_installation_update(self, item_id: str, game, platform: str):
        """Prepare installation status update data for a game item."""
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
        """Prepare installation status update data for a variant item."""
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
        """Apply a batch of tree updates on the main thread."""
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
        """Update installation status of existing tree items without full refresh."""
        if not self.current_games:
            return
        
        platform = self.gui.get_current_platform_key()
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
        """Update installation status for a game item."""
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
        """Update installation status for a variant item."""
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
        """Handle installed ROM check completion."""
        self.gui.update_status(f"Found {count} installed ROMs")
        self.gui.refresh_game_list()
    
    def clear_existing_roms_cache(self):
        """Clear the existing ROMs cache and filename lookup maps."""
        self.existing_roms.clear()
        self._normalized_to_actual.clear()
        self._actual_files_cache.clear()
    
    def cancel_async_updates(self):
        """Cancel any ongoing async update operations."""
        self._async_update_cancelled = True
    
    def start_background_checking(self, platform: str):
        """Start background installation status checking for the given platform."""
        target_dir = self.config_manager.get_target_directory(platform)
        if target_dir:
            thread = threading.Thread(target=self._async_populate_rom_cache, args=(platform, target_dir))
            thread.daemon = True
            thread.start()