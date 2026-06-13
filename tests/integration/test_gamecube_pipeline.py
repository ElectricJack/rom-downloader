#!/usr/bin/env python3
"""
Test script to verify GameCube tool pipeline configuration
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config.enhanced_config_manager import EnhancedConfigManager
from tools.pipeline_manager import ToolPipelineManager

def test_gamecube_pipeline():
    """Test GameCube platform tool pipeline configuration"""
    
    # Initialize config manager
    config = EnhancedConfigManager()
    
    # Get GameCube platform configuration
    platform_config = config.get_platform_config('GameCube')
    print("GameCube Platform Config:")
    print(f"  Name: {platform_config.get('name')}")
    print(f"  Extract Archives: {platform_config.get('extract_archives')}")
    print(f"  Tool Pipeline: {platform_config.get('tool_pipeline', 'None')}")
    print()
    
    # Get tool pipeline for GameCube
    pipeline = config.get_platform_tool_pipeline('GameCube')
    print("Generated Tool Pipeline:")
    for i, step in enumerate(pipeline):
        print(f"  Step {i+1}: {step.tool_id}")
        print(f"    Parameters: {step.parameters}")
        print(f"    Conditions: {step.conditions}")
    print()
    
    # Initialize tool pipeline manager
    tool_manager = ToolPipelineManager()
    
    # Check if zip_extractor tool is registered
    zip_tool = tool_manager.get_tool('zip_extractor')
    if zip_tool:
        print("ZipExtractorTool is registered:")
        print(f"  Tool ID: {zip_tool.tool_id}")
        print(f"  Description: {zip_tool.description}")
        print(f"  Supported Types: {zip_tool.supported_file_types}")
        print(f"  Default Parameters: {zip_tool.get_default_parameters()}")
    else:
        print("ERROR: ZipExtractorTool is NOT registered!")
    print()
    
    # Validate the pipeline
    if pipeline:
        errors = tool_manager.validate_pipeline(pipeline)
        if errors:
            print("Pipeline Validation Errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Pipeline validation: PASSED")
    else:
        print("No pipeline configured for GameCube")

if __name__ == "__main__":
    test_gamecube_pipeline()