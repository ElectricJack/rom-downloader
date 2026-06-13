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
        return "Convert Xbox ISO files to XISO format using extract-xiso"
    
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
                # Create XISO output file name
                output_file = output_dir / f"{file_path.stem}.xiso.iso"
                
                try:
                    logger.info(f"Converting Xbox ISO to XISO: {file_path} -> {output_file}")
                    
                    # Build extract-xiso command to rewrite as optimized XISO
                    # Use -r flag to rewrite ISO as XISO, -d to specify output directory  
                    cmd = [str(extract_xiso_path), "-r", "-d", str(output_dir), str(file_path)]
                    
                    # Run extract-xiso
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=parameters.get('timeout', 300)  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        # The -r flag creates the rewritten file in the output directory
                        actual_output_file = output_dir / file_path.name
                        
                        if actual_output_file.exists():
                            # Rename to .xiso.iso format
                            if not actual_output_file.name.endswith('.xiso.iso'):
                                actual_output_file.rename(output_file)
                            else:
                                output_file = actual_output_file
                                
                            output_files.append(output_file)
                            logger.info(f"Successfully created XISO: {output_file}")
                            
                            # Remove original if requested
                            if parameters.get('remove_original', True):
                                try:
                                    file_path.unlink()
                                    logger.info(f"Removed original ISO: {file_path}")
                                except FileNotFoundError:
                                    logger.info(f"Original ISO already removed: {file_path}")
                                except Exception as e:
                                    logger.warning(f"Could not remove original ISO {file_path}: {e}")
                        else:
                            logger.warning(f"XISO file not created: {actual_output_file}")
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
                    # If we successfully created output files, don't treat this as a failure
                    if output_files:
                        logger.warning(f"Minor error after successful XISO creation for {file_path}: {e}")
                        break  # Continue to next file
                    else:
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