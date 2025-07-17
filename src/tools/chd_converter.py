"""
CHD format conversion tool using chdman.
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

from tools.base import ToolHandler, ProcessingResult

logger = logging.getLogger(__name__)


class CHDConverterTool(ToolHandler):
    """Tool for converting disc images to CHD format"""
    
    @property
    def tool_id(self) -> str:
        return "chd_converter"
    
    @property
    def description(self) -> str:
        return "Convert disc images to CHD format using chdman"
    
    @property
    def supported_file_types(self) -> List[str]:
        return ['.iso', '.bin', '.cue']
    
    def can_process(self, input_files: List[Path], parameters: Dict[str, Any]) -> bool:
        # Check if chdman is available
        chdman_path = parameters.get('chdman_path', 'tools/chdman.exe')
        if not Path(chdman_path).exists():
            logger.warning(f"chdman not found at: {chdman_path}")
            return False
        
        # Check if we have supported files
        return any(f.suffix.lower() in self.supported_file_types 
                  for f in input_files if f.exists())
    
    def process(self, input_files: List[Path], output_dir: Path, 
                parameters: Dict[str, Any]) -> ProcessingResult:
        chdman_path = parameters.get('chdman_path', 'tools/chdman.exe')
        output_files = []
        
        for file_path in input_files:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
                
            if file_path.suffix.lower() in self.supported_file_types:
                chd_path = output_dir / f"{file_path.stem}.chd"
                
                try:
                    logger.info(f"Converting to CHD: {file_path} -> {chd_path}")
                    
                    # Build chdman command
                    cmd = [str(chdman_path), 'createcd', '-i', str(file_path), '-o', str(chd_path)]
                    
                    # Run chdman conversion
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=parameters.get('timeout', 300)  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        if chd_path.exists():
                            output_files.append(chd_path)
                            logger.info(f"Successfully converted to CHD: {chd_path}")
                            
                            # Remove original if requested
                            if parameters.get('remove_original', True):
                                file_path.unlink()
                                logger.info(f"Removed original file: {file_path}")
                        else:
                            logger.error(f"CHD file was not created: {chd_path}")
                    else:
                        return ProcessingResult(
                            success=False,
                            output_files=[],
                            error_message=f"CHD conversion failed for {file_path}: {result.stderr}"
                        )
                        
                except subprocess.TimeoutExpired:
                    return ProcessingResult(
                        success=False,
                        output_files=[],
                        error_message=f"CHD conversion timeout for {file_path}"
                    )
                except Exception as e:
                    return ProcessingResult(
                        success=False,
                        output_files=[],
                        error_message=f"Failed to convert {file_path}: {e}"
                    )
        
        return ProcessingResult(
            success=True,
            output_files=output_files,
            metadata={
                'converted_files': len(output_files),
                'source_files': len([f for f in input_files if f.suffix.lower() in self.supported_file_types])
            }
        )
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'chdman_path': 'tools/chdman.exe',
            'remove_original': True,
            'timeout': 300  # 5 minutes
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Check chdman path exists
        if 'chdman_path' in parameters:
            if not Path(parameters['chdman_path']).exists():
                return False
        
        # Check timeout is reasonable
        if 'timeout' in parameters:
            if not isinstance(parameters['timeout'], int) or parameters['timeout'] <= 0:
                return False
        
        # Check remove_original is boolean
        if 'remove_original' in parameters:
            if not isinstance(parameters['remove_original'], bool):
                return False
        
        return True