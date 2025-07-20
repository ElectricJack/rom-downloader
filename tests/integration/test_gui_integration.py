"""
Integration test to verify the GUI filtering works with the advanced ROM filter.

This test verifies that the shared filtering logic works correctly when
integrated into the GUI components.
"""

import unittest
import sys
import os

# Add the project root to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from models.game_library import Game, ROM
from filters.advanced_rom_filter import AdvancedRomFilter, FilterCriteria


class TestGUIIntegration(unittest.TestCase):
    """Test the integration between GUI and advanced ROM filter"""
    
    def setUp(self):
        """Set up test fixtures with real ROM objects"""
        self.advanced_filter = AdvancedRomFilter()
        
        # Create test ROMs using the actual ROM class
        self.test_roms = [
            ROM(
                filename="Street Fighter II (USA).zip",
                url="http://example.com/sf2_usa.zip",
                size="2MB",
                file_type="zip",
                tags={"english", "usa", "final"},
                platform="SNES"
            ),
            ROM(
                filename="Street Fighter II (Europe).zip", 
                url="http://example.com/sf2_eu.zip",
                size="2MB",
                file_type="zip",
                tags={"english", "europe", "final"},
                platform="SNES"
            ),
            ROM(
                filename="Street Fighter II (Japan).zip",
                url="http://example.com/sf2_jp.zip", 
                size="2MB",
                file_type="zip",
                tags={"japanese", "japan", "final"},
                platform="SNES"
            ),
            ROM(
                filename="Final Fantasy VI (USA).zip",
                url="http://example.com/ff6_usa.zip",
                size="3MB",
                file_type="zip", 
                tags={"english", "usa", "final"},
                platform="SNES"
            ),
            ROM(
                filename="Dragon Quest V (Japan).zip",
                url="http://example.com/dq5_jp.zip",
                size="2.5MB",
                file_type="zip",
                tags={"japanese", "japan", "final"},
                platform="SNES"
            ),
            ROM(
                filename="Secret of Mana (USA) [Beta].zip",
                url="http://example.com/som_beta.zip",
                size="1.5MB",
                file_type="zip",
                tags={"english", "usa", "beta"},
                platform="SNES"
            ),
        ]
    
    def test_empty_filter_shows_all_roms(self):
        """Test that empty filter criteria shows all ROMs"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        self.assertEqual(len(result), len(self.test_roms))
        # Compare by converting to list since ROM objects aren't hashable
        self.assertEqual(sorted(result, key=lambda r: r.filename), sorted(self.test_roms, key=lambda r: r.filename))
    
    def test_language_only_filter(self):
        """Test filtering by language only"""
        criteria = FilterCriteria(languages={"english"}, regions=set(), additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get English ROMs: Street Fighter II (USA), (Europe), Final Fantasy VI (USA), Secret of Mana (USA) [Beta]
        expected_count = 4
        self.assertEqual(len(result), expected_count)
        
        # Verify all results have English language
        for rom in result:
            self.assertIn("english", rom.tags)
    
    def test_region_only_filter(self):
        """Test filtering by region only"""
        criteria = FilterCriteria(languages=set(), regions={"usa"}, additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get USA ROMs: Street Fighter II (USA), Final Fantasy VI (USA), Secret of Mana (USA) [Beta]
        expected_count = 3
        self.assertEqual(len(result), expected_count)
        
        # Verify all results have USA region
        for rom in result:
            self.assertIn("usa", rom.tags)
    
    def test_combined_language_region_filter(self):
        """Test filtering by both language and region (AND logic)"""
        criteria = FilterCriteria(languages={"english"}, regions={"usa"}, additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get ROMs that are both English AND USA
        expected_count = 3  # Street Fighter II (USA), Final Fantasy VI (USA), Secret of Mana (USA) [Beta]
        self.assertEqual(len(result), expected_count)
        
        # Verify all results have both English and USA
        for rom in result:
            self.assertIn("english", rom.tags)
            self.assertIn("usa", rom.tags)
    
    def test_additional_tags_filter(self):
        """Test filtering by additional tags"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags={"final"})
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get final ROMs (excludes beta)
        expected_count = 5  # All except Secret of Mana Beta
        self.assertEqual(len(result), expected_count)
        
        # Verify all results have final tag
        for rom in result:
            self.assertIn("final", rom.tags)
    
    def test_exclude_beta_versions(self):
        """Test filtering to exclude beta versions"""
        criteria = FilterCriteria(languages=set(), regions=set(), additional_tags={"final"})
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should exclude the beta ROM
        beta_roms = [rom for rom in result if "beta" in rom.tags]
        self.assertEqual(len(beta_roms), 0)
    
    def test_multi_language_or_logic(self):
        """Test that multiple languages use OR logic within the group"""
        criteria = FilterCriteria(languages={"english", "japanese"}, regions=set(), additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get all ROMs since they're all either English or Japanese
        self.assertEqual(len(result), len(self.test_roms))
    
    def test_multi_region_or_logic(self):
        """Test that multiple regions use OR logic within the group"""
        criteria = FilterCriteria(languages=set(), regions={"usa", "japan"}, additional_tags=set())
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get ROMs from either USA or Japan
        expected_count = 5  # All except Street Fighter II (Europe)
        self.assertEqual(len(result), expected_count)
        
        # Verify no Europe-only ROMs
        for rom in result:
            has_usa_or_japan = "usa" in rom.tags or "japan" in rom.tags
            self.assertTrue(has_usa_or_japan)
    
    def test_complex_filtering_scenario(self):
        """Test complex filtering with all three filter types"""
        criteria = FilterCriteria(
            languages={"english"}, 
            regions={"usa"}, 
            additional_tags={"final"}
        )
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        
        # Should get English AND USA AND final ROMs
        expected_count = 2  # Street Fighter II (USA), Final Fantasy VI (USA)
        self.assertEqual(len(result), expected_count)
        
        # Verify all conditions are met
        for rom in result:
            self.assertIn("english", rom.tags)
            self.assertIn("usa", rom.tags)
            self.assertIn("final", rom.tags)
    
    def test_filter_criteria_creation_from_mixed_tags(self):
        """Test creating filter criteria from mixed tag selection"""
        selected_tags = {"english", "japanese", "usa", "japan", "final", "beta"}
        
        criteria = self.advanced_filter.create_filter_criteria(selected_tags)
        
        # Verify proper categorization
        self.assertEqual(criteria.languages, {"english", "japanese"})
        self.assertEqual(criteria.regions, {"usa", "japan"})
        self.assertEqual(criteria.additional_tags, {"final", "beta"})
    
    def test_rom_tag_extractor_compatibility(self):
        """Test that the filter works with ROM objects using custom tag extractor"""
        criteria = FilterCriteria(languages={"english"}, regions=set(), additional_tags=set())
        
        # Test with custom tag extractor (should work the same as default)
        def custom_tag_extractor(rom):
            return rom.tags
        
        result = self.advanced_filter.filter_roms(self.test_roms, criteria, custom_tag_extractor)
        
        # Should get same result as default extractor
        expected_result = self.advanced_filter.filter_roms(self.test_roms, criteria)
        self.assertEqual(len(result), len(expected_result))
        # Compare by sorting since ROM objects aren't hashable
        self.assertEqual(sorted(result, key=lambda r: r.filename), sorted(expected_result, key=lambda r: r.filename))


class TestGameLibraryCompatibility(unittest.TestCase):
    """Test compatibility with Game objects containing multiple ROM variants"""
    
    def setUp(self):
        """Set up test fixtures with Game objects"""
        self.advanced_filter = AdvancedRomFilter()
        
        # Create test games with multiple ROM variants
        self.sf2_game = Game(key="street_fighter_ii", display_name="Street Fighter II")
        self.sf2_game.add_variant(ROM(
            filename="Street Fighter II (USA).zip",
            url="http://example.com/sf2_usa.zip", 
            size="2MB",
            file_type="zip",
            tags={"english", "usa", "final"},
            platform="SNES"
        ))
        self.sf2_game.add_variant(ROM(
            filename="Street Fighter II (Europe).zip",
            url="http://example.com/sf2_eu.zip",
            size="2MB", 
            file_type="zip",
            tags={"english", "europe", "final"},
            platform="SNES"
        ))
        self.sf2_game.add_variant(ROM(
            filename="Street Fighter II (Japan).zip",
            url="http://example.com/sf2_jp.zip",
            size="2MB",
            file_type="zip", 
            tags={"japanese", "japan", "final"},
            platform="SNES"
        ))
    
    def test_game_has_all_variant_tags(self):
        """Test that games can be filtered based on all their ROM variant tags"""
        # Game should have all tags from all variants
        all_tags = self.sf2_game.get_all_tags()
        
        expected_tags = {"english", "japanese", "usa", "europe", "japan", "final"}
        self.assertEqual(all_tags, expected_tags)
    
    def test_filter_game_by_any_variant_language(self):
        """Test that games match if any variant has the required language"""
        criteria = FilterCriteria(languages={"english"}, regions=set(), additional_tags=set())
        
        # Game should match because it has English variants
        game_tags = self.sf2_game.get_all_tags()
        matches = self.advanced_filter.rom_matches_criteria(game_tags, criteria)
        
        self.assertTrue(matches)
    
    def test_filter_game_by_any_variant_region(self):
        """Test that games match if any variant has the required region"""
        criteria = FilterCriteria(languages=set(), regions={"usa"}, additional_tags=set())
        
        # Game should match because it has USA variant
        game_tags = self.sf2_game.get_all_tags()
        matches = self.advanced_filter.rom_matches_criteria(game_tags, criteria)
        
        self.assertTrue(matches)
    
    def test_filter_game_with_multiple_criteria(self):
        """Test filtering games with multiple criteria"""
        criteria = FilterCriteria(languages={"english"}, regions={"usa"}, additional_tags={"final"})
        
        # Game should match because it has English+USA+final variants
        game_tags = self.sf2_game.get_all_tags()
        matches = self.advanced_filter.rom_matches_criteria(game_tags, criteria)
        
        self.assertTrue(matches)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)