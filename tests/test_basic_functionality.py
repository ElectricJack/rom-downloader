"""
Basic functionality tests for the new ROM downloader components.
"""

import unittest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tools.base import ToolStep, ProcessingResult
from tools.zip_extractor import ZipExtractorTool
from tools.pipeline_manager import ToolPipelineManager
from models.game_library import ROM, Game, GameLibrary
from processors.game_library_processor import GameLibraryProcessor
from scraper.web_scraper import RomInfo


class TestToolPipeline(unittest.TestCase):
    """Test tool pipeline functionality"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pipeline_manager = ToolPipelineManager()
    
    def tearDown(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_pipeline_manager_initialization(self):
        """Test that pipeline manager initializes with default tools"""
        tools = self.pipeline_manager.list_tools()
        self.assertIn('zip_extractor', tools)
        self.assertIn('chd_converter', tools)
        self.assertIn('xbox_extractor', tools)
    
    def test_zip_extractor_tool(self):
        """Test ZIP extraction functionality"""
        zip_tool = ZipExtractorTool()
        
        # Create a test ZIP file
        test_zip = self.temp_dir / "test.zip"
        test_file_content = b"This is a test ROM file"
        
        with zipfile.ZipFile(test_zip, 'w') as zf:
            zf.writestr("test_rom.bin", test_file_content)
        
        # Test can_process
        self.assertTrue(zip_tool.can_process([test_zip], {}))
        
        # Test extraction
        output_dir = self.temp_dir / "extracted"
        output_dir.mkdir()
        
        result = zip_tool.process([test_zip], output_dir, {'remove_original': False})
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.output_files), 1)
        self.assertEqual(result.output_files[0].name, "test_rom.bin")
        self.assertTrue(result.output_files[0].exists())
        
        # Check extracted content
        with open(result.output_files[0], 'rb') as f:
            self.assertEqual(f.read(), test_file_content)
    
    def test_tool_pipeline_validation(self):
        """Test pipeline validation"""
        # Valid pipeline
        valid_pipeline = [
            ToolStep(tool_id='zip_extractor', parameters={'remove_original': True})
        ]
        errors = self.pipeline_manager.validate_pipeline(valid_pipeline)
        self.assertEqual(len(errors), 0)
        
        # Invalid pipeline (unknown tool)
        invalid_pipeline = [
            ToolStep(tool_id='unknown_tool', parameters={})
        ]
        errors = self.pipeline_manager.validate_pipeline(invalid_pipeline)
        self.assertEqual(len(errors), 1)
        self.assertIn('unknown_tool', errors[0])


class TestGameLibraryModels(unittest.TestCase):
    """Test game library data models"""
    
    def test_rom_creation(self):
        """Test ROM object creation and methods"""
        rom = ROM(
            filename="Super Mario Bros (USA).nes",
            url="http://example.com/mario.nes",
            size="32KB",
            file_type="NES",
            tags={"USA", "English"},
            platform="nes"
        )
        
        self.assertEqual(rom.filename, "Super Mario Bros (USA).nes")
        self.assertTrue(rom.has_tag("USA"))
        self.assertTrue(rom.has_tag("usa"))  # Case insensitive
        self.assertFalse(rom.has_tag("Japan"))
        
        variant_key = rom.create_variant_key()
        self.assertIn("NES", variant_key)
        self.assertIn("English", variant_key)
    
    def test_game_management(self):
        """Test Game object functionality"""
        game = Game(
            key="super_mario_bros",
            display_name="Super Mario Bros",
            platforms={"nes"}
        )
        
        # Add ROM variants
        usa_rom = ROM(
            filename="Super Mario Bros (USA).nes",
            url="http://example.com/mario_usa.nes",
            size="32KB",
            file_type="NES",
            tags={"USA"},
            platform="nes"
        )
        
        japan_rom = ROM(
            filename="Super Mario Bros (Japan).nes",
            url="http://example.com/mario_japan.nes",
            size="32KB",
            file_type="NES",
            tags={"Japan"},
            platform="nes"
        )
        
        game.add_variant(usa_rom)
        game.add_variant(japan_rom)
        
        self.assertEqual(len(game.variants), 2)
        self.assertEqual(len(game.get_variants_for_platform("nes")), 2)
        
        # Test best variant selection
        best = game.get_best_variant("nes", ["USA", "Japan"])
        self.assertEqual(best.filename, "Super Mario Bros (USA).nes")
    
    def test_game_library(self):
        """Test GameLibrary functionality"""
        library = GameLibrary()
        
        # Create and add a game
        game = Game(
            key="super_mario_bros",
            display_name="Super Mario Bros",
            platforms={"nes"}
        )
        
        rom = ROM(
            filename="Super Mario Bros (USA).nes",
            url="http://example.com/mario.nes",
            size="32KB",
            file_type="NES",
            tags={"USA", "English"},
            platform="nes"
        )
        
        game.add_variant(rom)
        library.add_game(game)
        
        # Test library functionality
        self.assertEqual(len(library.games), 1)
        self.assertEqual(len(library.get_games_for_platform("nes")), 1)
        self.assertIn("USA", library.get_platform_tags("nes"))
        
        # Test selection
        library.select_rom_variant("super_mario_bros", "nes", rom.create_variant_key())
        selection = library.get_selection("super_mario_bros", "nes")
        self.assertIsNotNone(selection)
        self.assertEqual(selection.game_key, "super_mario_bros")


class TestGameLibraryProcessor(unittest.TestCase):
    """Test game library processor"""
    
    def setUp(self):
        self.processor = GameLibraryProcessor()
    
    def test_tag_extraction(self):
        """Test tag extraction from ROM names"""
        test_cases = [
            ("Super Mario Bros (USA).nes", {"USA"}, "Super Mario Bros"),
            ("Zelda (USA, Europe).sfc", {"USA", "Europe"}, "Zelda"),
            ("Final Fantasy [En] (USA).nes", {"En", "USA"}, "Final Fantasy"),
            ("Sonic (Rev A) (USA).bin", {"Rev", "USA"}, "Sonic"),
            ("Mario Kart (USA, Rev 1.1).iso", {"USA", "Rev"}, "Mario Kart")
        ]
        
        for filename, expected_tags, expected_name in test_cases:
            tags, normalized_name = self.processor.extract_tags_and_normalize(filename)
            self.assertEqual(tags, expected_tags, f"Failed for {filename}")
            self.assertEqual(normalized_name, expected_name, f"Failed for {filename}")
    
    def test_game_key_creation(self):
        """Test game key creation"""
        test_cases = [
            ("Super Mario Bros (USA).nes", "super_mario_bros"),
            ("The Legend of Zelda (USA).sfc", "legend_of_zelda"),
            ("Final Fantasy VII (USA).iso", "final_fantasy_vii"),
            ("Street Fighter II (USA).zip", "street_fighter_ii"),
            ("A Bug's Life (USA).nes", "bugs_life")
        ]
        
        for filename, expected_key in test_cases:
            key = self.processor.create_game_key(filename)
            self.assertEqual(key, expected_key, f"Failed for {filename}")
    
    def test_rom_collection_processing(self):
        """Test processing a collection of ROMs"""
        # Create mock RomInfo objects
        rom_infos = [
            RomInfo("Super Mario Bros (USA).nes", "http://example.com/mario_usa.nes", "32KB", "NES"),
            RomInfo("Super Mario Bros (Japan).nes", "http://example.com/mario_japan.nes", "32KB", "NES"),
            RomInfo("Zelda (USA).sfc", "http://example.com/zelda_usa.sfc", "1MB", "SFC"),
        ]
        
        library = self.processor.process_rom_collection(rom_infos, "nes")
        
        # Should have 2 unique games
        self.assertEqual(len(library.games), 2)
        
        # Super Mario Bros should have 2 variants
        mario_game = library.games.get("super_mario_bros")
        self.assertIsNotNone(mario_game)
        self.assertEqual(len(mario_game.variants), 2)
        
        # Zelda should have 1 variant
        zelda_game = library.games.get("zelda")
        self.assertIsNotNone(zelda_game)
        self.assertEqual(len(zelda_game.variants), 1)
        
        # Check tag registry
        platform_tags = library.get_platform_tags("nes")
        self.assertIn("USA", platform_tags)
        self.assertIn("Japan", platform_tags)


class TestIntegration(unittest.TestCase):
    """Integration tests for multiple components"""
    
    def test_end_to_end_workflow(self):
        """Test a complete workflow from ROM info to processed library"""
        # Create ROM collection
        rom_infos = [
            RomInfo("Super Mario Bros (USA).zip", "http://example.com/mario.zip", "32KB", "ZIP"),
            RomInfo("Zelda (Europe).iso", "http://example.com/zelda.iso", "1MB", "ISO"),
        ]
        
        # Process into library
        processor = GameLibraryProcessor()
        library = processor.process_rom_collection(rom_infos, "nes")
        
        # Verify library structure
        self.assertEqual(len(library.games), 2)
        
        # Test selections
        mario_game = library.games["super_mario_bros"]
        mario_variant = list(mario_game.variants.keys())[0]
        library.select_rom_variant("super_mario_bros", "nes", mario_variant)
        
        selected_roms = library.get_selected_roms("nes")
        self.assertEqual(len(selected_roms), 1)
        self.assertEqual(selected_roms[0].filename, "Super Mario Bros (USA).zip")
        
        # Test pipeline manager
        pipeline_manager = ToolPipelineManager()
        tools = pipeline_manager.list_tools()
        self.assertGreater(len(tools), 0)


if __name__ == '__main__':
    unittest.main()