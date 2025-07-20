"""
Web Scraper for ROM Download Sites
Handles scraping ROM download pages to enumerate available files.
"""

import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class RomInfo:
    """Represents information about a ROM file."""
    
    def __init__(self, name: str, url: str, size: str = "", file_type: str = "", is_folder: bool = False):
        self.name = unquote(name)
        self.url = url
        self.size = size
        self.file_type = file_type
        self.is_folder = is_folder
        self.region = self._extract_region()
        self.clean_name = self._clean_name()
    
    def _extract_region(self) -> str:
        """Extract region information from the ROM name."""
        # Common region patterns
        region_patterns = {
            r'\(USA?\)': 'USA',
            r'\(US\)': 'USA', 
            r'\(Europe?\)': 'Europe',
            r'\(Japan\)': 'Japan',
            r'\(World\)': 'World',
            r'\(En\)': 'English',
            r'\(English\)': 'English'
        }
        
        for pattern, region in region_patterns.items():
            if re.search(pattern, self.name, re.IGNORECASE):
                return region
        
        return 'Unknown'
    
    def _clean_name(self) -> str:
        """Clean the ROM name for display purposes."""
        # Remove file extensions (all supported ROM and archive formats)
        clean = re.sub(r'\.(rvz|zip|7z|iso|bin|cue|chd|gcm|nes|sfc|smc|gba|gbc|gb|nds|n64|z64|v64|vb|pce|a26|a52|a78|cdi|gdi|wux|wud)$', '', self.name, flags=re.IGNORECASE)
        
        # Remove common prefixes/suffixes but keep region info
        clean = re.sub(r'^\[.*?\]\s*', '', clean)  # Remove [tags] at start
        # Remove non-region parenthetical info (keep region patterns)
        region_patterns = [r'\(USA?\)', r'\(US\)', r'\(Europe?\)', r'\(Japan\)', r'\(World\)', r'\(En\)', r'\(English\)']
        has_region = any(re.search(pattern, clean, re.IGNORECASE) for pattern in region_patterns)
        
        if not has_region:
            # Only remove parentheses if no region found
            clean = re.sub(r'\s*\(.*?\)$', '', clean)
        
        return clean.strip()
    
    def __str__(self):
        return f"{self.clean_name} ({self.region}) - {self.size}"
    
    def __repr__(self):
        return f"RomInfo(name='{self.name}', region='{self.region}', size='{self.size}')"

class WebScraper:
    """Web scraper for ROM download sites."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def scrape_roms(self, url: str, file_pattern: str = None, _folder_mode: bool = False) -> List[RomInfo]:
        """Scrape ROM files from a given URL.
        
        Args:
            url: URL to scrape for ROM files.
            file_pattern: Regex pattern to match file names.
            folder_mode: If True, treat folders as ROM collections (for MAME-style archives).
            
        Returns:
            List of RomInfo objects representing found ROMs.
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Scraping ROMs from: {url}")
            logger.info(f"Using file pattern: {file_pattern}")
            
            request_start = time.time()
            response = self.session.get(url, timeout=30)
            request_time = time.time() - request_start
            logger.info(f"HTTP request completed in {request_time:.2f}s, status: {response.status_code}")
            
            response.raise_for_status()
            
            parse_start = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            parse_time = time.time() - parse_start
            logger.info(f"HTML parsing completed in {parse_time:.2f}s")
            
            roms = []
            
            # Look for file links - common patterns for directory listings
            links_start = time.time()
            file_links = soup.find_all('a', href=True)
            links_time = time.time() - links_start
            logger.info(f"Found {len(file_links)} links in {links_time:.2f}s")
            
            processed_count = 0
            matched_count = 0
            
            for i, link in enumerate(file_links):
                if i % 100 == 0 and i > 0:  # Log progress every 100 links
                    logger.info(f"Processed {i}/{len(file_links)} links, found {matched_count} matches so far")
                
                href = link.get('href')
                if not href or href.startswith('../') or href == '/':
                    continue
                
                processed_count += 1
                
                # Get the full URL
                full_url = urljoin(url, href)
                
                # Extract file name from href or link text
                file_name = href.strip('/')
                if not file_name:
                    file_name = link.get_text().strip()
                
                # Skip directories
                if href.endswith('/'):
                    continue
                
                # Apply file pattern filter if provided
                if file_pattern:
                    if not re.search(file_pattern, file_name, re.IGNORECASE):
                        continue
                
                matched_count += 1
                
                # Extract file size if available
                size_text = ""
                # Look for size information in the same row or nearby
                parent = link.parent
                if parent:
                    size_match = re.search(r'(\d+(?:\.\d+)?\s*[KMGT]?B)', parent.get_text())
                    if size_match:
                        size_text = size_match.group(1)
                
                # Determine file type
                file_type = ""
                if '.' in file_name:
                    file_type = file_name.split('.')[-1].upper()
                
                rom_info = RomInfo(
                    name=file_name,
                    url=full_url,
                    size=size_text,
                    file_type=file_type
                )
                
                roms.append(rom_info)
                if len(roms) <= 10:  # Log first 10 ROMs found
                    logger.info(f"Found ROM: {rom_info.clean_name} ({rom_info.size}, {rom_info.file_type})")
            
            total_time = time.time() - start_time
            logger.info(f"Scraping completed in {total_time:.2f}s - processed {processed_count} files, found {len(roms)} ROM files")
            return roms
            
        except requests.RequestException as e:
            logger.error(f"Network error scraping URL {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error scraping URL {url}: {e}", exc_info=True)
            return []
    
    def test_connection(self, url: str) -> bool:
        """Test if we can connect to the given URL.
        
        Args:
            url: URL to test connection to.
            
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed for {url}: {e}")
            return False
    
    def get_file_info(self, url: str) -> Optional[Dict[str, str]]:
        """Get file information from a direct file URL.
        
        Args:
            url: Direct URL to a file.
            
        Returns:
            Dictionary with file information or None if error.
        """
        try:
            response = self.session.head(url, timeout=10)
            if response.status_code == 200:
                return {
                    'size': response.headers.get('Content-Length', '0'),
                    'content_type': response.headers.get('Content-Type', ''),
                    'last_modified': response.headers.get('Last-Modified', '')
                }
        except Exception as e:
            logger.error(f"Error getting file info for {url}: {e}")
        
        return None
    
