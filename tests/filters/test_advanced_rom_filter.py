"""
Comprehensive test cases for advanced ROM filtering logic.

Tests the additive region/language selection with AND/OR logic:
- OR logic within each group (languages, regions, additional tags)
- AND logic between groups  
- Empty selection means "all" for that group
"""

import unittest
from typing import Set
from dataclasses import dataclass

# Import the shared filtering logic
import sys
import os

# Add the project root to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from filters.advanced_rom_filter import AdvancedRomFilter, FilterCriteria


@dataclass(frozen=True)
class MockROM:
    """Mock ROM object for testing"""
    name: str
    tags: frozenset
    
    def __init__(self, name: str, tags: Set[str]):
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'tags', frozenset(tags))
    
    def __repr__(self):
        return f"ROM({self.name}, {sorted(self.tags)})"


class TestAdvancedRomFilter(unittest.TestCase):
    """Test cases for AdvancedRomFilter"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filter = AdvancedRomFilter()
        
        # Create test ROMs with various tag combinations
        self.test_roms = [
            # English ROMs
            MockROM("Game1", {"english", "usa", "final"}),
            MockROM("Game2", {"en", "europe", "demo"}),
            MockROM("Game3", {"english", "world", "beta"}),
            
            # Japanese ROMs
            MockROM("Game4", {"japanese", "japan", "final"}),
            MockROM("Game5", {"ja", "jp", "demo"}),
            
            # Multi-language ROMs
            MockROM("Game6", {"english", "french", "europe", "final"}),
            MockROM("Game7", {"japanese", "english", "world", "collection"}),
            
            # Region-specific without explicit language
            MockROM("Game8", {"usa", "ntsc", "special"}),
            MockROM("Game9", {"europe", "pal", "limited"}),
            MockROM("Game10", {"japan", "ntsc", "prototype"}),
            
            # Other languages
            MockROM("Game11", {"german", "germany", "final"}),
            MockROM("Game12", {"spanish", "spain", "demo"}),
            MockROM("Game13", {"french", "france", "beta"}),
            
            # Multiple regions
            MockROM("Game14", {"usa", "europe", "world", "deluxe"}),
            MockROM("Game15", {"asia", "japan", "korea", "special"}),
            
            # Additional tags only
            MockROM("Game16", {"prototype", "unreleased", "rare"}),
            MockROM("Game17", {"collection", "remaster", "enhanced"}),
        ]
    
    def test_empty_filters_shows_all(self):
        """Test that empty filters show all ROMs"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        self.assertEqual(len(result), len(self.test_roms))
        self.assertEqual(set(result), set(self.test_roms))
    
    def test_single_language_filter(self):
        """Test filtering by single language (OR within language group)"""
        criteria = FilterCriteria(languages={"english"}, regions=set(), additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game1", "Game3", "Game6", "Game7"}  # Only ROMs with "english" tag
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_multiple_language_filter_or_logic(self):
        """Test that multiple languages use OR logic within the group"""
        criteria = FilterCriteria(languages={"english", "japanese"}, regions=set(), additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        # Should include ROMs with either English OR Japanese (exact tag match)
        expected_names = {"Game1", "Game3", "Game4", "Game6", "Game7"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_single_region_filter(self):
        """Test filtering by single region"""
        criteria = FilterCriteria(languages=set(), regions={"usa"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game1", "Game8", "Game14"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_multiple_region_filter_or_logic(self):
        """Test that multiple regions use OR logic within the group"""
        criteria = FilterCriteria(languages=set(), regions={"usa", "japan"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        # Should include ROMs with either USA OR Japan
        expected_names = {"Game1", "Game4", "Game8", "Game10", "Game14", "Game15"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_language_and_region_filter_and_logic(self):
        """Test that language AND region filters use AND logic between groups"""
        criteria = FilterCriteria(languages={"english"}, regions={"usa"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        # Should include ROMs that have English AND USA
        expected_names = {"Game1"}  # Only Game1 has both English and USA
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_complex_multi_filter_and_logic(self):
        """Test complex filtering with multiple languages, regions, and additional tags"""
        criteria = FilterCriteria(
            languages={"english", "japanese"}, 
            regions={"world"}, 
            additional_tags={"final", "collection"}
        )
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        # Should include ROMs that have (English OR Japanese) AND (World) AND (final OR collection)
        expected_names = {"Game7"}  # Only Game7 has Japanese+English, World, and Collection
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_additional_tags_only(self):
        """Test filtering by additional tags only"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags={"demo"})
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game2", "Game5", "Game12"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_multiple_additional_tags_or_logic(self):
        """Test that multiple additional tags use OR logic"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags={"demo", "beta"})
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game2", "Game3", "Game5", "Game12", "Game13"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_no_matches(self):
        """Test filtering that results in no matches"""
        criteria = FilterCriteria(languages={"chinese"}, regions={"usa"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        self.assertEqual(len(result), 0)
    
    def test_case_insensitive_matching(self):
        """Test that tag matching is case-insensitive"""
        criteria = FilterCriteria(languages={"ENGLISH"}, regions=set(), additional_tags=set())
        
        result = self.filter.filter_roms(self.test_roms, criteria)
        # Should match ROMs with "english" tags despite case difference
        expected_names = {"Game1", "Game3", "Game6", "Game7"}
        actual_names = {rom.name for rom in result}
        
        self.assertEqual(actual_names, expected_names)
    
    def test_tag_categorization(self):
        """Test that tags are correctly categorized"""
        tags = {"english", "usa", "demo", "japanese", "world", "beta", "prototype"}
        
        categories = self.filter.categorize_tags(tags)
        
        expected = {
            'languages': {"english", "japanese"},
            'regions': {"usa", "world"},
            'additional': {"demo", "beta", "prototype"}
        }
        
        self.assertEqual(categories, expected)
    
    def test_filter_criteria_creation(self):
        """Test creating filter criteria from selected tags"""
        selected_tags = {"english", "usa", "demo", "japanese", "world"}
        
        criteria = self.filter.create_filter_criteria(selected_tags)
        
        self.assertEqual(criteria.languages, {"english", "japanese"})
        self.assertEqual(criteria.regions, {"usa", "world"})
        self.assertEqual(criteria.additional_tags, {"demo"})
    
    def test_rom_matches_criteria_direct(self):
        """Test rom_matches_criteria method directly"""
        criteria = FilterCriteria(languages={"english"}, regions={"usa"}, additional_tags=set())
        
        # ROM with matching tags
        rom_tags1 = {"english", "usa", "final"}
        self.assertTrue(self.filter.rom_matches_criteria(rom_tags1, criteria))
        
        # ROM missing language
        rom_tags2 = {"japanese", "usa", "final"}
        self.assertFalse(self.filter.rom_matches_criteria(rom_tags2, criteria))
        
        # ROM missing region
        rom_tags3 = {"english", "europe", "final"}
        self.assertFalse(self.filter.rom_matches_criteria(rom_tags3, criteria))
    
    def test_filter_summary(self):
        """Test filter summary generation"""
        criteria = FilterCriteria(
            languages={"english", "japanese"}, 
            regions={"usa"}, 
            additional_tags={"demo", "final"}
        )
        
        summary = self.filter.get_filter_summary(criteria)
        
        # Should contain all filter groups with AND between them
        self.assertIn("Languages: english, japanese", summary)
        self.assertIn("Regions: usa", summary)
        self.assertIn("Additional: demo, final", summary)
        self.assertIn(" AND ", summary)
    
    def test_empty_filter_summary(self):
        """Test summary for empty filters"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags=set())
        
        summary = self.filter.get_filter_summary(criteria)
        self.assertEqual(summary, "No filters active (showing all ROMs)")
    
    def test_edge_case_alias_matching(self):
        """Test that tag aliases match correctly"""
        # Test English short form
        criteria = FilterCriteria(languages={"en"}, regions=set(), additional_tags=set())
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game2"}  # Only Game2 has "en" tag
        actual_names = {rom.name for rom in result}
        self.assertEqual(actual_names, expected_names)
        
        # Test Japanese short form  
        criteria = FilterCriteria(languages={"ja"}, regions=set(), additional_tags=set())
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game5"}  # Only Game5 has "ja" tag
        actual_names = {rom.name for rom in result}
        self.assertEqual(actual_names, expected_names)
    
    def test_region_alias_matching(self):
        """Test that region aliases match correctly"""
        # Test Japan as region (note: jp is categorized as language, so use japan)
        criteria = FilterCriteria(languages=set(), regions={"japan"}, additional_tags=set())
        result = self.filter.filter_roms(self.test_roms, criteria)
        expected_names = {"Game4", "Game10", "Game15"}  # ROMs with "japan" tag
        actual_names = {rom.name for rom in result}
        self.assertEqual(actual_names, expected_names)


class TestFilterIntegration(unittest.TestCase):
    """Integration tests simulating real-world usage scenarios"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.filter = AdvancedRomFilter()
        
        # Simulate a realistic ROM collection
        self.game_library = [
            MockROM("Street Fighter II (USA)", {"english", "usa", "final"}),
            MockROM("Street Fighter II (Europe)", {"english", "europe", "final"}),
            MockROM("Street Fighter II (Japan)", {"japanese", "japan", "final"}),
            MockROM("Street Fighter II - Special Champion Edition (USA)", {"english", "usa", "special"}),
            MockROM("Final Fantasy VI (USA)", {"english", "usa", "final"}),
            MockROM("Final Fantasy VI (Europe)", {"english", "europe", "final"}),
            MockROM("Final Fantasy III (Japan)", {"japanese", "japan", "final"}),
            MockROM("Super Mario World (USA)", {"english", "usa", "final"}),
            MockROM("Super Mario World (Europe)", {"english", "europe", "final"}),
            MockROM("Super Mario World (Japan)", {"japanese", "japan", "final"}),
            MockROM("Dragon Quest V (Japan)", {"japanese", "japan", "final"}),
            MockROM("Secret of Mana (USA)", {"english", "usa", "final"}),
            MockROM("Seiken Densetsu 2 (Japan)", {"japanese", "japan", "final"}),
            MockROM("Chrono Trigger (USA)", {"english", "usa", "final"}),
            MockROM("Chrono Trigger (Europe) [Beta]", {"english", "europe", "beta"}),
            MockROM("Mega Man X (USA)", {"english", "usa", "final"}),
            MockROM("Rockman X (Japan)", {"japanese", "japan", "final"}),
            MockROM("ActRaiser (USA)", {"english", "usa", "final"}),
            MockROM("ActRaiser (Europe)", {"english", "europe", "final"}),
            MockROM("ActRaiser (Germany)", {"german", "germany", "final"}),
        ]
    
    def test_typical_user_scenario_english_only(self):
        """Test typical scenario: User wants English ROMs only"""
        criteria = FilterCriteria(languages={"english"}, regions=set(), additional_tags=set())
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get all English ROMs regardless of region
        english_roms = [rom for rom in self.game_library if "english" in rom.tags]
        self.assertEqual(len(result), len(english_roms))
        self.assertEqual(set(result), set(english_roms))
    
    def test_region_preference_scenario(self):
        """Test scenario: User wants USA region ROMs only"""
        criteria = FilterCriteria(languages=set(), regions={"usa"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get all USA ROMs regardless of language
        usa_roms = [rom for rom in self.game_library if "usa" in rom.tags]
        expected_count = 8  # Count of ROMs with "usa" tag
        self.assertEqual(len(result), expected_count)
    
    def test_combined_language_region_scenario(self):
        """Test scenario: User wants English AND USA ROMs"""
        criteria = FilterCriteria(languages={"english"}, regions={"usa"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get ROMs that are both English AND USA
        expected_names = {
            "Street Fighter II (USA)",
            "Street Fighter II - Special Champion Edition (USA)",
            "Final Fantasy VI (USA)",
            "Super Mario World (USA)",
            "Secret of Mana (USA)",
            "Chrono Trigger (USA)",
            "Mega Man X (USA)",
            "ActRaiser (USA)"
        }
        actual_names = {rom.name for rom in result}
        self.assertEqual(actual_names, expected_names)
    
    def test_multi_region_preference_scenario(self):
        """Test scenario: User wants USA OR Europe ROMs"""
        criteria = FilterCriteria(languages=set(), regions={"usa", "europe"}, additional_tags=set())
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get ROMs from either USA or Europe
        usa_europe_roms = [rom for rom in self.game_library 
                          if "usa" in rom.tags or "europe" in rom.tags]
        self.assertEqual(len(result), len(usa_europe_roms))
    
    def test_exclude_beta_scenario(self):
        """Test scenario: User wants final releases only (exclude beta)"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags={"final"})
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get only final releases
        final_roms = [rom for rom in self.game_library if "final" in rom.tags]
        self.assertEqual(len(result), len(final_roms))
        
        # Verify beta ROM is excluded
        beta_rom_names = {rom.name for rom in result if "beta" in rom.tags}
        self.assertEqual(len(beta_rom_names), 0)
    
    def test_complex_real_world_scenario(self):
        """Test complex scenario: English or Japanese, from USA or Japan, final only"""
        criteria = FilterCriteria(
            languages={"english", "japanese"}, 
            regions={"usa", "japan"}, 
            additional_tags={"final"}
        )
        
        result = self.filter.filter_roms(self.game_library, criteria)
        
        # Should get ROMs that are:
        # (English OR Japanese) AND (USA OR Japan) AND (Final)
        expected_names = {
            "Street Fighter II (USA)",
            "Street Fighter II (Japan)",
            "Final Fantasy VI (USA)",
            "Final Fantasy III (Japan)",
            "Super Mario World (USA)",
            "Super Mario World (Japan)",
            "Dragon Quest V (Japan)",
            "Secret of Mana (USA)",
            "Seiken Densetsu 2 (Japan)",
            "Chrono Trigger (USA)",
            "Mega Man X (USA)",
            "Rockman X (Japan)",
            "ActRaiser (USA)"
        }
        actual_names = {rom.name for rom in result}
        self.assertEqual(actual_names, expected_names)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)