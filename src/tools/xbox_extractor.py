"""
Xbox ISO extraction tool using extract-xiso.
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.tools.base import ToolHandler, ProcessingResult

logger = logging.getLogger(__name__)


class XboxExtractorTool(ToolHandler):
    """Tool for extracting Xbox ISO files"""
    
    @property
    def tool_id(self) -> str:
        return "xbox_extractor"
    
    @property
    def description(self) -> str:
        return "Extract Xbox ISO files using extract-xiso"
    
    @property
    def supported_file_types(self) -> List[str]:
        return ['.iso']
    
    def can_process(self, input_files: List[Path], parameters: Dict[str, Any]) -> bool:
        # Only process ISOs if we're on Xbox platform
        platform = parameters.get('platform', '').lower()
        if platform != 'xbox':
            return False
        
        # Check if extract-xiso is available
        extract_xiso_path = parameters.get('extract_xiso_path', 'tools/extract-xiso.exe')
        if not Path(extract_xiso_path).exists():
            logger.warning(f"extract-xiso not found at: {extract_xiso_path}")
            return False
        
        # Check if we have ISO files
        return any(f.suffix.lower() == '.iso' for f in input_files if f.exists())
    
    def process(self, input_files: List[Path], output_dir: Path, 
                parameters: Dict[str, Any]) -> ProcessingResult:
        extract_xiso_path = parameters.get('extract_xiso_path', 'tools/extract-xiso.exe')
        output_files = []
        
        for file_path in input_files:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
                
            if file_path.suffix.lower() == '.iso':
                extract_dir = output_dir / file_path.stem
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                try:
                    logger.info(f"Extracting Xbox ISO: {file_path} -> {extract_dir}")
                    
                    # Build extract-xiso command
                    cmd = [str(extract_xiso_path), str(file_path), str(extract_dir)]
                    
                    # Run extract-xiso
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=parameters.get('timeout', 300)  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        # Collect extracted files
                        for extracted_file in extract_dir.rglob('*'):
                            if extracted_file.is_file():
                                output_files.append(extracted_file)
                        
                        if output_files:
                            logger.info(f"Successfully extracted {len(output_files)} files from {file_path}")
                            
                            # Remove original if requested
                            if parameters.get('remove_original', True):
                                file_path.unlink()
                                logger.info(f"Removed original ISO: {file_path}")
                        else:
                            logger.warning(f"No files extracted from {file_path}")
                    else:
                        return ProcessingResult(
                            success=False,
                            output_files=[],
                            error_message=f"Xbox extraction failed for {file_path}: {result.stderr}"
                        )
                        
                except subprocess.TimeoutExpired:
                    return ProcessingResult(
                        success=False,
                        output_files=[],
                        error_message=f"Xbox extraction timeout for {file_path}"
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
                'source_isos': len([f for f in input_files if f.suffix.lower() == '.iso'])
            }
        )
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'extract_xiso_path': 'tools/extract-xiso.exe',
            'remove_original': True,
            'timeout': 300,  # 5 minutes
            'platform': 'xbox'
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Check extract-xiso path exists
        if 'extract_xiso_path' in parameters:
            if not Path(parameters['extract_xiso_path']).exists():
                return False
        
        # Check timeout is reasonable
        if 'timeout' in parameters:
            if not isinstance(parameters['timeout'], int) or parameters['timeout'] <= 0:
                return False
        
        # Check remove_original is boolean
        if 'remove_original' in parameters:
            if not isinstance(parameters['remove_original'], bool):
                return False
        
        # Check platform is string
        if 'platform' in parameters:
            if not isinstance(parameters['platform'], str):
                return False
        
        return True