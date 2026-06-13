"""
Network Drive Handler
Handles network drive connectivity and fallback to local storage.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple, Callable, List
import threading
import time

logger = logging.getLogger(__name__)

class NetworkHandler:
    """Handles network drive operations with local fallback."""
    
    def __init__(self, network_path: str, local_fallback_path: str = "./local_roms"):
        """Initialize the network handler.
        
        Args:
            network_path: Network drive path (e.g., //BATOCERA/share/roms).
            local_fallback_path: Local path to use if network is unavailable.
        """
        self.network_path = Path(network_path)
        self.local_fallback_path = Path(local_fallback_path)
        self.use_network = False
        self.current_base_path = None
        
        self.check_network_availability()
    
    def check_network_availability(self) -> bool:
        """Check if the network drive is available.
        
        Returns:
            True if network drive is accessible, False otherwise.
        """
        try:
            # Try to access the network path
            if self.network_path.exists() and self.network_path.is_dir():
                # Try to create a test file to verify write access
                test_file = self.network_path / "rom_downloader_test.tmp"
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    test_file.unlink()  # Clean up test file
                    
                    self.use_network = True
                    self.current_base_path = self.network_path
                    logger.info(f"Network drive available: {self.network_path}")
                    return True
                    
                except Exception as e:
                    logger.warning(f"Network drive exists but not writable: {e}")
                    
        except Exception as e:
            logger.warning(f"Network drive not accessible: {e}")
        
        # Fall back to local storage
        self.use_network = False
        self.current_base_path = self.local_fallback_path
        self.local_fallback_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using local fallback path: {self.local_fallback_path}")
        return False
    
    def get_target_path(self, subfolder: str) -> Path:
        """Get the target path for a specific ROM platform.
        
        Args:
            subfolder: Platform-specific subfolder name.
            
        Returns:
            Full path to the platform directory.
        """
        if self.current_base_path is None:
            self.check_network_availability()
        
        target_path = self.current_base_path / subfolder
        target_path.mkdir(parents=True, exist_ok=True)
        
        return target_path
    
    def is_using_network(self) -> bool:
        """Check if currently using network drive.
        
        Returns:
            True if using network drive, False if using local fallback.
        """
        return self.use_network
    
    def get_current_base_path(self) -> Path:
        """Get the current base path being used.
        
        Returns:
            Current base path (network or local).
        """
        if self.current_base_path is None:
            self.check_network_availability()
        
        return self.current_base_path
    
    def copy_to_network(self, local_file: Path, network_subfolder: str, 
                       progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[bool, str]:
        """Copy a file from local storage to network drive with progress tracking.
        
        Args:
            local_file: Local file to copy.
            network_subfolder: Target subfolder on network drive.
            progress_callback: Optional callback for progress updates (bytes_copied, total_bytes, filename).
            
        Returns:
            Tuple of (success, error_message).
        """
        if not local_file.exists():
            return False, f"Local file does not exist: {local_file}"
        
        try:
            # Check if network is available
            if not self.check_network_availability():
                return False, "Network drive not available"
            
            target_dir = self.network_path / network_subfolder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_file = target_dir / local_file.name
            
            # Copying file to network location
            
            # Get file size for progress tracking
            file_size = local_file.stat().st_size
            
            if progress_callback and file_size > 0:
                # Copy with progress tracking
                self._copy_with_progress(local_file, target_file, progress_callback)
            else:
                # Simple copy for small files or when no callback provided
                shutil.copy2(local_file, target_file)
            
            # Verify copy was successful
            if target_file.exists() and target_file.stat().st_size == local_file.stat().st_size:
                logger.info(f"Successfully copied to network: {target_file}")
                if progress_callback:
                    progress_callback(file_size, file_size, local_file.name)
                return True, ""
            else:
                return False, "Copy verification failed"
                
        except Exception as e:
            error_msg = f"Error copying to network: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def _copy_with_progress(self, src: Path, dst: Path, progress_callback: Callable[[int, int, str], None]):
        """Copy file with progress tracking.
        
        Args:
            src: Source file path.
            dst: Destination file path.
            progress_callback: Callback for progress updates (bytes_copied, total_bytes, filename).
        """
        file_size = src.stat().st_size
        copied_bytes = 0
        buffer_size = 64 * 1024  # 64KB buffer
        
        with open(src, 'rb') as src_file, open(dst, 'wb') as dst_file:
            while True:
                buffer = src_file.read(buffer_size)
                if not buffer:
                    break
                
                dst_file.write(buffer)
                copied_bytes += len(buffer)
                
                # Update progress
                progress_callback(copied_bytes, file_size, src.name)
                
                # Small delay to allow progress updates to be processed
                if copied_bytes % (buffer_size * 10) == 0:  # Update every 640KB
                    time.sleep(0.01)
        
        # Copy file metadata
        shutil.copystat(src, dst)
    
    def sync_local_to_network(self, platform: str, 
                             progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[int, int, List[str]]:
        """Sync local ROM files to network drive.
        
        Args:
            platform: Platform name to sync.
            progress_callback: Optional callback for progress updates (bytes_copied, total_bytes, filename).
            
        Returns:
            Tuple of (successful_copies, failed_copies, error_messages).
        """
        if not self.check_network_availability():
            return 0, 0, ["Network drive not available"]
        
        local_platform_path = self.local_fallback_path / platform
        if not local_platform_path.exists():
            return 0, 0, [f"Local platform directory does not exist: {local_platform_path}"]
        
        successful_copies = 0
        failed_copies = 0
        error_messages = []
        
        try:
            for local_file in local_platform_path.iterdir():
                if local_file.is_file():
                    success, error = self.copy_to_network(local_file, platform, progress_callback)
                    if success:
                        successful_copies += 1
                        # Optionally remove local file after successful copy
                        # local_file.unlink()
                    else:
                        failed_copies += 1
                        error_messages.append(f"{local_file.name}: {error}")
            
            logger.info(f"Sync completed: {successful_copies} successful, {failed_copies} failed")
            
        except Exception as e:
            error_msg = f"Error during sync: {e}"
            logger.error(error_msg)
            error_messages.append(error_msg)
        
        return successful_copies, failed_copies, error_messages
    
    def get_storage_info(self) -> dict:
        """Get information about current storage configuration.
        
        Returns:
            Dictionary with storage information.
        """
        info = {
            'using_network': self.use_network,
            'network_path': str(self.network_path),
            'local_fallback_path': str(self.local_fallback_path),
            'current_base_path': str(self.current_base_path) if self.current_base_path else None,
            'network_available': False,
            'network_writable': False
        }
        
        # Check network availability
        try:
            if self.network_path.exists():
                info['network_available'] = True
                # Test write access
                test_file = self.network_path / "rom_downloader_write_test.tmp"
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    test_file.unlink()
                    info['network_writable'] = True
                except:
                    pass
        except:
            pass
        
        return info