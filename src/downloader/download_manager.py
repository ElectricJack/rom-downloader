"""
Download Manager for ROM Files
Handles downloading ROM files with delays and progress tracking.
"""

import os
import time
import random
import logging
import shutil
import threading
import zipfile
import py7zr
import queue
from typing import List, Callable, Optional
from pathlib import Path
import requests
from urllib.parse import urlparse

# Import RomInfo from scraper module
import sys
sys.path.append(str(Path(__file__).parent.parent))
from scraper.web_scraper import RomInfo
from network.network_handler import NetworkHandler

logger = logging.getLogger(__name__)

class CopyQueueItem:
    """Represents an item in the network copy queue."""
    
    def __init__(self, rom: RomInfo, src_file: Path, dst_file: Path, platform_name: str):
        self.rom = rom
        self.src_file = src_file
        self.dst_file = dst_file
        self.platform_name = platform_name

class DownloadProgress:
    """Represents download progress information."""
    
    def __init__(self, rom: RomInfo, current_bytes: int = 0, total_bytes: int = 0, 
                 operation: str = "downloading"):
        self.rom = rom
        self.current_bytes = current_bytes
        self.total_bytes = total_bytes
        self.percentage = 0.0
        self.speed = 0.0  # bytes per second
        self.eta = 0  # estimated time remaining in seconds
        self.operation = operation  # "downloading" or "copying"
        
        if total_bytes > 0:
            self.percentage = (current_bytes / total_bytes) * 100
    
    def __str__(self):
        operation_text = "Copying" if self.operation == "copying" else "Downloading"
        if self.total_bytes > 0:
            return f"{operation_text} {self.rom.clean_name}: {self.percentage:.1f}% ({self._format_bytes(self.current_bytes)}/{self._format_bytes(self.total_bytes)})"
        else:
            return f"{operation_text} {self.rom.clean_name}: {self._format_bytes(self.current_bytes)}"
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"

class DownloadManager:
    """Manages ROM file downloads with rate limiting and progress tracking."""
    
    def __init__(self, temp_path: str = "./temp_downloads", 
                 delay_min: int = 2, delay_max: int = 5, config_manager=None):
        """Initialize the download manager.
        
        Args:
            temp_path: Temporary directory for downloads.
            delay_min: Minimum delay between downloads in seconds.
            delay_max: Maximum delay between downloads in seconds.
            config_manager: Configuration manager for platform settings.
        """
        self.temp_path = Path(temp_path)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.config_manager = config_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Network handler will be initialized when needed with the correct path
        self.network_handler = None
        
        # Ensure temp directory exists
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        # Download state
        self.is_downloading = False
        self.current_download = None
        self.cancelled = False
        
        # Network copy queue and threading
        self.copy_queue = queue.Queue()
        self.copy_thread = None
        self.copy_thread_running = False
        self.copy_progress_callback = None
        self.current_copy_item = None
        self.max_queue_size = 2  # Allow up to 2 items in queue before pausing downloads
    
    def _copy_worker(self):
        """Worker thread for processing network copy queue."""
        logger.info("Copy worker thread started")
        
        while self.copy_thread_running:
            try:
                # Get next item from queue with timeout
                try:
                    item = self.copy_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                if item is None:  # Shutdown signal
                    break
                
                self.current_copy_item = item
                logger.info(f"Starting network copy: {item.rom.clean_name}")
                
                # Perform the copy with progress tracking
                success = self._perform_network_copy(item)
                
                if success:
                    logger.info(f"Successfully copied to network: {item.rom.clean_name}")
                else:
                    logger.error(f"Failed to copy to network: {item.rom.clean_name}")
                
                self.copy_queue.task_done()
                self.current_copy_item = None
                
            except Exception as e:
                logger.error(f"Error in copy worker: {e}")
                if self.current_copy_item:
                    self.copy_queue.task_done()
                    self.current_copy_item = None
        
        logger.info("Copy worker thread stopped")
    
    def _perform_network_copy(self, item: CopyQueueItem) -> bool:
        """Perform network copy with progress tracking."""
        try:
            def copy_progress_callback(bytes_copied, total_bytes, filename):
                if self.copy_progress_callback:
                    copy_progress = DownloadProgress(
                        item.rom, bytes_copied, total_bytes, operation="copying"
                    )
                    self.copy_progress_callback(copy_progress)
            
            # Copy with progress tracking
            file_size = item.src_file.stat().st_size
            copied_bytes = 0
            buffer_size = 64 * 1024  # 64KB buffer
            
            with open(item.src_file, 'rb') as src_f, open(item.dst_file, 'wb') as dst_f:
                while True:
                    buffer = src_f.read(buffer_size)
                    if not buffer:
                        break
                    
                    dst_f.write(buffer)
                    copied_bytes += len(buffer)
                    
                    # Update progress
                    copy_progress_callback(copied_bytes, file_size, item.src_file.name)
                    
                    # Small delay to allow progress updates to be processed
                    if copied_bytes % (buffer_size * 10) == 0:  # Update every 640KB
                        time.sleep(0.01)
            
            # Copy file metadata
            shutil.copystat(item.src_file, item.dst_file)
            
            # Final progress update
            copy_progress_callback(file_size, file_size, item.src_file.name)
            
            # Remove temp file after successful copy
            item.src_file.unlink(missing_ok=True)
            logger.info(f"Successfully copied to network drive: {item.dst_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying {item.src_file} to {item.dst_file}: {e}")
            return False
    
    def download_roms(self, roms: List[RomInfo], target_directory: Path,
                     progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                     completion_callback: Optional[Callable[[RomInfo, bool, str, Optional[str]], None]] = None,
                     platform_name: str = None) -> None:
        """Download a list of ROMs sequentially.
        
        Args:
            roms: List of ROMs to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            completion_callback: Optional callback for each completed download (rom, success, error, final_file_type).
            platform_name: Name of the platform for configuration lookup.
        """
        if self.is_downloading:
            logger.warning("Download already in progress")
            return
        
        self.is_downloading = True
        self.cancelled = False
        self.copy_progress_callback = progress_callback
        
        # Start copy worker thread if not already running
        if not self.copy_thread_running:
            self.copy_thread_running = True
            self.copy_thread = threading.Thread(target=self._copy_worker, daemon=True)
            self.copy_thread.start()
        
        try:
            logger.info(f"Starting download of {len(roms)} ROMs to {target_directory}")
            
            # Ensure target directory exists
            target_directory.mkdir(parents=True, exist_ok=True)
            
            for i, rom in enumerate(roms):
                if self.cancelled:
                    logger.info("Download cancelled by user")
                    break
                
                # Check if copy queue is full - if so, wait before downloading next ROM
                while self.copy_queue.qsize() >= self.max_queue_size and not self.cancelled:
                    logger.info(f"Copy queue full ({self.copy_queue.qsize()}), waiting before next download...")
                    time.sleep(1)
                
                if self.cancelled:
                    break
                
                logger.info(f"Downloading ROM {i+1}/{len(roms)}: {rom.clean_name}")
                self.current_download = rom
                
                success, error_message, final_file_type = self._download_single_rom(
                    rom, target_directory, progress_callback, platform_name
                )
                
                # Call completion callback if provided
                if completion_callback:
                    completion_callback(rom, success, error_message, final_file_type)
                
                # Add delay between downloads (except for the last one)
                if i < len(roms) - 1 and not self.cancelled:
                    delay = random.randint(self.delay_min, self.delay_max)
                    logger.info(f"Waiting {delay} seconds before next download...")
                    time.sleep(delay)
            
            logger.info("Download session completed")
            
            # Wait for all queued copies to complete
            logger.info("Waiting for network copies to complete...")
            self.copy_queue.join()
            logger.info("All network copies completed")
            
        finally:
            self.is_downloading = False
            self.current_download = None
            
            # Stop copy worker thread
            if self.copy_thread_running:
                self.copy_thread_running = False
                self.copy_queue.put(None)  # Signal thread to stop
                if self.copy_thread and self.copy_thread.is_alive():
                    self.copy_thread.join(timeout=5)
                self.copy_thread = None
    
    def _download_single_rom(self, rom: RomInfo, target_directory: Path,
                           progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                           platform_name: str = None) -> tuple[bool, str, Optional[str]]:
        """Download a single ROM file.
        
        Args:
            rom: ROM to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            platform_name: Name of the platform for configuration lookup.
            
        Returns:
            Tuple of (success, error_message, final_file_type).
        """
        try:
            # Generate filename
            filename = self._sanitize_filename(rom.name)
            temp_file = self.temp_path / filename
            final_file = target_directory / filename
            
            # Check if file already exists
            if final_file.exists():
                logger.info(f"File already exists, skipping: {final_file}")
                return True, "", final_file.suffix.lower()
            
            # Start download
            logger.debug(f"Downloading {rom.url} to {temp_file}")
            
            response = self.session.get(rom.url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get total file size
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        temp_file.unlink(missing_ok=True)
                        return False, "Download cancelled"
                    
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress
                        if progress_callback and total_size > 0:
                            progress = DownloadProgress(rom, downloaded_size, total_size)
                            
                            # Calculate speed and ETA
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                progress.speed = downloaded_size / elapsed
                                if progress.speed > 0:
                                    remaining_bytes = total_size - downloaded_size
                                    progress.eta = remaining_bytes / progress.speed
                            
                            progress_callback(progress)
            
            # Check if we need to extract the archive
            should_extract = (self.config_manager and platform_name and 
                            self.config_manager.should_extract_archives(platform_name))
            
            files_to_move = []
            if should_extract and self._is_archive(temp_file):
                logger.info(f"Extracting archive: {temp_file}")
                # Update progress to show extraction status
                if progress_callback:
                    extract_progress = DownloadProgress(rom, 0, 0, operation="extracting")
                    progress_callback(extract_progress)
                
                extracted_files = self._extract_archive(temp_file, self.temp_path)
                if extracted_files:
                    files_to_move = [(src, target_directory / src.name) for src in extracted_files]
                    # Remove the original archive file
                    temp_file.unlink(missing_ok=True)
                else:
                    # Extraction failed, move the original file
                    files_to_move = [(temp_file, final_file)]
            else:
                # No extraction needed, move original file
                files_to_move = [(temp_file, final_file)]
            
            # Move files to final destination with timeout protection
            for src_file, dst_file in files_to_move:
                # Skip if destination already exists
                if dst_file.exists():
                    logger.info(f"File already exists, skipping: {dst_file}")
                    src_file.unlink(missing_ok=True)
                    continue
                    
                logger.info(f"Moving {src_file} to {dst_file}")
            
            def queue_for_copy(src_file, dst_file, platform_name):
                """Queue file for network copying or copy locally immediately."""
                try:
                    dst_str = str(dst_file)
                    
                    # Check if this is a network destination (mounted network drive)
                    if dst_str.startswith('/mnt/') and 'batocera' in dst_str.lower():
                        # Queue for network copying
                        copy_item = CopyQueueItem(rom, src_file, dst_file, platform_name)
                        self.copy_queue.put(copy_item)
                        logger.info(f"Queued for network copy: {dst_file.name}")
                        return {'success': True, 'error': None}
                        
                    else:
                        # Local copy - use regular move immediately
                        shutil.move(str(src_file), str(dst_file))
                        logger.info(f"Successfully moved to local drive: {dst_file}")
                        return {'success': True, 'error': None}
                        
                except Exception as e:
                    return {'success': False, 'error': str(e)}
            
            # Process all files to move
            all_success = True
            error_messages = []
            final_file_type = None
            
            for src_file, dst_file in files_to_move:
                if dst_file.exists():
                    continue  # Already handled above
                    
                try:
                    copy_result = queue_for_copy(src_file, dst_file, platform_name)
                    
                    if not copy_result['success']:
                        error_msg = f"File transfer failed for {dst_file.name}: {copy_result['error']}"
                        logger.error(error_msg)
                        error_messages.append(error_msg)
                        all_success = False
                        # Clean up temp file on failure
                        src_file.unlink(missing_ok=True)
                    else:
                        # Track the file type of successfully queued files
                        final_file_type = dst_file.suffix.lower()
                    
                except Exception as e:
                    error_msg = f"Unexpected error during file transfer for {dst_file.name}: {e}"
                    logger.error(error_msg)
                    error_messages.append(error_msg)
                    all_success = False
                    src_file.unlink(missing_ok=True)
            
            if not all_success:
                return False, "; ".join(error_messages), final_file_type
            
            logger.info(f"Successfully downloaded: {rom.clean_name}")
            return True, "", final_file_type
            
        except requests.RequestException as e:
            error_msg = f"Network error downloading {rom.clean_name}: {e}"
            logger.error(error_msg)
            temp_file.unlink(missing_ok=True)
            return False, error_msg, None
            
        except Exception as e:
            error_msg = f"Error downloading {rom.clean_name}: {e}"
            logger.error(error_msg)
            temp_file.unlink(missing_ok=True)
            return False, error_msg, None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.
        
        Args:
            filename: Original filename.
            
        Returns:
            Sanitized filename.
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = filename
        
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove multiple consecutive underscores
        while '__' in sanitized:
            sanitized = sanitized.replace('__', '_')
        
        # Trim and ensure reasonable length
        sanitized = sanitized.strip('_. ')
        if len(sanitized) > 200:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:200-len(ext)] + ext
        
        return sanitized
    
    def _is_archive(self, file_path: Path) -> bool:
        """Check if a file is an archive that can be extracted.
        
        Args:
            file_path: Path to the file to check.
            
        Returns:
            True if the file is an extractable archive, False otherwise.
        """
        return file_path.suffix.lower() in ['.zip', '.7z']
    
    def _extract_archive(self, archive_path: Path, extract_to: Path) -> List[Path]:
        """Extract an archive file.
        
        Args:
            archive_path: Path to the archive file.
            extract_to: Directory to extract files to.
            
        Returns:
            List of extracted file paths, empty list if extraction failed.
        """
        extracted_files = []
        
        try:
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        # Skip directories and hidden files
                        if not member.endswith('/') and not member.startswith('.'):
                            # Extract to temp directory
                            extracted_path = zip_ref.extract(member, extract_to)
                            extracted_files.append(Path(extracted_path))
                            logger.debug(f"Extracted: {member}")
                            
            elif archive_path.suffix.lower() == '.7z':
                with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                    archive.extractall(path=extract_to)
                    # Get list of extracted files
                    for member in archive.getnames():
                        if not member.endswith('/') and not member.startswith('.'):
                            extracted_files.append(extract_to / member)
                            logger.debug(f"Extracted: {member}")
                            
            logger.info(f"Successfully extracted {len(extracted_files)} files from {archive_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to extract {archive_path}: {e}")
            # Clean up any partially extracted files
            for file_path in extracted_files:
                file_path.unlink(missing_ok=True)
            extracted_files = []
        
        return extracted_files
    
    def cancel_download(self) -> None:
        """Cancel the current download session."""
        logger.info("Cancelling download session...")
        self.cancelled = True
        
        # Stop copy worker thread
        if self.copy_thread_running:
            self.copy_thread_running = False
            self.copy_queue.put(None)  # Signal thread to stop
    
    def get_download_status(self) -> dict:
        """Get current download status.
        
        Returns:
            Dictionary with download status information.
        """
        return {
            'is_downloading': self.is_downloading,
            'current_rom': self.current_download.clean_name if self.current_download else None,
            'cancelled': self.cancelled,
            'copy_queue_size': self.copy_queue.qsize(),
            'current_copy': self.current_copy_item.rom.clean_name if self.current_copy_item else None,
            'copy_thread_running': self.copy_thread_running
        }
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary download files."""
        try:
            if self.temp_path.exists():
                for file_path in self.temp_path.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")