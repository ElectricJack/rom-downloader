"""
GUI Managers Package

Contains manager classes that handle specific functionality extracted from 
the main GameLibraryGUI class for better separation of concerns.
"""

from .tag_filter_manager import TagFilterManager

__all__ = ['TagFilterManager']