"""
Enhanced configuration manager with tool pipeline support.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.tools.base import ToolStep
from src.utils.dirs import app_dirs
from src.utils.rom_utils import get_rom_utils

logger = logging.getLogger(__name__)


class EnhancedConfigManager:
    """Enhanced configuration manager with tool pipeline support"""
    
    def __init__(self, config_file: Path = None):
        self.config_file = config_file or app_dirs.get_config_dir() / 'platforms.json'
        self.config_data = {}
        self.rom_utils = get_rom_utils()
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from file"""
        try:
            if not self.config_file.exists():
                logger.error(f"Configuration file not found: {self.config_file}")
                return False
            
            with open(self.config_file, 'r') as f:
                self.config_data = json.load(f)
            
            # Validate configuration structure
            if not self._validate_config():
                logger.error("Invalid configuration structure")
                return False
            
            logger.info(f"Loaded configuration from {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
    
    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config_data, f, indent=2)
            
            logger.info(f"Saved configuration to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def reload_config(self) -> bool:
        """Reload configuration from file"""
        logger.info("Reloading configuration")
        return self.load_config()
    
    def _validate_config(self) -> bool:
        """Validate configuration structure"""
        if not isinstance(self.config_data, dict):
            return False
        
        # Check required sections
        if 'settings' not in self.config_data:
            return False
        
        if 'platforms' not in self.config_data:
            return False
        
        # Validate platforms
        platforms = self.config_data['platforms']
        if not isinstance(platforms, dict):
            return False
        
        for platform_id, platform_config in platforms.items():
            if not self._validate_platform_config(platform_config):
                logger.error(f"Invalid configuration for platform: {platform_id}")
                return False
        
        return True
    
    def _validate_platform_config(self, platform_config: Dict[str, Any]) -> bool:
        """Validate a single platform configuration"""
        required_fields = ['name', 'url', 'target_folder', 'file_extensions']
        
        for field in required_fields:
            if field not in platform_config:
                return False
        
        # Validate tool pipeline if present
        if 'tool_pipeline' in platform_config:
            pipeline = platform_config['tool_pipeline']
            if not isinstance(pipeline, list):
                return False
            
            for step in pipeline:
                if not self._validate_tool_step(step):
                    return False
        
        return True
    
    def _validate_tool_step(self, step: Dict[str, Any]) -> bool:
        """Validate a tool pipeline step"""
        if 'tool_id' not in step:
            return False
        
        if 'parameters' in step and not isinstance(step['parameters'], dict):
            return False
        
        if 'conditions' in step and not isinstance(step['conditions'], dict):
            return False
        
        return True
    
    def get_settings(self) -> Dict[str, Any]:
        """Get global settings"""
        return self.config_data.get('settings', {})
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting"""
        return self.get_settings().get(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Set a global setting"""
        if 'settings' not in self.config_data:
            self.config_data['settings'] = {}
        
        self.config_data['settings'][key] = value
    
    def get_platforms(self) -> Dict[str, Dict[str, Any]]:
        """Get all platform configurations"""
        return self.config_data.get('platforms', {})
    
    def get_platform_config(self, platform_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific platform"""
        return self.get_platforms().get(platform_id)
    
    def get_platform_names(self) -> List[str]:
        """Get list of all platform IDs"""
        return list(self.get_platforms().keys())
    
    def get_network_drive_paths(self) -> List[str]:
        """Get list of configured network drive paths"""
        settings = self.get_settings()
        
        # Handle legacy config format
        if 'network_drive_path' in settings and 'network_drive_paths' not in settings:
            # Migrate from old format
            legacy_path = settings['network_drive_path']
            paths = [legacy_path] if legacy_path else ["//BATOCERA/share/roms"]
            self.set_setting('network_drive_paths', paths)
            self.set_setting('current_network_drive_path', paths[0])
            # Remove legacy setting
            if 'network_drive_path' in settings:
                del settings['network_drive_path']
            if 'target_directory' in settings:
                del settings['target_directory']
            self.save_config()
            return paths
        
        return settings.get('network_drive_paths', ["//BATOCERA/share/roms"])
    
    def get_current_network_drive_path(self) -> str:
        """Get the currently selected network drive path"""
        settings = self.get_settings()
        current = settings.get('current_network_drive_path')
        
        # Ensure current path is in the list of available paths
        available_paths = self.get_network_drive_paths()
        if not current or current not in available_paths:
            if available_paths:
                current = available_paths[0]
                self.set_setting('current_network_drive_path', current)
                self.save_config()
            else:
                current = "//BATOCERA/share/roms"
        
        return current
    
    def set_current_network_drive_path(self, path: str):
        """Set the current network drive path"""
        available_paths = self.get_network_drive_paths()
        if path not in available_paths:
            raise ValueError(f"Path '{path}' not in configured network drive paths")
        
        self.set_setting('current_network_drive_path', path)
    
    def add_network_drive_path(self, path: str):
        """Add a new network drive path"""
        paths = self.get_network_drive_paths()
        if path not in paths:
            paths.append(path)
            self.set_setting('network_drive_paths', paths)
            
            # If this is the first path, make it current
            if len(paths) == 1:
                self.set_setting('current_network_drive_path', path)
    
    def remove_network_drive_path(self, path: str):
        """Remove a network drive path"""
        paths = self.get_network_drive_paths()
        if path in paths:
            paths.remove(path)
            
            # Ensure we have at least one path
            if not paths:
                paths = ["//BATOCERA/share/roms"]
            
            self.set_setting('network_drive_paths', paths)
            
            # Update current path if needed
            current = self.get_setting('current_network_drive_path')
            if current == path or current not in paths:
                self.set_setting('current_network_drive_path', paths[0])
    
    def get_platform_display_names(self) -> Dict[str, str]:
        """Get mapping of platform IDs to display names"""
        platforms = self.get_platforms()
        return {
            platform_id: config.get('name', platform_id)
            for platform_id, config in platforms.items()
        }
    
    def get_platform_tool_pipeline(self, platform_id: str) -> List[ToolStep]:
        """Get tool pipeline for a platform"""
        platform_config = self.get_platform_config(platform_id)
        if not platform_config:
            return []
        
        pipeline_config = platform_config.get('tool_pipeline', [])
        
        # Handle legacy extract_archives setting if no explicit tool_pipeline
        if not pipeline_config and platform_config.get('extract_archives', False):
            # Create default extraction pipeline for legacy configurations
            pipeline_config = [
                {
                    'tool_id': 'zip_extractor',
                    'parameters': {'remove_original': True},
                    'conditions': {'file_types': ['.zip']}
                },
                {
                    'tool_id': 'zip_extractor', 
                    'parameters': {'remove_original': True},
                    'conditions': {'file_types': ['.7z']}
                }
            ]
        
        # Convert to ToolStep objects
        pipeline = []
        for step_config in pipeline_config:
            step = ToolStep(
                tool_id=step_config['tool_id'],
                parameters=step_config.get('parameters', {}),
                conditions=step_config.get('conditions', {})
            )
            pipeline.append(step)
        
        return pipeline
    
    def set_platform_tool_pipeline(self, platform_id: str, pipeline: List[ToolStep]):
        """Set tool pipeline for a platform"""
        platform_config = self.get_platform_config(platform_id)
        if not platform_config:
            raise ValueError(f"Platform not found: {platform_id}")
        
        # Convert ToolStep objects to dictionaries
        pipeline_config = []
        for step in pipeline:
            step_config = {
                'tool_id': step.tool_id,
                'parameters': step.parameters,
                'conditions': step.conditions
            }
            pipeline_config.append(step_config)
        
        platform_config['tool_pipeline'] = pipeline_config
    
    def add_platform(self, platform_id: str, config: Dict[str, Any]):
        """Add a new platform configuration"""
        if not self._validate_platform_config(config):
            raise ValueError(f"Invalid platform configuration: {platform_id}")
        
        if 'platforms' not in self.config_data:
            self.config_data['platforms'] = {}
        
        self.config_data['platforms'][platform_id] = config
    
    def remove_platform(self, platform_id: str) -> bool:
        """Remove a platform configuration"""
        if platform_id in self.config_data.get('platforms', {}):
            del self.config_data['platforms'][platform_id]
            return True
        return False
    
    def get_target_directory(self, platform_id: str) -> Optional[Path]:
        """Get target directory for a platform (current network drive + platform folder)"""
        platform_config = self.get_platform_config(platform_id)
        if not platform_config:
            return Path(self.get_current_network_drive_path())
        
        target_folder = platform_config.get('target_folder', platform_id.lower())
        current_drive = self.get_current_network_drive_path()
        
        # Combine current network drive with platform folder
        return Path(current_drive) / target_folder
    
    def get_temp_directory(self) -> Path:
        """Get temporary download directory"""
        # Temp path is now handled by OS-appropriate directory utilities
        return app_dirs.get_temp_dir()
    
    def get_preferred_regions(self) -> List[str]:
        """Get preferred regions list"""
        return self.get_setting('preferred_regions', ['USA', 'US', 'En', 'English'])
    
    def get_max_concurrent_downloads(self) -> int:
        """Get maximum concurrent downloads"""
        return self.get_setting('max_concurrent_downloads', 1)
    
    def get_download_delay_range(self) -> tuple:
        """Get download delay range (min, max)"""
        min_delay = self.get_setting('download_delay_min', 2)
        max_delay = self.get_setting('download_delay_max', 5)
        return (min_delay, max_delay)
    
    def should_extract_archives(self, platform_id: str) -> bool:
        """Check if archives should be extracted for a platform"""
        platform_config = self.get_platform_config(platform_id)
        if not platform_config:
            return False
        
        return platform_config.get('extract_archives', True)
    
    def get_file_pattern(self, platform_id: str) -> Optional[str]:
        """Get file pattern for a platform (generated from file extensions)"""
        return self.rom_utils.generate_file_pattern_for_platform(platform_id)
    
    def get_supported_file_extensions(self, platform_id: str) -> List[str]:
        """Get supported file extensions for a platform"""
        platform_config = self.get_platform_config(platform_id)
        if not platform_config:
            return []
        
        return platform_config.get('file_extensions', [])
    
    def create_default_config(self) -> Dict[str, Any]:
        """Create a default configuration structure"""
        return {
            "settings": {
                "target_directory": "./local_roms",
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
                    "extract_archives": True,
                    "tool_pipeline": [
                        {
                            "tool_id": "zip_extractor",
                            "parameters": {
                                "remove_original": True
                            },
                            "conditions": {
                                "file_types": [".zip"]
                            }
                        },
                        {
                            "tool_id": "chd_converter",
                            "parameters": {
                                "chdman_path": "tools/chdman.exe",
                                "remove_original": True
                            },
                            "conditions": {
                                "file_types": [".iso", ".bin", ".cue"]
                            }
                        }
                    ]
                },
                "Xbox": {
                    "name": "Microsoft Xbox",
                    "url": "https://myrient.erista.me/files/Redump/Microsoft%20-%20Xbox/",
                    "target_folder": "xbox",
                    "file_extensions": [".xiso", ".iso", ".zip", ".7z"],
                    "extract_archives": True,
                    "tool_pipeline": [
                        {
                            "tool_id": "zip_extractor",
                            "parameters": {
                                "remove_original": True
                            },
                            "conditions": {
                                "file_types": [".zip"]
                            }
                        },
                        {
                            "tool_id": "xbox_extractor",
                            "parameters": {
                                "extract_xiso_path": "tools/extract-xiso.exe",
                                "remove_original": True,
                                "platform": "xbox"
                            },
                            "conditions": {
                                "file_types": [".iso"],
                                "platform": "xbox"
                            }
                        }
                    ]
                }
            }
        }
    
    def initialize_default_config(self) -> bool:
        """Initialize with default configuration and save to file"""
        try:
            self.config_data = self.create_default_config()
            return self.save_config()
        except Exception as e:
            logger.error(f"Failed to initialize default config: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration"""
        platforms = self.get_platforms()
        
        summary = {
            'config_file': str(self.config_file),
            'platforms_count': len(platforms),
            'platforms': list(platforms.keys()),
            'settings': self.get_settings()
        }
        
        # Add tool pipeline summary for each platform
        pipeline_summary = {}
        for platform_id in platforms:
            pipeline = self.get_platform_tool_pipeline(platform_id)
            pipeline_summary[platform_id] = [step.tool_id for step in pipeline]
        
        summary['tool_pipelines'] = pipeline_summary
        
        return summary