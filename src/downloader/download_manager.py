"""
Download Manager for ROM Files
Handles downloading ROM files with delays and progress tracking.
"""

import os
import time
import random
import logging
import shutil
from typing import List, Callable, Optional
from pathlib import Path
import requests
from urllib.parse import urlparse

# Import RomInfo from scraper module
import sys
sys.path.append(str(Path(__file__).parent.parent))
from scraper.web_scraper import RomInfo

logger = logging.getLogger(__name__)

class DownloadProgress:
    """Represents download progress information."""
    
    def __init__(self, rom: RomInfo, current_bytes: int = 0, total_bytes: int = 0):
        self.rom = rom
        self.current_bytes = current_bytes
        self.total_bytes = total_bytes
        self.percentage = 0.0
        self.speed = 0.0  # bytes per second
        self.eta = 0  # estimated time remaining in seconds
        
        if total_bytes > 0:
            self.percentage = (current_bytes / total_bytes) * 100
    
    def __str__(self):
        if self.total_bytes > 0:
            return f"{self.rom.clean_name}: {self.percentage:.1f}% ({self._format_bytes(self.current_bytes)}/{self._format_bytes(self.total_bytes)})"
        else:
            return f"{self.rom.clean_name}: {self._format_bytes(self.current_bytes)}"
    
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
                 delay_min: int = 2, delay_max: int = 5):
        """Initialize the download manager.
        
        Args:
            temp_path: Temporary directory for downloads.
            delay_min: Minimum delay between downloads in seconds.
            delay_max: Maximum delay between downloads in seconds.
        """
        self.temp_path = Path(temp_path)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Ensure temp directory exists
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        # Download state
        self.is_downloading = False
        self.current_download = None
        self.cancelled = False
    
    def download_roms(self, roms: List[RomInfo], target_directory: Path,
                     progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                     completion_callback: Optional[Callable[[RomInfo, bool, str], None]] = None) -> None:
        """Download a list of ROMs sequentially.
        
        Args:
            roms: List of ROMs to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            completion_callback: Optional callback for each completed download.
        """
        if self.is_downloading:
            logger.warning("Download already in progress")
            return
        
        self.is_downloading = True
        self.cancelled = False
        
        try:
            logger.info(f"Starting download of {len(roms)} ROMs to {target_directory}")
            
            # Ensure target directory exists
            target_directory.mkdir(parents=True, exist_ok=True)
            
            for i, rom in enumerate(roms):
                if self.cancelled:
                    logger.info("Download cancelled by user")
                    break
                
                logger.info(f"Downloading ROM {i+1}/{len(roms)}: {rom.clean_name}")
                self.current_download = rom
                
                success, error_message = self._download_single_rom(
                    rom, target_directory, progress_callback
                )
                
                # Call completion callback if provided
                if completion_callback:
                    completion_callback(rom, success, error_message)
                
                # Add delay between downloads (except for the last one)
                if i < len(roms) - 1 and not self.cancelled:
                    delay = random.randint(self.delay_min, self.delay_max)
                    logger.info(f"Waiting {delay} seconds before next download...")
                    time.sleep(delay)
            
            logger.info("Download session completed")
            
        finally:
            self.is_downloading = False
            self.current_download = None
    
    def _download_single_rom(self, rom: RomInfo, target_directory: Path,
                           progress_callback: Optional[Callable[[DownloadProgress], None]] = None) -> tuple[bool, str]:
        """Download a single ROM file.
        
        Args:
            rom: ROM to download.
            target_directory: Final destination directory.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Tuple of (success, error_message).
        """
        try:
            # Generate filename
            filename = self._sanitize_filename(rom.name)
            temp_file = self.temp_path / filename
            final_file = target_directory / filename
            
            # Check if file already exists
            if final_file.exists():
                logger.info(f"File already exists, skipping: {final_file}")
                return True, ""
            
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
            
            # Move file to final destination
            logger.debug(f"Moving {temp_file} to {final_file}")
            shutil.move(str(temp_file), str(final_file))
            
            logger.info(f"Successfully downloaded: {rom.clean_name}")
            return True, ""
            
        except requests.RequestException as e:
            error_msg = f"Network error downloading {rom.clean_name}: {e}"
            logger.error(error_msg)
            temp_file.unlink(missing_ok=True)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Error downloading {rom.clean_name}: {e}"
            logger.error(error_msg)
            temp_file.unlink(missing_ok=True)
            return False, error_msg
    
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
    
    def cancel_download(self) -> None:
        """Cancel the current download session."""
        logger.info("Cancelling download session...")
        self.cancelled = True
    
    def get_download_status(self) -> dict:
        """Get current download status.
        
        Returns:
            Dictionary with download status information.
        """
        return {
            'is_downloading': self.is_downloading,
            'current_rom': self.current_download.clean_name if self.current_download else None,
            'cancelled': self.cancelled
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