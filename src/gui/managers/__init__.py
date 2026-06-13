"""
GUI Managers Package

Contains manager classes that handle specific functionality extracted from 
the main GameLibraryGUI class for better separation of concerns.
"""

from .tag_filter_manager import TagFilterManager
from .queue_manager import QueueManager
from .game_tree_manager import GameTreeManager
from .installation_status_manager import InstallationStatusManager

__all__ = ['TagFilterManager', 'QueueManager', 'GameTreeManager', 'InstallationStatusManager']