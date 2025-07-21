"""
CHD format conversion tool using chdman.
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.tools.base import ToolHandler, ProcessingResult

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
        processed_stems = set()  # Track which disc sets we've already processed
        
        # Sort files to prioritize .cue files first, then .iso files, then .bin files
        def file_priority(file_path):
            ext = file_path.suffix.lower()
            if ext == '.cue':
                return 0  # Highest priority
            elif ext == '.iso':
                return 1  # Medium priority
            elif ext == '.bin':
                return 2  # Lowest priority
            else:
                return 3
        
        sorted_files = sorted([f for f in input_files if f.exists()], key=file_priority)
        
        for file_path in sorted_files:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
                
            # Skip if we've already processed this disc set
            if file_path.stem in processed_stems:
                logger.info(f"Skipping {file_path} - already processed as part of disc set")
                continue
                
            if file_path.suffix.lower() in self.supported_file_types:
                chd_path = output_dir / f"{file_path.stem}.chd"
                
                # Skip .bin files if there's a corresponding .cue file
                if file_path.suffix.lower() == '.bin':
                    cue_file = file_path.with_suffix('.cue')
                    if cue_file.exists():
                        logger.info(f"Skipping {file_path} - will use {cue_file} instead")
                        continue
                
                try:
                    logger.info(f"Converting to CHD: {file_path} -> {chd_path}")
                    
                    # Build chdman command
                    cmd = [str(chdman_path), 'createcd', '-i', str(file_path), '-o', str(chd_path)]
                    
                    # Run chdman conversion with increased timeout for large files
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=parameters.get('timeout', 900)  # 15 minute timeout (increased from 5)
                    )
                    
                    if result.returncode == 0:
                        if chd_path.exists() and chd_path.stat().st_size > 1024:  # Check file is larger than 1KB
                            output_files.append(chd_path)
                            processed_stems.add(file_path.stem)
                            logger.info(f"Successfully converted to CHD: {chd_path} ({chd_path.stat().st_size} bytes)")
                            
                            # Remove original and related files if requested
                            if parameters.get('remove_original', True):
                                # For .cue files, also remove corresponding .bin files
                                if file_path.suffix.lower() == '.cue':
                                    # Find and remove associated .bin files
                                    for bin_file in output_dir.glob(f"{file_path.stem}*.bin"):
                                        if bin_file.exists():
                                            bin_file.unlink()
                                            logger.info(f"Removed associated bin file: {bin_file}")
                                
                                file_path.unlink()
                                logger.info(f"Removed original file: {file_path}")
                        else:
                            logger.error(f"CHD file was not created properly: {chd_path} (size: {chd_path.stat().st_size if chd_path.exists() else 'missing'})")
                            return ProcessingResult(
                                success=False,
                                output_files=[],
                                error_message=f"CHD file was not created properly: {chd_path}"
                            )
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
                        error_message=f"CHD conversion timeout for {file_path} (exceeded {parameters.get('timeout', 900)} seconds)"
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
            'timeout': 900  # 15 minutes (increased from 5 for large disc images)
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