"""
Base classes for the tool pipeline system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of running a tool step"""
    success: bool
    output_files: List[Path] = field(default_factory=list)
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolStep:
    """Represents a single step in the tool pipeline"""
    tool_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)


class ToolHandler(ABC):
    """Abstract base class for all tool handlers"""
    
    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Unique identifier for this tool"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does"""
        pass
    
    @property
    @abstractmethod
    def supported_file_types(self) -> List[str]:
        """List of file extensions this tool can process"""
        pass
    
    @abstractmethod
    def can_process(self, input_files: List[Path], parameters: Dict[str, Any]) -> bool:
        """Check if this tool can process the given files"""
        pass
    
    @abstractmethod
    def process(self, input_files: List[Path], output_dir: Path, 
                parameters: Dict[str, Any]) -> ProcessingResult:
        """Process the input files and return results"""
        pass
    
    @abstractmethod
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameters for this tool"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate that parameters are acceptable for this tool"""
        # Default implementation - can be overridden by specific tools
        return True