"""
Advanced ROM filtering with additive region/language selection logic.

This module provides the core filtering logic that implements:
- OR logic within each group (languages, regions, additional tags)
- AND logic between groups
- Empty selection means "all" for that group
"""

import logging
from typing import Set, List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterCriteria:
    """Container for filtering criteria with separated concerns"""
    languages: Set[str]
    regions: Set[str]
    additional_tags: Set[str]
    
    def is_empty(self) -> bool:
        """Check if all filter criteria are empty"""
        return not (self.languages or self.regions or self.additional_tags)
    
    def has_language_filter(self) -> bool:
        """Check if language filter is active"""
        return bool(self.languages)
    
    def has_region_filter(self) -> bool:
        """Check if region filter is active"""
        return bool(self.regions)
    
    def has_additional_filter(self) -> bool:
        """Check if additional tag filter is active"""
        return bool(self.additional_tags)


class AdvancedRomFilter:
    """
    Advanced ROM filtering with additive selection logic.
    
    Logic:
    - Within each group (languages, regions, additional): OR relationship
    - Between groups: AND relationship
    - Empty group means "all items match" for that group
    """
    
    def __init__(self):
        # Define language tags (ISO 639-1 codes and common language names)
        self.language_tags = {
            'en', 'english', 'ja', 'japanese', 'jp', 'fr', 'french', 'de', 'german',
            'es', 'spanish', 'it', 'italian', 'pt', 'portuguese', 'ru', 'russian',
            'ko', 'korean', 'zh', 'chinese', 'nl', 'dutch', 'sv', 'swedish',
            'da', 'danish', 'no', 'norwegian', 'fi', 'finnish', 'pl', 'polish',
            'tr', 'turkish', 'ar', 'arabic', 'he', 'hebrew', 'hi', 'hindi',
            'th', 'thai', 'vi', 'vietnamese', 'id', 'indonesian', 'ms', 'malay',
            'cs', 'czech', 'hu', 'hungarian', 'ro', 'romanian', 'bg', 'bulgarian',
            'hr', 'croatian', 'sk', 'slovak', 'sl', 'slovenian', 'et', 'estonian',
            'lv', 'latvian', 'lt', 'lithuanian', 'mt', 'maltese', 'ga', 'irish'
        }
        
        # Define country/region tags (expanded list)
        self.region_tags = {
            'usa', 'us', 'america', 'europe', 'eu', 'japan', 'jp', 'asia',
            'australia', 'au', 'canada', 'ca', 'uk', 'britain', 'france', 'fr',
            'germany', 'de', 'italy', 'it', 'spain', 'es', 'mexico', 'mx',
            'brazil', 'br', 'china', 'cn', 'korea', 'kr', 'taiwan', 'tw',
            'turkey', 'tr', 'sweden', 'se', 'russia', 'ru', 'norway', 'no',
            'finland', 'fi', 'denmark', 'dk', 'poland', 'pl', 'netherlands', 'nl',
            'belgium', 'be', 'switzerland', 'ch', 'austria', 'at', 'czech', 'cz',
            'hungary', 'hu', 'romania', 'ro', 'bulgaria', 'bg', 'croatia', 'hr',
            'greece', 'gr', 'portugal', 'pt', 'ireland', 'ie', 'slovakia', 'sk',
            'slovenia', 'si', 'estonia', 'ee', 'latvia', 'lv', 'lithuania', 'lt',
            'india', 'in', 'thailand', 'th', 'vietnam', 'vn', 'indonesia', 'id',
            'malaysia', 'my', 'singapore', 'sg', 'philippines', 'ph',
            'world', 'global', 'international', 'ntsc', 'pal', 'secam'
        }
    
    def categorize_tags(self, tags: Set[str]) -> Dict[str, Set[str]]:
        """
        Categorize tags into languages, regions, and additional tags.
        
        Args:
            tags: Set of tag strings to categorize
            
        Returns:
            Dictionary with 'languages', 'regions', and 'additional' keys
        """
        categories = {
            'languages': set(),
            'regions': set(),
            'additional': set()
        }
        
        for tag in tags:
            tag_lower = tag.lower()
            
            if tag_lower in self.language_tags:
                categories['languages'].add(tag)
            elif tag_lower in self.region_tags:
                categories['regions'].add(tag)
            else:
                categories['additional'].add(tag)
        
        return categories
    
    def create_filter_criteria(self, selected_tags: Set[str]) -> FilterCriteria:
        """
        Convert a set of selected tags into structured filter criteria.
        
        Args:
            selected_tags: Set of tag strings selected by user
            
        Returns:
            FilterCriteria object with categorized tags
        """
        categorized = self.categorize_tags(selected_tags)
        
        return FilterCriteria(
            languages=categorized['languages'],
            regions=categorized['regions'],
            additional_tags=categorized['additional']
        )
    
    def rom_matches_criteria(self, rom_tags: Set[str], criteria: FilterCriteria) -> bool:
        """
        Check if a ROM's tags match the filter criteria using additive logic.
        
        Logic:
        1. If no filters are active, ROM matches (show all)
        2. For each active filter group:
           - ROM must have at least one tag from that group (OR within group)
        3. ROM must satisfy all active groups (AND between groups)
        
        Args:
            rom_tags: Set of tags associated with the ROM
            criteria: Filter criteria to match against
            
        Returns:
            True if ROM matches criteria, False otherwise
        """
        # If no filters are active, show all ROMs
        if criteria.is_empty():
            return True
        
        # Categorize the ROM's tags
        rom_categories = self.categorize_tags(rom_tags)
        
        # Check each filter group
        if criteria.has_language_filter():
            # ROM must have at least one matching language (OR within languages)
            if not self._has_matching_tag(rom_categories['languages'], criteria.languages):
                return False
        
        if criteria.has_region_filter():
            # ROM must have at least one matching region (OR within regions)
            if not self._has_matching_tag(rom_categories['regions'], criteria.regions):
                return False
        
        if criteria.has_additional_filter():
            # ROM must have at least one matching additional tag (OR within additional)
            if not self._has_matching_tag(rom_categories['additional'], criteria.additional_tags):
                return False
        
        # ROM satisfies all active filter groups
        return True
    
    def _has_matching_tag(self, rom_tags: Set[str], filter_tags: Set[str]) -> bool:
        """
        Check if ROM has at least one tag that matches any filter tag (case-insensitive).
        
        Args:
            rom_tags: Set of ROM's tags in this category
            filter_tags: Set of filter tags for this category
            
        Returns:
            True if there's at least one match, False otherwise
        """
        # Convert both sets to lowercase for case-insensitive comparison
        rom_tags_lower = {tag.lower() for tag in rom_tags}
        filter_tags_lower = {tag.lower() for tag in filter_tags}
        
        # Check for any intersection
        return bool(rom_tags_lower & filter_tags_lower)
    
    def filter_roms(self, roms: List, criteria: FilterCriteria, tag_extractor=None) -> List:
        """
        Filter a list of ROMs based on the given criteria.
        
        Args:
            roms: List of ROM objects to filter
            criteria: Filter criteria to apply
            tag_extractor: Function to extract tags from ROM object (default: uses .tags attribute)
            
        Returns:
            List of ROMs that match the criteria
        """
        if tag_extractor is None:
            tag_extractor = lambda rom: getattr(rom, 'tags', set())
        
        filtered_roms = []
        for rom in roms:
            rom_tags = tag_extractor(rom)
            if self.rom_matches_criteria(rom_tags, criteria):
                filtered_roms.append(rom)
        
        return filtered_roms
    
    def get_filter_summary(self, criteria: FilterCriteria) -> str:
        """
        Generate a human-readable summary of active filters.
        
        Args:
            criteria: Filter criteria to summarize
            
        Returns:
            String describing the active filters
        """
        if criteria.is_empty():
            return "No filters active (showing all ROMs)"
        
        parts = []
        
        if criteria.has_language_filter():
            langs = sorted(criteria.languages)
            parts.append(f"Languages: {', '.join(langs)}")
        
        if criteria.has_region_filter():
            regions = sorted(criteria.regions)
            parts.append(f"Regions: {', '.join(regions)}")
        
        if criteria.has_additional_filter():
            additional = sorted(criteria.additional_tags)
            parts.append(f"Additional: {', '.join(additional)}")
        
        return " AND ".join(parts)