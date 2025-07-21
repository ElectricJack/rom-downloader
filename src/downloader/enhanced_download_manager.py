"""
Enhanced download manager with tool pipeline integration.
"""

import time
import random
import logging
import requests
import shutil
import queue
import threading
import os
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from src.models.game_library import ROM
from src.tools.pipeline_manager import ToolPipelineManager
from src.tools.base import ProcessingResult
from src.config.enhanced_config_manager import EnhancedConfigManager

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
class CopyQueueItem:
    """Represents an item in the network copy queue"""
    rom: ROM
    src_file: Path
    dst_file: Path
    
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
        
        # Copy queue for background network operations
        self.copy_queue = queue.Queue()
        self.copy_thread = None
        self.copy_thread_running = False
        self.copy_progress_callback = None
        self.copy_completion_callback = None
        self.current_copy_item = None
        self.pending_copies = set()  # Track pending copies by ROM filename
        self.completed_installations = set()  # Track completed installations
        
        # Enhanced download manager initialized
    
    def download_roms(self, roms: List[ROM], platform: str,
                     progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None,
                     completion_callback: Optional[Callable[[ROM, DownloadResult], None]] = None,
                     copy_progress_callback: Optional[Callable[[ROM, DownloadProgress], None]] = None,
                     copy_completion_callback: Optional[Callable[[ROM, DownloadResult], None]] = None) -> List[DownloadResult]:
        """Download multiple ROMs with tool pipeline processing"""
        
        # Starting download session
        
        results = []
        self.cancelled = False
        
        # Store copy callbacks
        self.copy_progress_callback = copy_progress_callback
        self.copy_completion_callback = copy_completion_callback
        
        # Start copy worker thread if not already running
        if not self.copy_thread_running:
            self.copy_thread_running = True
            self.copy_thread = threading.Thread(target=self._copy_worker, daemon=True)
            self.copy_thread.start()
            # Copy worker thread started
        
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
                        pass  # Successfully downloaded and processed
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
        
        # Download batch completed
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
            
            # Step 3: Don't delete temp file here - let copy worker handle cleanup
            # The copy worker will delete the temp file after successful copy
            # This ensures the file exists when the copy worker processes it
            
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
        # Generate temp filename preserving the extension
        name_without_ext = rom.filename
        extension = ""
        if '.' in rom.filename:
            name_without_ext, extension = rom.filename.rsplit('.', 1)
            extension = f".{extension}"
        temp_filename = f"{name_without_ext}_{int(time.time())}{extension}"
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
            # No processing needed, queue file for background copy
            final_file = target_dir / rom.filename
            try:
                # Add to copy queue for background processing
                copy_item = CopyQueueItem(
                    rom=rom,
                    src_file=rom_file,
                    dst_file=final_file
                )
                self.copy_queue.put(copy_item)
                self.pending_copies.add(rom.filename)
                # Queued for copy
                
                return ProcessingResult(
                    success=True,
                    output_files=[final_file],
                    metadata={'pipeline_steps': 0, 'queued_for_copy': True}
                )
            except Exception as e:
                return ProcessingResult(
                    success=False,
                    error_message=f"Failed to queue file for copy: {e}"
                )
        
        # Update progress to show processing started
        if progress_callback:
            progress = DownloadProgress(
                rom=rom,
                operation="processing",
                step="Starting tool pipeline"
            )
            progress_callback(rom, progress)
        
        # Process through pipeline with status updates
        logger.info(f"Processing {rom.filename} through tool pipeline ({len(pipeline)} steps)")
        
        # Use temp directory for pipeline output, then queue for network copy
        temp_output_dir = self.temp_dir / f"processed_{int(time.time())}"
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add callback to pipeline manager to get step-by-step updates
        def pipeline_progress_callback(step_name: str, step_index: int, total_steps: int):
            if progress_callback:
                progress = DownloadProgress(
                    rom=rom,
                    current_bytes=step_index,
                    total_bytes=total_steps,
                    operation="processing",
                    step=f"Running {step_name}"
                )
                progress_callback(rom, progress)
        
        result = self.pipeline_manager.process_rom(
            rom_path=rom_file,
            platform=platform,
            pipeline_config=pipeline,
            output_dir=temp_output_dir,
            progress_callback=pipeline_progress_callback
        )
        
        # If processing succeeded, queue output files for network copy
        if result.success and result.output_files:
            # Pipeline processing complete
            
            # Queue each output file for copy to target directory
            queued_files = []
            for output_file in result.output_files:
                final_file = target_dir / output_file.name
                copy_item = CopyQueueItem(
                    rom=rom,
                    src_file=output_file,
                    dst_file=final_file
                )
                self.copy_queue.put(copy_item)
                self.pending_copies.add(rom.filename)
                queued_files.append(final_file)
                # Queued for copy
            
            # Update result to reflect final destinations
            result.output_files = queued_files
            if result.metadata is None:
                result.metadata = {}
            result.metadata['queued_for_copy'] = True
        
        return result
    
    def cancel_downloads(self):
        """Cancel all active downloads and copies"""
        self.cancelled = True
        logger.info("Cancelling all downloads and copies...")
        
        # Clear pending copies from queue
        queue_cleared = 0
        try:
            while not self.copy_queue.empty():
                try:
                    item = self.copy_queue.get_nowait()
                    self.copy_queue.task_done()
                    queue_cleared += 1
                except:
                    break
        except Exception as e:
            logger.error(f"Error clearing copy queue: {e}")
        
        if queue_cleared > 0:
            logger.info(f"Cleared {queue_cleared} pending copies from queue")
        
        # Clear pending copies tracking
        self.pending_copies.clear()
        
        # Download cancellation requested
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get download statistics"""
        return {
            'temp_directory': str(self.temp_dir),
            'max_concurrent': self.max_concurrent,
            'delay_range': self.delay_range,
            'active_downloads': len(self.current_downloads),
            'pending_copies': len(self.pending_copies),
            'completed_installations': len(self.completed_installations),
            'cancelled': self.cancelled
        }
    
    def is_installation_complete(self, rom_filename: str) -> bool:
        """Check if a ROM installation is complete"""
        return rom_filename in self.completed_installations
    
    def is_copy_pending(self, rom_filename: str) -> bool:
        """Check if a ROM copy is pending"""
        return rom_filename in self.pending_copies
    
    def get_copy_queue_size(self) -> int:
        """Get the current size of the copy queue"""
        return self.copy_queue.qsize()
    
    def wait_for_all_copies_complete(self, timeout: float = None) -> bool:
        """Wait for all pending copies to complete"""
        try:
            # Wait for the copy queue to be empty and all pending copies finished
            start_time = time.time()
            while self.pending_copies or not self.copy_queue.empty():
                if timeout and (time.time() - start_time) > timeout:
                    return False
                time.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Error waiting for copies to complete: {e}")
            return False
    
    def _copy_worker(self):
        """Background worker thread for processing network copy queue"""
        # Copy worker thread started
        
        while self.copy_thread_running and not self.cancelled:
            try:
                # Get next item from queue (with timeout to allow thread shutdown)
                item = self.copy_queue.get(timeout=1.0)
                
                # Check for cancellation before starting copy
                if self.cancelled:
                    self.copy_queue.task_done()
                    break
                
                self.current_copy_item = item
                # Starting network copy
                
                # Perform the copy with progress tracking
                success = self._perform_network_copy(item)
                
                if success:
                    logger.info(f"Successfully copied: {item.rom.filename}")
                    self.completed_installations.add(item.rom.filename)
                    # Notify GUI that copy succeeded
                    if self.copy_completion_callback:
                        result = DownloadResult(
                            rom=item.rom,
                            success=True,
                            output_files=[item.dst_file]
                        )
                        self.copy_completion_callback(item.rom, result)
                else:
                    logger.error(f"Failed to copy to network: {item.rom.filename}")
                    # Notify GUI that copy failed
                    if self.copy_completion_callback:
                        result = DownloadResult(
                            rom=item.rom,
                            success=False,
                            error_message="Copy failed"
                        )
                        self.copy_completion_callback(item.rom, result)
                
                # Remove from pending copies tracking
                self.pending_copies.discard(item.rom.filename)
                
                self.copy_queue.task_done()
                self.current_copy_item = None
                
            except queue.Empty:
                # Timeout waiting for queue item - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in copy worker: {e}")
                if self.current_copy_item:
                    self.copy_queue.task_done()
                    self.current_copy_item = None
        
        # Copy worker thread stopped
    
    def _check_disk_space(self, target_path: Path, required_bytes: int) -> tuple[bool, str]:
        """Check if there's enough disk space for the file"""
        try:
            # Get available space on target drive
            if os.name == 'nt':  # Windows
                # For network paths, try to get the actual network drive stats
                try:
                    statvfs = os.statvfs(str(target_path.parent))
                    available_bytes = statvfs.f_bavail * statvfs.f_frsize
                except (OSError, AttributeError):
                    # Fallback for Windows network drives
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        str(target_path.parent), 
                        ctypes.pointer(free_bytes), 
                        None, 
                        None
                    )
                    available_bytes = free_bytes.value
            else:  # Unix-like systems
                statvfs = os.statvfs(str(target_path.parent))
                available_bytes = statvfs.f_bavail * statvfs.f_frsize
            
            if available_bytes < required_bytes:
                # Format sizes for user-friendly display
                def format_bytes(bytes_val):
                    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                        if bytes_val < 1024.0:
                            return f"{bytes_val:.1f} {unit}"
                        bytes_val /= 1024.0
                    return f"{bytes_val:.1f} PB"
                
                error_msg = (
                    f"Insufficient disk space on target drive.\n\n"
                    f"Required: {format_bytes(required_bytes)}\n"
                    f"Available: {format_bytes(available_bytes)}\n\n"
                    f"Please free up space on the Batocera device or check the network connection."
                )
                return False, error_msg
            
            return True, ""
            
        except Exception as e:
            # If we can't check disk space, log warning but allow the copy to proceed
            logger.warning(f"Could not check disk space for {target_path}: {e}")
            return True, ""
    
    def _show_disk_space_error(self, error_msg: str):
        """Show disk space error dialog to user"""
        try:
            # Create a simple error dialog
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Keep dialog on top
            
            messagebox.showerror(
                "Disk Space Error",
                error_msg,
                parent=root
            )
            
            root.destroy()
            
        except Exception as e:
            # If GUI dialog fails, at least log the error
            logger.error(f"Disk space error (dialog failed): {error_msg}")
            logger.error(f"Dialog error: {e}")
    
    def _perform_network_copy(self, item: CopyQueueItem) -> bool:
        """Perform network copy with progress tracking"""
        try:
            file_size = item.src_file.stat().st_size
            
            # Check disk space before starting copy
            has_space, error_msg = self._check_disk_space(item.dst_file, file_size)
            if not has_space:
                # Show error dialog and stop all downloads
                self._show_disk_space_error(error_msg)
                self.cancel_downloads()
                return False
            
            copied_bytes = 0
            buffer_size = 64 * 1024  # 64KB buffer
            start_time = time.time()
            
            # Ensure target directory exists
            item.dst_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Perform the copy with progress tracking
            partial_file_created = False
            try:
                with open(item.src_file, 'rb') as src, open(item.dst_file, 'wb') as dst:
                    partial_file_created = True
                    while True:
                        # Check for cancellation
                        if self.cancelled:
                            break
                            
                        buffer = src.read(buffer_size)
                        if not buffer:
                            break
                        
                        dst.write(buffer)
                        dst.flush()  # Force write to disk to get accurate progress
                        copied_bytes += len(buffer)
                        
                        # Update progress callback with timing info
                        if self.copy_progress_callback and file_size > 0:
                            elapsed = time.time() - start_time
                            speed_bps = int(copied_bytes / elapsed) if elapsed > 0 else 0
                            remaining_bytes = file_size - copied_bytes
                            eta_seconds = int(remaining_bytes / speed_bps) if speed_bps > 0 else 0
                            
                            progress = DownloadProgress(
                                rom=item.rom,
                                current_bytes=copied_bytes,
                                total_bytes=file_size,
                                speed_bps=speed_bps,
                                eta_seconds=eta_seconds,
                                operation="copying"
                            )
                            self.copy_progress_callback(item.rom, progress)
                        
                        # Small delay for large files to allow UI updates and prevent UI freezing
                        if copied_bytes % (buffer_size * 5) == 0:  # Every 320KB
                            time.sleep(0.01)  # 10ms delay for smoother UI updates
                
                # If cancelled during copy, clean up partial file
                if self.cancelled and partial_file_created:
                    try:
                        if item.dst_file.exists():
                            item.dst_file.unlink()
                            logger.info(f"Cleaned up partial file: {item.dst_file}")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up partial file {item.dst_file}: {cleanup_error}")
                    return False
                
            except Exception as e:
                # Clean up partial file on error
                if partial_file_created and item.dst_file.exists():
                    try:
                        item.dst_file.unlink()
                        logger.info(f"Cleaned up partial file after error: {item.dst_file}")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up partial file after error {item.dst_file}: {cleanup_error}")
                raise e
            
            # Copy file metadata (permissions, timestamps)
            try:
                shutil.copystat(str(item.src_file), str(item.dst_file))
            except (OSError, PermissionError):
                # Non-critical if we can't copy metadata
                pass
            
            # Final progress update (100%)
            if self.copy_progress_callback:
                progress = DownloadProgress(
                    rom=item.rom,
                    current_bytes=file_size,
                    total_bytes=file_size,
                    operation="copying"
                )
                self.copy_progress_callback(item.rom, progress)
            
            # Remove source file after successful copy
            item.src_file.unlink(missing_ok=True)
            
            # Clean up parent directory if it's a processed_{id} directory and is now empty
            parent_dir = item.src_file.parent
            if parent_dir.name.startswith('processed_') and parent_dir.parent == self.temp_dir:
                try:
                    # Only remove if directory is empty
                    if not any(parent_dir.iterdir()):
                        parent_dir.rmdir()
                        logger.debug(f"Cleaned up empty processed directory: {parent_dir.name}")
                except OSError:
                    # Directory not empty or other error - ignore
                    pass
            
            logger.info(f"Successfully copied {item.src_file.name} to {item.dst_file} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy {item.src_file} to {item.dst_file}: {e}")
            # Clean up partial destination file
            if item.dst_file.exists():
                item.dst_file.unlink(missing_ok=True)
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary files and directories"""
        if not self.temp_dir.exists():
            return
        
        cleaned_files = 0
        cleaned_dirs = 0
        for temp_item in self.temp_dir.iterdir():
            try:
                if temp_item.is_file():
                    temp_item.unlink()
                    cleaned_files += 1
                elif temp_item.is_dir():
                    # Remove directory and all contents (for processed_{id} folders)
                    shutil.rmtree(temp_item)
                    cleaned_dirs += 1
            except Exception as e:
                logger.warning(f"Failed to clean up temp item {temp_item}: {e}")
        
        logger.info(f"Cleaned up {cleaned_files} temporary files and {cleaned_dirs} directories")
    
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