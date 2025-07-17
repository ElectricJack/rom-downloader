"""
ZIP archive extraction tool.
"""

import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Any

from tools.base import ToolHandler, ProcessingResult

logger = logging.getLogger(__name__)


class ZipExtractorTool(ToolHandler):
    """Tool for extracting ZIP archives"""
    
    @property
    def tool_id(self) -> str:
        return "zip_extractor"
    
    @property
    def description(self) -> str:
        return "Extract ZIP archives"
    
    @property
    def supported_file_types(self) -> List[str]:
        return ['.zip']
    
    def can_process(self, input_files: List[Path], parameters: Dict[str, Any]) -> bool:
        return any(f.suffix.lower() == '.zip' for f in input_files if f.exists())
    
    def process(self, input_files: List[Path], output_dir: Path, 
                parameters: Dict[str, Any]) -> ProcessingResult:
        output_files = []
        
        for file_path in input_files:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
                
            if file_path.suffix.lower() == '.zip':
                try:
                    logger.info(f"Extracting ZIP: {file_path}")
                    
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        # Extract all files
                        zip_ref.extractall(output_dir)
                        
                        # Track extracted files
                        for name in zip_ref.namelist():
                            if not name.endswith('/'):  # Skip directories
                                extracted_path = output_dir / name
                                if extracted_path.exists():
                                    output_files.append(extracted_path)
                    
                    # Optionally remove original ZIP
                    if parameters.get('remove_original', True):
                        file_path.unlink()
                        logger.info(f"Removed original ZIP: {file_path}")
                        
                except zipfile.BadZipFile:
                    return ProcessingResult(
                        success=False,
                        output_files=[],
                        error_message=f"Invalid ZIP file: {file_path}"
                    )
                except Exception as e:
                    return ProcessingResult(
                        success=False,
                        output_files=[],
                        error_message=f"Failed to extract {file_path}: {e}"
                    )
        
        return ProcessingResult(
            success=True,
            output_files=output_files,
            metadata={
                'extracted_files': len(output_files),
                'source_archives': len([f for f in input_files if f.suffix.lower() == '.zip'])
            }
        )
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'remove_original': True
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Check that remove_original is a boolean if provided
        if 'remove_original' in parameters:
            if not isinstance(parameters['remove_original'], bool):
                return False
        return True