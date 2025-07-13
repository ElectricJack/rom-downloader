"""
Web Scraper for ROM Download Sites
Handles scraping ROM download pages to enumerate available files.
"""

import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, unquote
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class RomInfo:
    """Represents information about a ROM file."""
    
    def __init__(self, name: str, url: str, size: str = "", file_type: str = ""):
        self.name = unquote(name)
        self.url = url
        self.size = size
        self.file_type = file_type
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
        # Remove file extensions
        clean = re.sub(r'\.(rvz|zip|7z|iso|bin|cue)$', '', self.name, flags=re.IGNORECASE)
        
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
    
    def scrape_roms(self, url: str, file_pattern: str = None) -> List[RomInfo]:
        """Scrape ROM files from a given URL.
        
        Args:
            url: URL to scrape for ROM files.
            file_pattern: Regex pattern to match file names.
            
        Returns:
            List of RomInfo objects representing found ROMs.
        """
        try:
            logger.info(f"Scraping ROMs from: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            roms = []
            
            # Look for file links - common patterns for directory listings
            file_links = soup.find_all('a', href=True)
            
            for link in file_links:
                href = link.get('href')
                if not href or href.startswith('../') or href == '/':
                    continue
                
                # Get the full URL
                full_url = urljoin(url, href)
                
                # Extract file name from href or link text
                file_name = href.strip('/')
                if not file_name:
                    file_name = link.get_text().strip()
                
                # Skip if it's a directory (ends with /)
                if href.endswith('/'):
                    continue
                
                # Apply file pattern filter if provided
                if file_pattern:
                    if not re.search(file_pattern, file_name, re.IGNORECASE):
                        continue
                
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
                logger.debug(f"Found ROM: {rom_info}")
            
            logger.info(f"Found {len(roms)} ROM files")
            return roms
            
        except requests.RequestException as e:
            logger.error(f"Error scraping URL {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error scraping URL {url}: {e}")
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