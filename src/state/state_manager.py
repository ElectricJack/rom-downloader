"""
State Management for ROM Downloader
Handles persistence of user selections and application state.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent))
from utils.dirs import app_dirs

logger = logging.getLogger(__name__)

class StateManager:
    """Manages application state persistence."""
    
    def __init__(self, state_path: Optional[Path] = None):
        """Initialize the state manager.
        
        Args:
            state_path: Path to the state file. Uses OS app data dir if None.
        """
        if state_path is None:
            state_path = app_dirs.get_state_dir() / "app_state.json"
        
        self.state_path = state_path
        self.state_data = {}
        
        # Ensure state directory exists
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.load_state()
    
    def load_state(self) -> None:
        """Load application state from file."""
        try:
            if self.state_path.exists():
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    self.state_data = json.load(f)
                logger.info(f"Loaded application state from {self.state_path}")
            else:
                logger.info("No existing state file found, starting fresh")
                self.state_data = self._create_default_state()
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.state_data = self._create_default_state()
    
    def save_state(self) -> None:
        """Save current application state to file."""
        try:
            # Update timestamp
            self.state_data['last_updated'] = datetime.now().isoformat()
            
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(self.state_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved application state to {self.state_path}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _create_default_state(self) -> Dict:
        """Create default application state structure."""
        return {
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'platforms': {},
            'app_settings': {
                'last_selected_platform': '',
                'window_geometry': '800x600',
                'auto_save_selections': True
            }
        }
    
    def save_platform_selections(self, platform: str, selected_roms: Set[str]) -> None:
        """Save ROM selections for a specific platform.
        
        Args:
            platform: Platform name.
            selected_roms: Set of selected ROM names.
        """
        if 'platforms' not in self.state_data:
            self.state_data['platforms'] = {}
        
        self.state_data['platforms'][platform] = {
            'selected_roms': list(selected_roms),
            'last_updated': datetime.now().isoformat(),
            'selection_count': len(selected_roms)
        }
        
        self.save_state()
        logger.info(f"Saved {len(selected_roms)} ROM selections for platform: {platform}")
    
    def load_platform_selections(self, platform: str) -> Set[str]:
        """Load ROM selections for a specific platform.
        
        Args:
            platform: Platform name.
            
        Returns:
            Set of previously selected ROM names.
        """
        platform_data = self.state_data.get('platforms', {}).get(platform, {})
        selected_roms = set(platform_data.get('selected_roms', []))
        
        if selected_roms:
            logger.info(f"Loaded {len(selected_roms)} ROM selections for platform: {platform}")
        
        return selected_roms
    
    def clear_platform_selections(self, platform: str) -> None:
        """Clear ROM selections for a specific platform.
        
        Args:
            platform: Platform name.
        """
        if 'platforms' in self.state_data and platform in self.state_data['platforms']:
            del self.state_data['platforms'][platform]
            self.save_state()
            logger.info(f"Cleared ROM selections for platform: {platform}")
    
    def get_platform_info(self, platform: str) -> Dict:
        """Get information about a platform's saved state.
        
        Args:
            platform: Platform name.
            
        Returns:
            Dictionary with platform information.
        """
        return self.state_data.get('platforms', {}).get(platform, {})
    
    def get_all_platforms(self) -> List[str]:
        """Get list of all platforms with saved state.
        
        Returns:
            List of platform names.
        """
        return list(self.state_data.get('platforms', {}).keys())
    
    def set_app_setting(self, key: str, value) -> None:
        """Set an application setting.
        
        Args:
            key: Setting key.
            value: Setting value.
        """
        if 'app_settings' not in self.state_data:
            self.state_data['app_settings'] = {}
        
        self.state_data['app_settings'][key] = value
        self.save_state()
    
    def get_app_setting(self, key: str, default=None):
        """Get an application setting.
        
        Args:
            key: Setting key.
            default: Default value if setting not found.
            
        Returns:
            Setting value or default.
        """
        return self.state_data.get('app_settings', {}).get(key, default)
    
    def set_last_selected_platform(self, platform: str) -> None:
        """Save the last selected platform.
        
        Args:
            platform: Platform name.
        """
        self.set_app_setting('last_selected_platform', platform)
    
    def get_last_selected_platform(self) -> str:
        """Get the last selected platform.
        
        Returns:
            Last selected platform name or empty string.
        """
        return self.get_app_setting('last_selected_platform', '')
    
    def save_window_geometry(self, geometry: str) -> None:
        """Save window geometry.
        
        Args:
            geometry: Window geometry string (e.g., '800x600+100+100').
        """
        self.set_app_setting('window_geometry', geometry)
    
    def get_window_geometry(self) -> str:
        """Get saved window geometry.
        
        Returns:
            Window geometry string.
        """
        return self.get_app_setting('window_geometry', '800x600')
    
    def add_download_history(self, platform: str, rom_name: str, success: bool, 
                           download_time: Optional[str] = None) -> None:
        """Add an entry to download history.
        
        Args:
            platform: Platform name.
            rom_name: ROM name.
            success: Whether download was successful.
            download_time: Download timestamp (defaults to now).
        """
        if download_time is None:
            download_time = datetime.now().isoformat()
        
        if 'download_history' not in self.state_data:
            self.state_data['download_history'] = []
        
        history_entry = {
            'platform': platform,
            'rom_name': rom_name,
            'success': success,
            'timestamp': download_time
        }
        
        self.state_data['download_history'].append(history_entry)
        
        # Keep only last 1000 entries
        if len(self.state_data['download_history']) > 1000:
            self.state_data['download_history'] = self.state_data['download_history'][-1000:]
        
        self.save_state()
    
    def get_download_history(self, platform: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get download history.
        
        Args:
            platform: Platform to filter by (optional).
            limit: Maximum number of entries to return.
            
        Returns:
            List of download history entries.
        """
        history = self.state_data.get('download_history', [])
        
        if platform:
            history = [entry for entry in history if entry.get('platform') == platform]
        
        # Return most recent entries first
        return list(reversed(history[-limit:]))
    
    def get_download_stats(self, platform: Optional[str] = None) -> Dict:
        """Get download statistics.
        
        Args:
            platform: Platform to get stats for (optional).
            
        Returns:
            Dictionary with download statistics.
        """
        history = self.get_download_history(platform, limit=10000)  # Get more for stats
        
        total_downloads = len(history)
        successful_downloads = len([h for h in history if h.get('success', False)])
        failed_downloads = total_downloads - successful_downloads
        
        return {
            'total_downloads': total_downloads,
            'successful_downloads': successful_downloads,
            'failed_downloads': failed_downloads,
            'success_rate': (successful_downloads / total_downloads * 100) if total_downloads > 0 else 0
        }