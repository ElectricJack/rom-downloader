"""
Game library processor for converting ROM lists into organized game library.
"""

import re
import logging
from typing import List, Set, Tuple, Dict
from pathlib import Path

from src.scraper.web_scraper import RomInfo
from src.models.game_library import ROM, Game, GameLibrary
from src.utils.rom_utils import get_rom_utils

logger = logging.getLogger(__name__)


class GameLibraryProcessor:
    """Processes ROMs into organized game library"""
    
    def __init__(self):
        self.tag_patterns = [
            r'\(([^)]+)\)',  # Anything in parentheses
            r'\[([^\]]+)\]'  # Anything in brackets (optional)
        ]
        
        # Get ROM utilities for consistent extension handling
        self.rom_utils = get_rom_utils()
        
        # Tags that should be prioritized (ordered by preference)
        self.priority_tags = [
            'USA', 'US', 'En', 'English', 'World', 'Europe', 'Japan', 'JP'
        ]
    
    def process_rom_collection(self, roms: List[RomInfo], platform: str) -> GameLibrary:
        """Convert ROM list into organized game library"""
        library = GameLibrary()
        
        logger.info(f"Processing {len(roms)} ROMs for platform {platform}")
        
        for rom_info in roms:
            # Convert RomInfo to ROM with tag extraction
            rom = self._create_rom_from_info(rom_info, platform)
            
            # Create game key using canonical ROM name
            rom_utils = get_rom_utils()
            canonical_name = rom_utils.get_canonical_rom_name(rom.filename)
            game_key = self.create_game_key(canonical_name)
            
            if game_key not in library.games:
                display_name = self._create_display_name(rom.clean_name)
                game = Game(
                    key=game_key,
                    display_name=display_name,
                    platforms={platform}
                )
                library.add_game(game)
            
            # Add ROM variant to game
            game = library.games[game_key]
            game.add_variant(rom)
            
            # Update tag registry after adding variant
            library.tag_registry[platform].update(rom.tags)
        
        logger.info(f"Processed into {len(library.games)} unique games with {sum(len(g.variants) for g in library.games.values())} variants")
        
        # Sort the games alphabetically by display name
        sorted_games = dict(sorted(library.games.items(), key=lambda item: item[1].display_name.lower()))
        library.games = sorted_games
        logger.debug(f"Sorted {len(library.games)} games alphabetically")
        
        return library
    
    def _create_rom_from_info(self, rom_info: RomInfo, platform: str) -> ROM:
        """Create ROM object from RomInfo with tag extraction"""
        tags, normalized_name = self.extract_tags_and_normalize(rom_info.name)
        
        is_installed_only = getattr(rom_info, 'is_installed_only', False)
        if is_installed_only:
            logger.info(f"Creating installed-only ROM: {rom_info.name}")
        
        return ROM(
            filename=rom_info.name,
            url=rom_info.url,
            size=rom_info.size,
            file_type=rom_info.file_type,
            tags=tags,
            platform=platform,
            clean_name=rom_info.clean_name,
            is_installed_only=is_installed_only
        )
    
    def extract_tags_and_normalize(self, filename: str) -> Tuple[Set[str], str]:
        """Extract all tags and return normalized name"""
        tags = set()
        normalized = filename
        
        # Remove file extension using centralized ROM utilities
        normalized = self.rom_utils.get_rom_stem(normalized)
        
        # Extract tags from parentheses and brackets
        for pattern in self.tag_patterns:
            matches = re.findall(pattern, normalized)
            for match in matches:
                # Handle comma-delimited tags
                tag_parts = [t.strip() for t in match.split(',') if t.strip()]
                tags.update(tag_parts)
        
        # Clean and normalize tags
        tags = self.clean_tags(tags)
        
        # Remove all parenthetical/bracket content from name
        for pattern in self.tag_patterns:
            normalized = re.sub(pattern, '', normalized)
        
        # Clean up normalized name
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return tags, normalized
    
    def clean_tags(self, tags: Set[str]) -> Set[str]:
        """Clean and normalize tags according to rules"""
        cleaned_tags = set()
        
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            
            # Rule 1: Ignore tags that start with a number
            if tag and tag[0].isdigit():
                continue
            
            # Rule 2: Ignore tags that start with "Disk" (case-insensitive)
            if tag.lower().startswith('disk'):
                continue
            
            # Rule 3: Ignore version tags (v1, v2, etc. and Ver. 1, Ver. 2, etc.)
            if re.match(r'^v\d+', tag.lower()) or re.match(r'^ver\.?\s*\d+', tag.lower()):
                continue
            
            # Rule 4: Combine tags that start with specific prefixes
            tag_lower = tag.lower()
            
            # Demo tags (Demo, Demo Eizou, etc.) -> Demo
            if tag_lower.startswith('demo'):
                cleaned_tags.add('Demo')
                continue
            
            # Proto tags (Proto, Prototype, etc.) -> Proto
            if tag_lower.startswith('proto'):
                cleaned_tags.add('Proto')
                continue
            
            # Promo tags (Promo, Promotional, etc.) -> Promo
            if tag_lower.startswith('promo'):
                cleaned_tags.add('Promo')
                continue
            
            # Beta tags (Beta, Beta 1, etc.) -> Beta
            if tag_lower.startswith('beta'):
                cleaned_tags.add('Beta')
                continue
            
            # Rev tags (Rev, Rev 1, Rev A, etc.) -> Rev
            # But keep "Revision" as it's a different word
            if tag_lower.startswith('rev') and (tag_lower == 'rev' or tag_lower.startswith('rev ')):
                cleaned_tags.add('Rev')
                continue
            
            # If none of the rules apply, keep the original tag
            cleaned_tags.add(tag)
        
        return cleaned_tags
    
    def categorize_tags(self, tags: Set[str]) -> Dict[str, List[str]]:
        """Categorize tags into groups: language, country, and other"""
        
        # Define language tags (ISO 639-1 codes and common language names)
        language_tags = {
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
        country_tags = {
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
        
        categories = {
            'language': [],
            'country': [],
            'other': []
        }
        
        for tag in sorted(tags):
            tag_lower = tag.lower()
            
            if tag_lower in language_tags:
                categories['language'].append(tag)
            elif tag_lower in country_tags:
                categories['country'].append(tag)
            else:
                categories['other'].append(tag)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def format_tag_groups_compact(self, categorized_tags: Dict[str, List[str]]) -> str:
        """Format categorized tags into a compact string representation"""
        parts = []
        
        # Format each category without emojis
        if 'language' in categorized_tags:
            langs = ', '.join(categorized_tags['language'])
            parts.append(f"Languages: {langs}")
        
        if 'country' in categorized_tags:
            countries = ', '.join(categorized_tags['country'])
            parts.append(f"Regions: {countries}")
        
        if 'other' in categorized_tags:
            other = ', '.join(categorized_tags['other'])
            parts.append(f"Other: {other}")
        
        return ' | '.join(parts)
    
    def create_game_key(self, canonical_name: str) -> str:
        """Create consistent game key from canonical ROM name"""
        # canonical_name is already normalized and extension-free
        key = canonical_name.lower()
        
        # Apply additional game-level transformations
        # Remove common prefixes/suffixes
        prefixes_to_remove = ['the ', 'a ', 'an ']
        for prefix in prefixes_to_remove:
            if key.startswith(prefix):
                key = key[len(prefix):]
                break
        
        # Remove punctuation and special characters
        key = re.sub(r'[^\w\s]', '', key)
        
        # Replace spaces with underscores
        key = re.sub(r'\s+', '_', key)
        
        # Remove leading/trailing underscores
        key = key.strip('_')
        
        return key
    
    def _create_display_name(self, filename: str) -> str:
        """Create clean display name from filename"""
        _, normalized_name = self.extract_tags_and_normalize(filename)
        
        # Clean up common artifacts
        display_name = normalized_name.strip()
        
        # Remove common prefixes that might be left
        prefixes_to_clean = ['- ', '_ ', '. ']
        for prefix in prefixes_to_clean:
            if display_name.startswith(prefix):
                display_name = display_name[len(prefix):]
        
        # Remove common suffixes
        suffixes_to_clean = [' -', ' _', ' .']
        for suffix in suffixes_to_clean:
            if display_name.endswith(suffix):
                display_name = display_name[:-len(suffix)]
        
        # Ensure proper capitalization
        display_name = self._title_case(display_name)
        
        return display_name
    
    def _title_case(self, text: str) -> str:
        """Apply title case with special handling for common words"""
        # Words that should not be capitalized (except at start)
        small_words = {
            'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 
            'of', 'on', 'or', 'the', 'to', 'up', 'vs', 'via'
        }
        
        words = text.split()
        result = []
        
        for i, word in enumerate(words):
            if i == 0 or word.lower() not in small_words:
                # Capitalize first letter, keep rest as-is to preserve acronyms
                if word:
                    result.append(word[0].upper() + word[1:])
                else:
                    result.append(word)
            else:
                result.append(word.lower())
        
        return ' '.join(result)
    
    def deduplicate_games(self, library: GameLibrary) -> GameLibrary:
        """Remove duplicate games and merge variants"""
        # This is mainly for merging games that might have slightly different keys
        # but represent the same game
        
        # For now, return as-is. More sophisticated deduplication can be added later
        return library
    
    def get_tag_statistics(self, library: GameLibrary) -> Dict[str, Dict[str, int]]:
        """Get statistics about tag usage per platform"""
        stats = {}
        
        for platform in library.tag_registry:
            platform_stats = {}
            platform_games = library.get_games_for_platform(platform)
            
            for game in platform_games:
                for tag in game.get_all_tags():
                    platform_stats[tag] = platform_stats.get(tag, 0) + 1
            
            # Sort by frequency
            stats[platform] = dict(sorted(platform_stats.items(), key=lambda x: x[1], reverse=True))
        
        return stats
    
    def suggest_preferred_tags(self, library: GameLibrary, platform: str) -> List[str]:
        """Suggest preferred tags based on frequency and common patterns"""
        tag_stats = self.get_tag_statistics(library)
        platform_tags = tag_stats.get(platform, {})
        
        # Start with predefined priority tags that exist in the data
        preferred = []
        for tag in self.priority_tags:
            if tag in platform_tags:
                preferred.append(tag)
        
        # Add other common tags (more than 5% of games)
        total_games = len(library.get_games_for_platform(platform))
        if total_games > 0:
            for tag, count in platform_tags.items():
                if tag not in preferred and count / total_games > 0.05:
                    preferred.append(tag)
        
        return preferred[:10]  # Limit to top 10
    
    def merge_installed_only_roms(self, library: GameLibrary, installed_only_roms: List[RomInfo], platform: str) -> GameLibrary:
        """Merge installed-only ROMs into the existing game library"""
        logger.info(f"Merging {len(installed_only_roms)} installed-only ROMs for platform {platform}")
        
        merged_count = 0
        for rom_info in installed_only_roms:
            # Convert RomInfo to ROM
            rom = self._create_rom_from_info(rom_info, platform)
            # Mark as installed since we found it on disk
            rom.set_installed(True, rom_info.name)
            
            # Create game key using canonical ROM name
            rom_utils = get_rom_utils()
            canonical_name = rom_utils.get_canonical_rom_name(rom.filename)
            game_key = self.create_game_key(canonical_name)
            
            if game_key not in library.games:
                # Create new game for installed-only ROM
                display_name = self._create_display_name(rom.clean_name)
                game = Game(
                    key=game_key,
                    display_name=display_name,
                    platforms={platform}
                )
                library.add_game(game)
                logger.debug(f"Created new game for installed-only ROM: {display_name}")
            
            # Add ROM variant to game
            game = library.games[game_key]
            game.add_variant(rom)
            
            # Update tag registry after adding variant
            if platform not in library.tag_registry:
                library.tag_registry[platform] = set()
            library.tag_registry[platform].update(rom.tags)
            
            merged_count += 1
        
        logger.info(f"Successfully merged {merged_count} installed-only ROMs into library")
        
        # Sort the games alphabetically by display name after merging
        sorted_games = dict(sorted(library.games.items(), key=lambda item: item[1].display_name.lower()))
        library.games = sorted_games
        logger.debug(f"Sorted {len(library.games)} games alphabetically after merging installed-only ROMs")
        
        return library