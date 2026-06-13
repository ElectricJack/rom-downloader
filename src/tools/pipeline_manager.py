"""
Tool pipeline manager for orchestrating ROM processing.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable

from src.tools.base import ToolHandler, ToolStep, ProcessingResult
from src.tools.zip_extractor import ZipExtractorTool
from src.tools.chd_converter import CHDConverterTool
from src.tools.xbox_extractor import XboxExtractorTool

logger = logging.getLogger(__name__)


class ToolPipelineManager:
    """Manages tool pipelines for ROM processing"""
    
    def __init__(self):
        self.tool_handlers: Dict[str, ToolHandler] = {}
        self.register_default_tools()
    
    def register_default_tools(self):
        """Register all built-in tool handlers"""
        tools = [
            ZipExtractorTool(),
            CHDConverterTool(),
            XboxExtractorTool(),
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    def register_tool(self, tool: ToolHandler):
        """Register a new tool handler"""
        self.tool_handlers[tool.tool_id] = tool
        logger.info(f"Registered tool: {tool.tool_id} - {tool.description}")
    
    def get_tool(self, tool_id: str) -> Optional[ToolHandler]:
        """Get a tool handler by ID"""
        return self.tool_handlers.get(tool_id)
    
    def list_tools(self) -> List[str]:
        """List all available tool IDs"""
        return list(self.tool_handlers.keys())
    
    def get_tool_info(self, tool_id: str) -> Optional[Dict]:
        """Get information about a tool"""
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        
        return {
            'tool_id': tool.tool_id,
            'description': tool.description,
            'supported_file_types': tool.supported_file_types,
            'default_parameters': tool.get_default_parameters()
        }
    
    def validate_pipeline(self, pipeline_config: List[ToolStep]) -> List[str]:
        """Validate a pipeline configuration and return any errors"""
        errors = []
        
        for i, step in enumerate(pipeline_config):
            tool = self.get_tool(step.tool_id)
            if not tool:
                errors.append(f"Step {i}: Unknown tool '{step.tool_id}'")
                continue
            
            # Validate tool parameters
            if not tool.validate_parameters(step.parameters):
                errors.append(f"Step {i}: Invalid parameters for tool '{step.tool_id}'")
        
        return errors
    
    def process_rom(self, rom_path: Path, platform: str, 
                   pipeline_config: List[ToolStep], 
                   output_dir: Path,
                   progress_callback: Optional[Callable[[str, int, int], None]] = None) -> ProcessingResult:
        """Process a ROM through the configured tool pipeline"""
        
        # Validate pipeline first
        errors = self.validate_pipeline(pipeline_config)
        if errors:
            return ProcessingResult(
                success=False,
                output_files=[],
                error_message=f"Pipeline validation failed: {'; '.join(errors)}"
            )
        
        # Start with the original ROM file
        current_files = [rom_path]
        all_output_files = []
        step_results = []
        
        logger.info(f"Starting pipeline processing for {rom_path} on platform {platform}")
        
        for i, step in enumerate(pipeline_config):
            # Update progress
            if progress_callback:
                progress_callback(f"{step.tool_id}", i, len(pipeline_config))
                
            tool = self.get_tool(step.tool_id)
            if not tool:
                return ProcessingResult(
                    success=False,
                    output_files=[],
                    error_message=f"Tool not found: {step.tool_id}"
                )
            
            logger.info(f"Step {i+1}: Running tool {step.tool_id}")
            
            # Check conditions
            if not self._check_conditions(step.conditions, current_files, platform):
                logger.info(f"Step {i+1}: Conditions not met, skipping")
                continue
            
            # Check if tool can process current files
            if not tool.can_process(current_files, step.parameters):
                logger.info(f"Step {i+1}: Tool cannot process current files, skipping")
                continue
            
            # Merge default parameters with step parameters
            merged_params = tool.get_default_parameters()
            merged_params.update(step.parameters)
            
            # Process files
            result = tool.process(current_files, output_dir, merged_params)
            step_results.append({
                'step': i+1,
                'tool_id': step.tool_id,
                'success': result.success,
                'input_files': [str(f) for f in current_files],
                'output_files': [str(f) for f in result.output_files],
                'metadata': result.metadata
            })
            
            if not result.success:
                logger.error(f"Step {i+1}: Tool {step.tool_id} failed: {result.error_message}")
                return ProcessingResult(
                    success=False,
                    output_files=[],
                    error_message=f"Step {i+1} failed: {result.error_message}",
                    metadata={'step_results': step_results}
                )
            
            # Update current files for next step
            if result.output_files:
                current_files = result.output_files
                all_output_files.extend(result.output_files)
            else:
                # If no output files, keep current files for next step
                all_output_files.extend(current_files)
            
            logger.info(f"Step {i+1}: Completed successfully, produced {len(result.output_files)} files")
        
        # If no steps were executed, return the original file
        if not step_results:
            all_output_files = [rom_path]
        
        return ProcessingResult(
            success=True,
            output_files=all_output_files,
            metadata={
                'pipeline_completed': True,
                'steps_executed': len(step_results),
                'step_results': step_results
            }
        )
    
    def _check_conditions(self, conditions: Dict[str, any], 
                         files: List[Path], platform: str) -> bool:
        """Check if conditions are met for running a tool step"""
        if not conditions:
            return True
        
        # Check platform condition
        if 'platform' in conditions:
            required_platform = conditions['platform']
            if isinstance(required_platform, str):
                if required_platform.lower() != platform.lower():
                    return False
            elif isinstance(required_platform, list):
                if platform.lower() not in [p.lower() for p in required_platform]:
                    return False
        
        # Check file type condition
        if 'file_types' in conditions:
            required_types = conditions['file_types']
            if not isinstance(required_types, list):
                required_types = [required_types]
            
            # Convert to lowercase for comparison
            required_types = [t.lower() for t in required_types]
            
            # Check if any file matches required types
            if not any(f.suffix.lower() in required_types for f in files):
                return False
        
        # Check file exists condition
        if 'file_exists' in conditions:
            required_files = conditions['file_exists']
            if not isinstance(required_files, list):
                required_files = [required_files]
            
            for req_file in required_files:
                if not Path(req_file).exists():
                    return False
        
        return True