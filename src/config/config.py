"""
Configuration Management for ROM Downloader
Handles loading and managing platform configurations.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for ROM platforms and application settings."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. Defaults to config/platforms.json
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "platforms.json"
        
        self.config_path = config_path
        self.config_data = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from the JSON file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
            else:
                logger.warning(f"Configuration file not found: {self.config_path}")
                self.create_default_config()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.create_default_config()
    
    def create_default_config(self) -> None:
        """Create a default configuration file."""
        default_config = {
            "settings": {
                "network_drive_path": "//BATOCERA/share/roms",
                "temp_download_path": "./temp_downloads",
                "download_delay_min": 2,
                "download_delay_max": 5,
                "preferred_regions": ["USA", "US", "En", "English"],
                "max_concurrent_downloads": 1
            },
            "platforms": {
                "GameCube": {
                    "name": "Nintendo GameCube",
                    "url": "https://myrient.erista.me/files/Redump/Nintendo%20-%20GameCube%20-%20NKit%20RVZ%20[zstd-19-128k]/",
                    "target_folder": "gamecube",
                    "file_extensions": [".rvz", ".zip", ".7z"],
                    "file_pattern": r".*\.(rvz|zip|7z)$",
                    "extract_archives": true
                }
            }
        }
        
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save default config
        self.save_config(default_config)
        self.config_data = default_config
    
    def save_config(self, config_data: Optional[Dict] = None) -> None:
        """Save configuration to the JSON file.
        
        Args:
            config_data: Configuration data to save. Uses current data if None.
        """
        if config_data is not None:
            self.config_data = config_data
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def get_platforms(self) -> Dict[str, Dict]:
        """Get all configured platforms.
        
        Returns:
            Dictionary of platform configurations.
        """
        return self.config_data.get("platforms", {})
    
    def get_platform(self, platform_name: str) -> Optional[Dict]:
        """Get configuration for a specific platform.
        
        Args:
            platform_name: Name of the platform to get.
            
        Returns:
            Platform configuration or None if not found.
        """
        return self.config_data.get("platforms", {}).get(platform_name)
    
    def get_settings(self) -> Dict:
        """Get application settings.
        
        Returns:
            Dictionary of application settings.
        """
        return self.config_data.get("settings", {})
    
    def get_setting(self, setting_name: str, default=None):
        """Get a specific application setting.
        
        Args:
            setting_name: Name of the setting to get.
            default: Default value if setting not found.
            
        Returns:
            Setting value or default.
        """
        return self.config_data.get("settings", {}).get(setting_name, default)
    
    def get_network_drive_path(self) -> str:
        """Get the network drive path for ROM storage."""
        return self.get_setting("network_drive_path", "//BATOCERA/share/roms")
    
    def _is_wsl(self) -> bool:
        """Check if we're running inside WSL."""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower() or 'wsl' in f.read().lower()
        except:
            return False
    
    def _convert_unc_path_for_wsl(self, unc_path: str) -> Path:
        """Convert Windows UNC path to WSL-compatible path.
        
        Args:
            unc_path: Windows UNC path like //SERVER/share/path
            
        Returns:
            WSL-compatible path
        """
        if not self._is_wsl():
            return Path(unc_path)
        
        # Convert //SERVER/share/path to /mnt/SERVER format (mount point only)
        if unc_path.startswith('//') or unc_path.startswith('\\\\'):
            # Remove leading slashes and split
            clean_path = unc_path.replace('\\', '/').lstrip('/')
            parts = clean_path.split('/')
            if len(parts) >= 1:
                server = parts[0].lower()
                # Only use server name for mount point, ignore the share name since we mounted the share directly
                wsl_path = f"/mnt/{server}"
                # Add any additional path components after the share
                if len(parts) > 2:  # Skip server and share, take the rest
                    additional_path = '/'.join(parts[2:])
                    wsl_path = f"{wsl_path}/{additional_path}"
                logger.info(f"Converting UNC path {unc_path} to WSL path {wsl_path}")
                return Path(wsl_path)
        
        # Fallback to original path
        logger.warning(f"Could not convert UNC path {unc_path}, using as-is")
        return Path(unc_path)
    
    def get_target_path(self, platform_name: str) -> Optional[Path]:
        """Get the full target path for a platform.
        
        Args:
            platform_name: Name of the platform.
            
        Returns:
            Full path to the platform's ROM directory.
        """
        platform = self.get_platform(platform_name)
        if not platform:
            return None
        
        network_path = self.get_network_drive_path()
        target_folder = platform.get("target_folder", platform_name.lower())
        
        # Convert UNC path for WSL compatibility
        base_path = self._convert_unc_path_for_wsl(network_path)
        return base_path / target_folder
    
    def should_extract_archives(self, platform_name: str) -> bool:
        """Check if archives should be extracted for a platform.
        
        Args:
            platform_name: Name of the platform.
            
        Returns:
            True if archives should be extracted, False otherwise.
        """
        platform = self.get_platform(platform_name)
        if not platform:
            return False
        
        return platform.get("extract_archives", False)