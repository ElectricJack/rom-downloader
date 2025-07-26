"""
Directory Management Utilities
Provides OS-appropriate directory paths for temporary files and application data.
"""

import os
import tempfile
import shutil
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class AppDirectories:
    """Manages OS-appropriate directories for the ROM downloader application."""
    
    APP_NAME = "rom-downloader"
    
    def __init__(self):
        """Initialize directory manager."""
        self._temp_dir = None
        self._app_data_dir = None
        self._config_copied = False
    
    def get_temp_dir(self) -> Path:
        """Get OS-appropriate temporary directory for downloads.
        
        Returns:
            Path to temporary downloads directory.
        """
        if self._temp_dir is None:
            # Create a temporary directory that will persist for the session
            temp_base = tempfile.gettempdir()
            self._temp_dir = Path(temp_base) / f"{self.APP_NAME}-temp"
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using temporary directory: {self._temp_dir}")
        
        return self._temp_dir
    
    def get_app_data_dir(self) -> Path:
        """Get OS-appropriate application data directory.
        
        Returns:
            Path to application data directory.
        """
        if self._app_data_dir is None:
            if os.name == 'nt':  # Windows
                app_data = os.environ.get('APPDATA')
                if app_data:
                    self._app_data_dir = Path(app_data) / self.APP_NAME
                else:
                    # Fallback to user home
                    self._app_data_dir = Path.home() / f".{self.APP_NAME}"
            else:  # Unix/Linux/macOS
                # Try XDG_DATA_HOME first, then fallback to ~/.local/share
                xdg_data_home = os.environ.get('XDG_DATA_HOME')
                if xdg_data_home:
                    self._app_data_dir = Path(xdg_data_home) / self.APP_NAME
                else:
                    self._app_data_dir = Path.home() / ".local" / "share" / self.APP_NAME
            
            # Ensure directory exists
            self._app_data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using app data directory: {self._app_data_dir}")
            
            # Copy default config if this is first run
            self._ensure_config_exists()
        
        return self._app_data_dir
    
    def get_state_dir(self) -> Path:
        """Get directory for application state files.
        
        Returns:
            Path to state directory.
        """
        return self.get_app_data_dir() / "state"
    
    def get_config_dir(self) -> Path:
        """Get directory for configuration files.
        
        Returns:
            Path to config directory.
        """
        return self.get_app_data_dir() / "config"
    
    def _ensure_config_exists(self) -> None:
        """Ensure default configuration exists in app data directory."""
        if self._config_copied:
            return
        
        config_dir = self.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if config already exists
        target_config = config_dir / "platforms.json"
        if target_config.exists():
            self._config_copied = True
            return
        
        # Try to copy from project config directory
        project_root = Path(__file__).parent.parent.parent
        source_config = project_root / "config" / "platforms.json"
        
        if source_config.exists():
            try:
                shutil.copy2(source_config, target_config)
                logger.info(f"Copied default config from {source_config} to {target_config}")
            except Exception as e:
                logger.error(f"Failed to copy config file: {e}")
                # Create a minimal default config
                self._create_minimal_config(target_config)
        else:
            logger.warning(f"Source config not found at {source_config}, creating minimal config")
            self._create_minimal_config(target_config)
        
        self._config_copied = True
    
    def _create_minimal_config(self, config_path: Path) -> None:
        """Create a minimal default configuration file.
        
        Args:
            config_path: Path where to create the config file.
        """
        minimal_config = {
            "settings": {
                "network_drive_path": "//BATOCERA/share/roms",
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
                    "extract_archives": True
                }
            }
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(minimal_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Created minimal config at {config_path}")
        except Exception as e:
            logger.error(f"Failed to create minimal config: {e}")
    
    def cleanup_temp_dir(self) -> None:
        """Clean up temporary directory."""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                logger.info(f"Cleaned up temporary directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory: {e}")
            finally:
                self._temp_dir = None

# Global instance
app_dirs = AppDirectories()