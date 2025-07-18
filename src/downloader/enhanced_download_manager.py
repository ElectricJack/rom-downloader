"""
Enhanced download manager with tool pipeline integration.
"""

import time
import random
import logging
import requests
import shutil
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from models.game_library import ROM
from tools.pipeline_manager import ToolPipelineManager
from tools.base import ProcessingResult
from config.enhanced_config_manager import EnhancedConfigManager

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """Progress information for a download operation"""
    rom: ROM
    current_bytes: int = 0
    total_bytes: int = 0
    speed_bps: int = 0
    eta_seconds: int = 0
    operation: str = "downloading"
    step: str = ""
    
    @property
    def percentage(self) -> float:
        """Get download percentage"""
        if self.total_bytes == 0:
            return 0.0
        return (self.current_bytes / self.total_bytes) * 100.0
    
    @property
    def speed_formatted(self) -> str:
        """Get formatted speed string"""
        if self.speed_bps < 1024:
            return f"{self.speed_bps} B/s"
        elif self.speed_bps < 1024 * 1024:
            return f"{self.speed_bps / 1024:.1f} KB/s"
        else:
            return f"{self.speed_bps / (1024 * 1024):.1f} MB/s"
    
    @property
    def eta_formatted(self) -> str:
        """Get formatted ETA string"""
        if self.eta_seconds < 60:
            return f"{self.eta_seconds}s"
        elif self.eta_seconds < 3600:
            return f"{self.eta_seconds // 60}m {self.eta_seconds % 60}s"
        else:
            hours = self.eta_seconds // 3600
            minutes = (self.eta_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


@dataclass
class DownloadResult:
    """Result of a download operation"""
    rom: ROM
    success: bool
    output_files: List[Path] = field(default_factory=list)
    error_message: str = ""
    processing_result: Optional[ProcessingResult] = None
    download_time: float = 0.0
    processing_time: float = 0.0
    
    @property
    def total_time(self) -> float:
        """Get total time for download and processing"""
        return self.download_time + self.processing_time


class EnhancedDownloadManager:
    """Enhanced download manager with tool pipeline integration"""
    
    def __init__(self, config_manager: EnhancedConfigManager, 
                 pipeline_manager: ToolPipelineManager = None):
        self.config = config_manager
        self.pipeline_manager = pipeline_manager or ToolPipelineManager()
        
        # Initialize HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Get configuration
        self.temp_dir = self.config.get_temp_directory()
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_concurrent = self.config.get_max_concurrent_downloads()
        self.delay_range = self.config.get_download_delay_range()
        
        # State
        self.cancelled = False
        self.current_downloads = {}
        
        logger.info(f"Enhanced download manager initialized with temp dir: {self.temp_dir}")
    
    def download_roms(self, roms: List[ROM], platform: str,
                     progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None,
                     completion_callback: Optional[Callable[[ROM, DownloadResult], None]] = None) -> List[DownloadResult]:
        """Download multiple ROMs with tool pipeline processing"""
        
        logger.info(f"Starting download of {len(roms)} ROMs for platform {platform}")
        
        results = []
        self.cancelled = False
        
        # Get target directory
        target_dir = self.config.get_target_directory(platform)
        if not target_dir:
            logger.error(f"No target directory configured for platform: {platform}")
            return results
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Process downloads with controlled concurrency
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all download tasks
            future_to_rom = {
                executor.submit(
                    self._download_and_process_rom,
                    rom, platform, target_dir, progress_callback
                ): rom
                for rom in roms
            }
            
            # Process completed downloads
            for future in as_completed(future_to_rom):
                if self.cancelled:
                    break
                
                rom = future_to_rom[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if completion_callback:
                        completion_callback(rom, result)
                    
                    if result.success:
                        logger.info(f"Successfully downloaded and processed: {rom.filename}")
                    else:
                        logger.error(f"Failed to download {rom.filename}: {result.error_message}")
                        
                except Exception as e:
                    logger.error(f"Exception during download of {rom.filename}: {e}")
                    error_result = DownloadResult(
                        rom=rom,
                        success=False,
                        error_message=str(e)
                    )
                    results.append(error_result)
                    
                    if completion_callback:
                        completion_callback(rom, error_result)
                
                # Add delay between downloads
                if not self.cancelled and len(results) < len(roms):
                    delay = random.uniform(*self.delay_range)
                    time.sleep(delay)
        
        logger.info(f"Download batch completed: {sum(1 for r in results if r.success)}/{len(results)} successful")
        return results
    
    def _download_and_process_rom(self, rom: ROM, platform: str, target_dir: Path,
                                progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None) -> DownloadResult:
        """Download and process a single ROM through the tool pipeline"""
        
        if self.cancelled:
            return DownloadResult(
                rom=rom,
                success=False,
                error_message="Download cancelled"
            )
        
        start_time = time.time()
        
        try:
            # Step 1: Download the ROM
            download_start = time.time()
            downloaded_file = self._download_rom(rom, self.temp_dir, progress_callback)
            download_time = time.time() - download_start
            
            if not downloaded_file:
                return DownloadResult(
                    rom=rom,
                    success=False,
                    error_message="Download failed",
                    download_time=download_time
                )
            
            # Step 2: Process through tool pipeline
            processing_start = time.time()
            processing_result = self._process_rom(downloaded_file, rom, platform, target_dir, progress_callback)
            processing_time = time.time() - processing_start
            
            # Step 3: Clean up temp file if processing succeeded
            if processing_result.success and downloaded_file.exists():
                try:
                    downloaded_file.unlink()
                except:
                    pass  # Don't fail if cleanup fails
            
            return DownloadResult(
                rom=rom,
                success=processing_result.success,
                output_files=processing_result.output_files,
                error_message=processing_result.error_message,
                processing_result=processing_result,
                download_time=download_time,
                processing_time=processing_time
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            return DownloadResult(
                rom=rom,
                success=False,
                error_message=f"Unexpected error: {e}",
                download_time=total_time
            )
    
    def _download_rom(self, rom: ROM, temp_dir: Path,
                     progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None) -> Optional[Path]:
        """Download a ROM file to temporary directory"""
        
        # Generate temporary filename
        temp_filename = f"{rom.filename}_{int(time.time())}"
        temp_file = temp_dir / temp_filename
        
        try:
            logger.debug(f"Downloading {rom.url} to {temp_file}")
            
            # Check if already exists (resume support could be added here)
            if temp_file.exists():
                temp_file.unlink()
            
            # Start download
            response = self.session.get(rom.url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get total size
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()
            
            # Track progress
            progress = DownloadProgress(
                rom=rom,
                total_bytes=total_size,
                operation="downloading"
            )
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        temp_file.unlink(missing_ok=True)
                        return None
                    
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            progress.current_bytes = downloaded_size
                            progress.speed_bps = int(downloaded_size / elapsed)
                            
                            if progress.speed_bps > 0:
                                remaining_bytes = total_size - downloaded_size
                                progress.eta_seconds = int(remaining_bytes / progress.speed_bps)
                        
                        if progress_callback:
                            progress_callback(rom, progress)
            
            logger.debug(f"Downloaded {rom.filename} ({downloaded_size} bytes)")
            return temp_file
            
        except requests.RequestException as e:
            logger.error(f"Network error downloading {rom.filename}: {e}")
            temp_file.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"Error downloading {rom.filename}: {e}")
            temp_file.unlink(missing_ok=True)
            return None
    
    def _process_rom(self, rom_file: Path, rom: ROM, platform: str, target_dir: Path,
                    progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None) -> ProcessingResult:
        """Process ROM through tool pipeline"""
        
        # Get tool pipeline for platform
        pipeline = self.config.get_platform_tool_pipeline(platform)
        
        if not pipeline:
            # No processing needed, just move file to target with progress tracking
            final_file = target_dir / rom_file.name
            try:
                # Use progress-aware copy for cross-filesystem compatibility
                success = self._copy_with_progress(rom_file, final_file, rom, progress_callback)
                if success:
                    return ProcessingResult(
                        success=True,
                        output_files=[final_file],
                        metadata={'pipeline_steps': 0}
                    )
                else:
                    return ProcessingResult(
                        success=False,
                        error_message="Failed to copy file with progress tracking"
                    )
            except Exception as e:
                return ProcessingResult(
                    success=False,
                    error_message=f"Failed to move file: {e}"
                )
        
        # Update progress
        if progress_callback:
            # We need the ROM object, but we only have the file path
            # For now, create a minimal progress update
            progress = DownloadProgress(
                rom=ROM(filename=rom_file.name, url="", size="", file_type=""),
                operation="processing",
                step="pipeline"
            )
            progress_callback(progress.rom, progress)
        
        # Process through pipeline
        result = self.pipeline_manager.process_rom(
            rom_path=rom_file,
            platform=platform,
            pipeline_config=pipeline,
            output_dir=target_dir
        )
        
        return result
    
    def cancel_downloads(self):
        """Cancel all active downloads"""
        self.cancelled = True
        logger.info("Download cancellation requested")
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get download statistics"""
        return {
            'temp_directory': str(self.temp_dir),
            'max_concurrent': self.max_concurrent,
            'delay_range': self.delay_range,
            'active_downloads': len(self.current_downloads),
            'cancelled': self.cancelled
        }
    
    def _copy_with_progress(self, src_file: Path, dst_file: Path, rom: ROM,
                           progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None) -> bool:
        """Copy file with progress tracking for network operations"""
        try:
            # Get file size for progress tracking
            file_size = src_file.stat().st_size
            
            copied_bytes = 0
            buffer_size = 64 * 1024  # 64KB buffer
            
            # Ensure target directory exists
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Perform the copy with progress tracking
            with open(src_file, 'rb') as src, open(dst_file, 'wb') as dst:
                while True:
                    buffer = src.read(buffer_size)
                    if not buffer:
                        break
                    
                    dst.write(buffer)
                    copied_bytes += len(buffer)
                    
                    # Update progress callback
                    if progress_callback and file_size > 0:
                        progress = DownloadProgress(
                            rom=rom,
                            current_bytes=copied_bytes,
                            total_bytes=file_size,
                            operation="copying"
                        )
                        progress_callback(rom, progress)
                    
                    # Small delay for large files to allow UI updates
                    if copied_bytes % (buffer_size * 10) == 0:  # Every 640KB
                        time.sleep(0.001)  # 1ms delay
            
            # Copy file metadata (permissions, timestamps)
            try:
                shutil.copystat(str(src_file), str(dst_file))
            except (OSError, PermissionError):
                # Non-critical if we can't copy metadata
                pass
            
            # Final progress update (100%)
            if progress_callback:
                progress = DownloadProgress(
                    rom=rom,
                    current_bytes=file_size,
                    total_bytes=file_size,
                    operation="copying"
                )
                progress_callback(rom, progress)
            
            # Remove source file after successful copy
            src_file.unlink(missing_ok=True)
            
            logger.info(f"Successfully copied {src_file.name} to {dst_file} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy {src_file} to {dst_file}: {e}")
            # Clean up partial destination file
            if dst_file.exists():
                dst_file.unlink(missing_ok=True)
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        if not self.temp_dir.exists():
            return
        
        cleaned_count = 0
        for temp_file in self.temp_dir.iterdir():
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} temporary files")
    
    def test_connection(self, url: str) -> bool:
        """Test connection to a URL"""
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Connection test failed for {url}: {e}")
            return False
    
    def estimate_download_time(self, rom: ROM) -> Optional[float]:
        """Estimate download time for a ROM (in seconds)"""
        if not rom.size:
            return None
        
        # Parse size string to bytes
        size_bytes = self._parse_size_string(rom.size)
        if size_bytes == 0:
            return None
        
        # Estimate based on average broadband speed (10 Mbps)
        avg_speed_bps = 10 * 1024 * 1024 / 8  # 10 Mbps to bytes per second
        
        return size_bytes / avg_speed_bps
    
    def _parse_size_string(self, size_str: str) -> int:
        """Parse size string like '1.5GB' to bytes"""
        if not size_str:
            return 0
        
        size_str = size_str.upper().replace(' ', '')
        
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }
        
        for unit, multiplier in multipliers.items():
            if size_str.endswith(unit):
                try:
                    number = float(size_str[:-len(unit)])
                    return int(number * multiplier)
                except ValueError:
                    pass
        
        return 0
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'session'):
            self.session.close()