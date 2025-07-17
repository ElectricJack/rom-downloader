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
import subprocess
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
        operation_map = {
            "copying": "Copying",
            "downloading": "Downloading", 
            "extracting": "Extracting",
            "extracted": "Extracted",
            "converting": "Converting to CHD",
            "converted": "Converted to CHD"
        }
        operation_text = operation_map.get(self.operation, "Processing")
        
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
        self.copy_completion_callback = None
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
                    # Notify GUI that copy is complete
                    if self.copy_completion_callback:
                        self.copy_completion_callback(item.rom, True, "")
                else:
                    logger.error(f"Failed to copy to network: {item.rom.clean_name}")
                    # Notify GUI that copy failed
                    if self.copy_completion_callback:
                        self.copy_completion_callback(item.rom, False, "Copy failed")
                
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
                     platform_name: str = None,
                     copy_completion_callback: Optional[Callable[[RomInfo, bool, str], None]] = None) -> None:
        """Download a list of ROMs sequentially.
        
        Args:
            roms: List of ROMs to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            completion_callback: Optional callback for each completed download (rom, success, error, final_file_type).
            platform_name: Name of the platform for configuration lookup.
            copy_completion_callback: Optional callback for when copies complete (rom, success, error).
        """
        if self.is_downloading:
            logger.warning("Download already in progress")
            return
        
        self.is_downloading = True
        self.cancelled = False
        self.copy_progress_callback = progress_callback
        self.copy_completion_callback = copy_completion_callback
        
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
        """Download a single ROM file or folder.
        
        Args:
            rom: ROM to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            platform_name: Name of the platform for configuration lookup.
            
        Returns:
            Tuple of (success, error_message, final_file_type).
        """
        try:
            # Handle folder downloads (MAME-style)
            if rom.is_folder:
                return self._download_folder(rom, target_directory, progress_callback, platform_name)
            
            # Handle regular file downloads
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
            
            # Final download progress update
            if progress_callback and total_size > 0:
                final_progress = DownloadProgress(rom, downloaded_size, total_size)
                final_progress.percentage = 100.0
                progress_callback(final_progress)
            
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
                    
                    # Update progress to show extraction completed with final extracted size
                    if progress_callback and extracted_files:
                        total_extracted_size = sum(f.stat().st_size for f in extracted_files)
                        extract_complete_progress = DownloadProgress(rom, total_extracted_size, total_extracted_size, operation="extracted")
                        progress_callback(extract_complete_progress)
                else:
                    # Extraction failed, move the original file
                    files_to_move = [(temp_file, final_file)]
            else:
                # No extraction needed, move original file
                files_to_move = [(temp_file, final_file)]
            
            # CHD conversion step - convert eligible files before network copy
            converted_files = []
            
            # Check if we have CUE files - if so, ONLY process CUE files and skip ALL BIN files
            cue_files = [src for src, dst in files_to_move if src.suffix.lower() == '.cue']
            bin_files = [src for src, dst in files_to_move if src.suffix.lower() == '.bin']
            
            if cue_files:
                logger.info(f"CUE files detected ({len(cue_files)} CUE, {len(bin_files)} BIN) - processing ONLY CUE files")
                
                # Track which BIN files to clean up after successful CHD conversion
                bin_files_to_cleanup = []
                
                for src_file, dst_file in files_to_move:
                    # Skip if destination already exists
                    if dst_file.exists():
                        logger.info(f"File already exists, skipping: {dst_file}")
                        src_file.unlink(missing_ok=True)
                        continue
                    
                    if src_file.suffix.lower() == '.cue':
                        # Process CUE file for CHD conversion
                        logger.info(f"Processing CUE file for CHD conversion: {src_file.name}")
                        
                        # Collect associated BIN files for cleanup AFTER conversion
                        for bin_src, bin_dst in files_to_move:
                            if bin_src.suffix.lower() == '.bin':
                                bin_files_to_cleanup.append(bin_src)
                        
                        chd_file = self._convert_to_chd(src_file, platform_name, progress_callback, rom)
                        if chd_file:
                            # CHD conversion successful - clean up source files now
                            logger.info(f"CHD conversion successful, cleaning up CUE file and {len(bin_files_to_cleanup)} BIN files")
                            
                            # Clean up the CUE file
                            src_file.unlink(missing_ok=True)
                            logger.info(f"Cleaned up CUE file: {src_file.name}")
                            
                            # Clean up BIN files
                            for bin_file in bin_files_to_cleanup:
                                if bin_file.exists():
                                    bin_file.unlink(missing_ok=True)
                                    logger.info(f"Cleaned up BIN file: {bin_file.name}")
                            
                            # Update destination to CHD file
                            chd_dst_file = dst_file.parent / chd_file.name
                            converted_files.append((chd_file, chd_dst_file))
                            logger.info(f"Converted CUE to CHD: {chd_file.name}")
                        else:
                            # No conversion, use original CUE file and include BIN files
                            converted_files.append((src_file, dst_file))
                            logger.info(f"Moving CUE file (no conversion): {src_file} to {dst_file}")
                            
                            # Include BIN files since CHD conversion failed
                            for bin_src, bin_dst in files_to_move:
                                if bin_src.suffix.lower() == '.bin':
                                    converted_files.append((bin_src, bin_dst))
                                    logger.info(f"Including BIN file (CHD conversion failed): {bin_src} to {bin_dst}")
                    
                    elif src_file.suffix.lower() == '.bin':
                        # Skip BIN files during processing - they'll be handled by CUE conversion or cleanup
                        logger.info(f"Skipping BIN file (will be processed with CUE): {src_file.name}")
                        continue
                    
                    else:
                        # Process other file types normally
                        chd_file = self._convert_to_chd(src_file, platform_name, progress_callback, rom)
                        if chd_file:
                            chd_dst_file = dst_file.parent / chd_file.name
                            converted_files.append((chd_file, chd_dst_file))
                            logger.info(f"Converted to CHD: {chd_file.name}")
                        else:
                            converted_files.append((src_file, dst_file))
                            logger.info(f"Moving {src_file} to {dst_file}")
            
            else:
                # No CUE files - process all files normally (including standalone BIN files)
                logger.info(f"No CUE files detected - processing all files normally")
                for src_file, dst_file in files_to_move:
                    # Skip if destination already exists
                    if dst_file.exists():
                        logger.info(f"File already exists, skipping: {dst_file}")
                        src_file.unlink(missing_ok=True)
                        continue
                    
                    # Try CHD conversion if platform supports it
                    chd_file = self._convert_to_chd(src_file, platform_name, progress_callback, rom)
                    if chd_file:
                        # Update destination to CHD file
                        chd_dst_file = dst_file.parent / chd_file.name
                        converted_files.append((chd_file, chd_dst_file))
                        logger.info(f"Converted to CHD: {chd_file.name}")
                    else:
                        # No conversion, use original file
                        converted_files.append((src_file, dst_file))
                        logger.info(f"Moving {src_file} to {dst_file}")
            
            # Update files_to_move with converted files
            files_to_move = converted_files
            
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
    
    def _download_folder(self, rom: RomInfo, target_directory: Path,
                        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                        platform_name: str = None) -> tuple[bool, str, Optional[str]]:
        """Download all files in a folder (MAME-style ROM collection).
        
        Args:
            rom: ROM folder to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            platform_name: Name of the platform for configuration lookup.
            
        Returns:
            Tuple of (success, error_message, final_file_type).
        """
        try:
            # Create folder name based on ROM name
            folder_name = self._sanitize_filename(rom.name)
            target_folder = target_directory / folder_name
            
            # Check if folder already exists
            if target_folder.exists() and any(target_folder.iterdir()):
                logger.info(f"Folder already exists and contains files, skipping: {target_folder}")
                return True, "", "FOLDER"
            
            # Create target folder
            target_folder.mkdir(parents=True, exist_ok=True)
            
            # Import web scraper to get folder contents
            from scraper.web_scraper import WebScraper
            scraper = WebScraper()
            
            # Get list of files in the folder
            folder_files = scraper.get_folder_contents(rom.url)
            
            if not folder_files:
                logger.warning(f"No files found in folder: {rom.url}")
                return False, "No files found in folder", None
            
            logger.info(f"Found {len(folder_files)} files in folder {rom.name}")
            
            # Download each file in the folder
            successful_downloads = 0
            total_files = len(folder_files)
            
            for i, file_rom in enumerate(folder_files):
                if self.cancelled:
                    logger.info("Download cancelled by user")
                    break
                
                # Update progress for folder download
                if progress_callback:
                    folder_progress = DownloadProgress(
                        rom, i, total_files,
                        operation=f"downloading ({i+1}/{total_files})"
                    )
                    progress_callback(folder_progress)
                
                # Download individual file
                filename = self._sanitize_filename(file_rom.name)
                temp_file = self.temp_path / filename
                final_file = target_folder / filename
                
                # Skip if file already exists
                if final_file.exists():
                    logger.info(f"File already exists, skipping: {final_file}")
                    successful_downloads += 1
                    continue
                
                try:
                    # Download the file
                    response = self.session.get(file_rom.url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Get total file size
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(temp_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.cancelled:
                                temp_file.unlink(missing_ok=True)
                                return False, "Download cancelled", None
                            
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                    
                    # Move file to target folder or queue for network copy
                    dst_str = str(final_file)
                    if dst_str.startswith('/mnt/') and 'batocera' in dst_str.lower():
                        # Queue for network copy
                        copy_item = CopyQueueItem(file_rom, temp_file, final_file, platform_name)
                        self.copy_queue.put(copy_item)
                        logger.info(f"Queued for network copy: {final_file}")
                    else:
                        # Direct copy to local target
                        shutil.move(str(temp_file), str(final_file))
                        logger.info(f"Moved to local target: {final_file}")
                    
                    successful_downloads += 1
                    logger.info(f"Downloaded file {i+1}/{total_files}: {file_rom.name}")
                    
                except Exception as file_error:
                    logger.error(f"Error downloading file {file_rom.name}: {file_error}")
                    # Continue with other files
                    temp_file.unlink(missing_ok=True)
            
            # Final progress update
            if progress_callback:
                final_progress = DownloadProgress(
                    rom, successful_downloads, total_files,
                    operation=f"completed ({successful_downloads}/{total_files})"
                )
                progress_callback(final_progress)
            
            if successful_downloads == 0:
                return False, "No files were downloaded successfully", None
            elif successful_downloads < total_files:
                return True, f"Partially successful: {successful_downloads}/{total_files} files downloaded", "FOLDER"
            else:
                return True, "", "FOLDER"
                
        except Exception as e:
            logger.error(f"Error downloading folder {rom.clean_name}: {e}")
            return False, str(e), None
    
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
    
    def _convert_to_chd(self, source_file: Path, platform_name: str, 
                       progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                       rom: Optional[RomInfo] = None) -> Optional[Path]:
        """Convert a ROM file to CHD format using chdman.exe.
        
        Args:
            source_file: Path to the source ROM file.
            platform_name: Name of the platform for CHD format detection.
            progress_callback: Optional callback for progress updates.
            rom: ROM info for progress updates.
            
        Returns:
            Path to the converted CHD file, or None if conversion failed.
        """
        logger.info(f"CHD conversion check: platform={platform_name}, file={source_file.name}")
        
        # Check if conversion is needed and supported
        if not self.config_manager:
            logger.info("CHD conversion skipped: no config manager")
            return None
            
        if not self.config_manager.supports_chd(platform_name):
            logger.info(f"CHD conversion skipped: platform {platform_name} does not support CHD")
            return None
            
        # Skip if already CHD format
        if source_file.suffix.lower() == '.chd':
            logger.info(f"CHD conversion skipped: {source_file.name} is already CHD format")
            return None
            
        # Check if file format is convertible to CHD
        convertible_extensions = ['.bin', '.cue', '.iso', '.cdi', '.gdi']
        if source_file.suffix.lower() not in convertible_extensions:
            logger.info(f"CHD conversion skipped: {source_file.suffix} is not convertible to CHD")
            return None
            
        # Find chdman.exe in tools folder
        tools_path = Path(__file__).parent.parent.parent / "tools"
        chdman_path = tools_path / "chdman.exe"
        
        logger.info(f"CHD conversion starting: looking for chdman.exe at {chdman_path}")
        
        if not chdman_path.exists():
            logger.warning(f"chdman.exe not found at {chdman_path}, skipping CHD conversion")
            return None
            
        # Generate CHD output filename
        chd_file = source_file.parent / f"{source_file.stem}.chd"
        
        logger.info(f"CHD conversion: source={source_file}, output={chd_file}")
        logger.info(f"CHD conversion: source file size={source_file.stat().st_size} bytes")
        
        try:
            logger.info(f"Converting {source_file.name} to CHD format...")
            
            # Update progress to show conversion status
            if progress_callback and rom:
                convert_progress = DownloadProgress(rom, 0, 0, operation="converting")
                progress_callback(convert_progress)
            
            # Determine chdman command based on file type
            cmd = None
            if source_file.suffix.lower() == '.cue':
                # For CUE files, use createcd command
                cmd = [str(chdman_path), "createcd", "-i", str(source_file), "-o", str(chd_file)]
                logger.info("CHD conversion: using createcd command for CUE file")
            elif source_file.suffix.lower() in ['.iso', '.bin']:
                # For ISO/BIN files, try createcd first (for CD images), fallback to createdvd
                cmd = [str(chdman_path), "createcd", "-i", str(source_file), "-o", str(chd_file)]
                logger.info("CHD conversion: using createcd command for ISO/BIN file")
            elif source_file.suffix.lower() in ['.cdi', '.gdi']:
                # For CDI/GDI files, use createcd
                cmd = [str(chdman_path), "createcd", "-i", str(source_file), "-o", str(chd_file)]
                logger.info("CHD conversion: using createcd command for CDI/GDI file")
            else:
                logger.warning(f"Unsupported file type for CHD conversion: {source_file.suffix}")
                return None
            
            # Run chdman conversion
            logger.info(f"CHD conversion: executing command: {' '.join(cmd)}")
            logger.info(f"CHD conversion: working directory: {os.getcwd()}")
            logger.info(f"CHD conversion: timeout set to 1800 seconds (30 minutes)")
            
            start_time = time.time()
            
            # Run with real-time output logging
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            logger.info(f"CHD conversion: process started with PID {process.pid}")
            
            # Monitor process with periodic updates
            stdout_lines = []
            stderr_lines = []
            last_update = time.time()
            
            while process.poll() is None:
                # Check for timeout
                if time.time() - start_time > 1800:  # 30 minutes
                    logger.error("CHD conversion: timeout reached, terminating process")
                    process.terminate()
                    time.sleep(5)
                    if process.poll() is None:
                        logger.error("CHD conversion: process didn't terminate, killing it")
                        process.kill()
                    raise subprocess.TimeoutExpired(cmd, 1800)
                
                # Read available output
                try:
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        stdout_lines.append(stdout_line.strip())
                        logger.debug(f"CHD conversion stdout: {stdout_line.strip()}")
                    
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        stderr_lines.append(stderr_line.strip())
                        logger.debug(f"CHD conversion stderr: {stderr_line.strip()}")
                        
                except:
                    pass
                
                # Periodic status update
                current_time = time.time()
                if current_time - last_update >= 10:  # Every 10 seconds
                    elapsed = current_time - start_time
                    logger.info(f"CHD conversion: still running... elapsed time: {elapsed:.1f}s")
                    
                    # Check if output file is being created/growing
                    if chd_file.exists():
                        chd_size = chd_file.stat().st_size
                        logger.info(f"CHD conversion: output file size: {chd_size} bytes")
                        
                        # Update progress if we have a callback
                        if progress_callback and rom:
                            convert_progress = DownloadProgress(rom, chd_size, chd_size, operation="converting")
                            progress_callback(convert_progress)
                    
                    last_update = current_time
                
                time.sleep(0.1)  # Small delay to prevent busy waiting
            
            # Get final output
            remaining_stdout, remaining_stderr = process.communicate()
            if remaining_stdout:
                stdout_lines.extend(remaining_stdout.strip().split('\n'))
            if remaining_stderr:
                stderr_lines.extend(remaining_stderr.strip().split('\n'))
            
            returncode = process.returncode
            stdout_text = '\n'.join(stdout_lines)
            stderr_text = '\n'.join(stderr_lines)
            
            elapsed_time = time.time() - start_time
            logger.info(f"CHD conversion: process completed in {elapsed_time:.1f}s with return code {returncode}")
            
            if returncode == 0:
                logger.info(f"Successfully converted {source_file.name} to CHD format")
                
                if chd_file.exists():
                    chd_size = chd_file.stat().st_size
                    logger.info(f"CHD conversion: output file size: {chd_size} bytes")
                else:
                    logger.error("CHD conversion: output file does not exist despite successful return code")
                    return None
                
                # Update progress to show conversion completed
                if progress_callback and rom:
                    convert_complete_progress = DownloadProgress(rom, chd_size, chd_size, operation="converted")
                    progress_callback(convert_complete_progress)
                
                # Note: Source file cleanup is now handled by the caller
                logger.info(f"CHD conversion: source file {source_file} will be cleaned up by caller")
                
                return chd_file
                
            else:
                logger.error(f"CHD conversion failed for {source_file.name} with return code {returncode}")
                logger.error(f"CHD conversion stdout: {stdout_text}")
                logger.error(f"CHD conversion stderr: {stderr_text}")
                
                # If createcd failed for ISO/BIN, try createdvd
                if source_file.suffix.lower() in ['.iso', '.bin'] and 'createcd' in cmd:
                    logger.info("CHD conversion: retrying with createdvd command...")
                    cmd_dvd = [str(chdman_path), "createdvd", "-i", str(source_file), "-o", str(chd_file)]
                    logger.info(f"CHD conversion: executing DVD command: {' '.join(cmd_dvd)}")
                    
                    # Clean up failed CHD file before retry
                    if chd_file.exists():
                        chd_file.unlink(missing_ok=True)
                    
                    start_time = time.time()
                    result = subprocess.run(
                        cmd_dvd,
                        capture_output=True,
                        text=True,
                        timeout=1800
                    )
                    elapsed_time = time.time() - start_time
                    logger.info(f"CHD conversion (DVD): completed in {elapsed_time:.1f}s with return code {result.returncode}")
                    
                    if result.returncode == 0:
                        logger.info(f"Successfully converted {source_file.name} to CHD format using createdvd")
                        
                        if chd_file.exists():
                            chd_size = chd_file.stat().st_size
                            logger.info(f"CHD conversion (DVD): output file size: {chd_size} bytes")
                        
                        # Update progress to show conversion completed
                        if progress_callback and rom:
                            convert_complete_progress = DownloadProgress(rom, chd_size, chd_size, operation="converted")
                            progress_callback(convert_complete_progress)
                        
                        # Note: Source file cleanup is now handled by the caller
                        logger.info(f"CHD conversion (DVD): source file {source_file} will be cleaned up by caller")
                        return chd_file
                    else:
                        logger.error(f"CHD conversion with createdvd also failed for {source_file.name}")
                        logger.error(f"CHD conversion (DVD) stdout: {result.stdout}")
                        logger.error(f"CHD conversion (DVD) stderr: {result.stderr}")
                
                # Clean up failed CHD file
                if chd_file.exists():
                    logger.info(f"CHD conversion: cleaning up failed output file {chd_file}")
                    chd_file.unlink(missing_ok=True)
                
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"CHD conversion timed out for {source_file.name} after 30 minutes")
            if chd_file.exists():
                logger.info(f"CHD conversion: cleaning up timeout output file {chd_file}")
                chd_file.unlink(missing_ok=True)
            return None
            
        except Exception as e:
            logger.error(f"Error during CHD conversion for {source_file.name}: {e}")
            logger.exception("CHD conversion exception details:")
            if chd_file.exists():
                logger.info(f"CHD conversion: cleaning up error output file {chd_file}")
                chd_file.unlink(missing_ok=True)
            return None
    
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