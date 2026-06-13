"""
Archive extraction tool for ZIP and 7z files.
"""

import zipfile
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.tools.base import ToolHandler, ProcessingResult

logger = logging.getLogger(__name__)


class ZipExtractorTool(ToolHandler):
    """Tool for extracting ZIP and 7z archives"""
    
    @property
    def tool_id(self) -> str:
        return "zip_extractor"
    
    @property
    def description(self) -> str:
        return "Extract ZIP and 7z archives"
    
    @property
    def supported_file_types(self) -> List[str]:
        return ['.zip', '.7z']
    
    def can_process(self, input_files: List[Path], parameters: Dict[str, Any]) -> bool:
        return any(f.suffix.lower() in ['.zip', '.7z'] for f in input_files if f.exists())
    
    def process(self, input_files: List[Path], output_dir: Path, 
                parameters: Dict[str, Any]) -> ProcessingResult:
        output_files = []
        
        for file_path in input_files:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
                
            if file_path.suffix.lower() == '.zip':
                result = self._extract_zip(file_path, output_dir, parameters)
                if not result.success:
                    return result
                output_files.extend(result.output_files)
                
            elif file_path.suffix.lower() == '.7z':
                result = self._extract_7z(file_path, output_dir, parameters)
                if not result.success:
                    return result
                output_files.extend(result.output_files)
        
        return ProcessingResult(
            success=True,
            output_files=output_files,
            metadata={
                'extracted_files': len(output_files),
                'source_archives': len([f for f in input_files if f.suffix.lower() in ['.zip', '.7z']])
            }
        )
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'remove_original': True,
            'sevenzip_path': '7z'
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        # Check that remove_original is a boolean if provided
        if 'remove_original' in parameters:
            if not isinstance(parameters['remove_original'], bool):
                return False
        
        # Check that sevenzip_path is a string if provided
        if 'sevenzip_path' in parameters:
            if not isinstance(parameters['sevenzip_path'], str):
                return False
        
        return True
    
    def _extract_zip(self, file_path: Path, output_dir: Path, parameters: Dict[str, Any]) -> ProcessingResult:
        """Extract ZIP file"""
        output_files = []
        
        try:
            logger.info(f"Extracting ZIP: {file_path}")
            
            # Verify file exists and has content before attempting extraction
            if not file_path.exists():
                return ProcessingResult(
                    success=False,
                    output_files=[],
                    error_message=f"ZIP file does not exist: {file_path}"
                )
            
            file_size = file_path.stat().st_size
            if file_size == 0:
                return ProcessingResult(
                    success=False,
                    output_files=[],
                    error_message=f"ZIP file is empty: {file_path} (0 bytes)"
                )
            
            logger.info(f"ZIP file size: {file_size} bytes")
            
            # Test ZIP file integrity before extraction
            try:
                with zipfile.ZipFile(file_path, 'r') as test_zip:
                    # Test the ZIP file by reading its central directory
                    test_result = test_zip.testzip()
                    if test_result:
                        return ProcessingResult(
                            success=False,
                            output_files=[],
                            error_message=f"ZIP file corruption detected in file: {test_result}"
                        )
                    logger.info(f"ZIP integrity test passed for {file_path}")
            except zipfile.BadZipFile as e:
                return ProcessingResult(
                    success=False,
                    output_files=[],
                    error_message=f"Invalid ZIP file (integrity test): {file_path} - {e}"
                )
            
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
            output_files=output_files
        )
    
    def _extract_7z(self, file_path: Path, output_dir: Path, parameters: Dict[str, Any]) -> ProcessingResult:
        """Extract 7z file"""
        output_files = []
        sevenzip_path = parameters.get('sevenzip_path', '7z')
        
        try:
            logger.info(f"Extracting 7z: {file_path}")
            
            # Use 7z command line to extract
            cmd = [sevenzip_path, 'x', str(file_path), f'-o{output_dir}', '-y']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Find extracted files
            if output_dir.exists():
                for extracted_file in output_dir.rglob('*'):
                    if extracted_file.is_file() and extracted_file != file_path:
                        output_files.append(extracted_file)
            
            # Optionally remove original 7z
            if parameters.get('remove_original', True):
                file_path.unlink()
                logger.info(f"Removed original 7z: {file_path}")
                
        except subprocess.CalledProcessError as e:
            error_msg = f"7z extraction failed for {file_path}: {e.stderr}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                output_files=[],
                error_message=error_msg
            )
        except FileNotFoundError:
            error_msg = f"7z executable not found: {sevenzip_path}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                output_files=[],
                error_message=error_msg
            )
        except Exception as e:
            return ProcessingResult(
                success=False,
                output_files=[],
                error_message=f"Failed to extract {file_path}: {e}"
            )
        
        return ProcessingResult(
            success=True,
            output_files=output_files
        )