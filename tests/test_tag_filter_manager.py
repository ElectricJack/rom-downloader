"""
Test cases for TagFilterManager

Tests the tag filtering functionality including:
- UI component setup
- Tag button creation and management
- Custom tag input and auto-completion
- Filter state management
- Callback functionality
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import ttk

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui.managers.tag_filter_manager import TagFilterManager


class TestTagFilterManager(unittest.TestCase):
    """Test cases for TagFilterManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during testing
        
        # Mock parent GUI
        self.mock_parent_gui = Mock()
        
        # Create TagFilterManager instance
        self.manager = TagFilterManager(self.mock_parent_gui)
        
        # Set up a test parent widget
        self.test_parent = ttk.Frame(self.root)
    
    def tearDown(self):
        """Clean up after tests"""
        self.root.destroy()
    
    def test_initialization(self):
        """Test TagFilterManager initialization"""
        # Check that all attributes are initialized correctly
        self.assertEqual(self.manager.parent_gui, self.mock_parent_gui)
        self.assertIsNone(self.manager.tag_frame)
        self.assertIsNone(self.manager.custom_tag_entry)
        self.assertEqual(self.manager.tag_buttons, {})
        self.assertEqual(self.manager.tag_variables, {})
        self.assertEqual(self.manager.active_tag_filters, set())
        self.assertEqual(self.manager.custom_tag_filters, set())
        self.assertEqual(self.manager.available_other_tags, set())
        self.assertFalse(self.manager.completion_visible)
    
    def test_setup_tag_filters(self):
        """Test tag filter UI setup"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Check that main components are created
        self.assertIsNotNone(self.manager.tag_frame)
        self.assertIsNotNone(self.manager.tag_groups_container)
        self.assertIsNotNone(self.manager.clear_filters_button)
        self.assertIsNotNone(self.manager.custom_tag_frame)
        self.assertIsNotNone(self.manager.custom_tag_entry)
        self.assertIsNotNone(self.manager.completion_listbox)
        
        # Check that the main frame is properly configured
        self.assertEqual(self.manager.tag_frame.cget('text'), 'Filter by Tags')
    
    def test_setup_custom_tag_input(self):
        """Test custom tag input setup"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Check custom tag components
        self.assertIsNotNone(self.manager.custom_tag_var)
        self.assertIsNotNone(self.manager.add_tag_button)
        self.assertIsNotNone(self.manager.active_tags_frame)
        self.assertIsNotNone(self.manager.completion_frame)
        
        # Check initial state
        self.assertEqual(self.manager.custom_tag_var.get(), "")
        self.assertFalse(self.manager.completion_visible)
    
    def test_update_tag_buttons(self):
        """Test updating tag buttons for a platform"""
        self.manager.setup_tag_filters(self.test_parent)
        
        categorized_tags = {
            'language': {'English', 'Japanese', 'French'},
            'country': {'USA', 'Japan', 'Europe'},
            'other': {'Prototype', 'Beta', 'Demo'}
        }
        
        self.manager.update_tag_buttons('TestPlatform', categorized_tags)
        
        # Check that available other tags are set
        self.assertEqual(self.manager.available_other_tags, categorized_tags['other'])
        
        # Check that language and country group frames are created
        self.assertIsNotNone(self.manager.language_group_frame)
        self.assertIsNotNone(self.manager.country_group_frame)
    
    def test_create_tag_buttons(self):
        """Test creation of tag buttons"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Create a test frame
        test_frame = ttk.LabelFrame(self.manager.tag_groups_container, text="Test")
        tags = {'Tag1', 'Tag2', 'Tag3'}
        
        self.manager.create_tag_buttons(test_frame, tags)
        
        # Check that buttons and variables are created
        self.assertEqual(len(self.manager.tag_buttons), 3)
        self.assertEqual(len(self.manager.tag_variables), 3)
        
        # Check that all tags are represented
        for tag in tags:
            self.assertIn(tag, self.manager.tag_buttons)
            self.assertIn(tag, self.manager.tag_variables)
            self.assertIsInstance(self.manager.tag_variables[tag], tk.BooleanVar)
    
    def test_on_tag_filter_change(self):
        """Test tag filter change handling"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Mock the callback
        mock_callback = Mock()
        self.manager.set_filters_changed_callback(mock_callback)
        
        # Create test variables
        test_var = tk.BooleanVar()
        self.manager.tag_variables['TestTag'] = test_var
        
        # Test adding filter
        test_var.set(True)
        self.manager.on_tag_filter_change('TestTag')
        
        self.assertIn('TestTag', self.manager.active_tag_filters)
        mock_callback.assert_called_once()
        
        # Test removing filter
        mock_callback.reset_mock()
        test_var.set(False)
        self.manager.on_tag_filter_change('TestTag')
        
        self.assertNotIn('TestTag', self.manager.active_tag_filters)
        mock_callback.assert_called_once()
    
    def test_add_custom_tag(self):
        """Test adding custom tags"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Mock the callback
        mock_callback = Mock()
        self.manager.set_filters_changed_callback(mock_callback)
        
        # Set available tags for matching
        self.manager.available_other_tags = {'Prototype', 'Beta', 'Demo'}
        
        # Test adding exact match
        self.manager.custom_tag_var.set('Prototype')
        self.manager.add_custom_tag()
        
        self.assertIn('Prototype', self.manager.custom_tag_filters)
        self.assertIn('Prototype', self.manager.active_tag_filters)
        self.assertEqual(self.manager.custom_tag_var.get(), "")
        mock_callback.assert_called_once()
        
        # Test adding custom text
        mock_callback.reset_mock()
        self.manager.custom_tag_var.set('CustomTag')
        self.manager.add_custom_tag()
        
        self.assertIn('CustomTag', self.manager.custom_tag_filters)
        self.assertIn('CustomTag', self.manager.active_tag_filters)
        mock_callback.assert_called_once()
    
    def test_remove_custom_tag(self):
        """Test removing custom tags"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Mock the callback
        mock_callback = Mock()
        self.manager.set_filters_changed_callback(mock_callback)
        
        # Add a custom tag first
        self.manager.custom_tag_filters.add('TestTag')
        self.manager.active_tag_filters.add('TestTag')
        
        # Create a mock button frame
        mock_frame = Mock()
        self.manager.active_tag_buttons['TestTag'] = mock_frame
        
        # Remove the tag
        self.manager.remove_custom_tag('TestTag')
        
        self.assertNotIn('TestTag', self.manager.custom_tag_filters)
        self.assertNotIn('TestTag', self.manager.active_tag_filters)
        mock_frame.destroy.assert_called_once()
        self.assertNotIn('TestTag', self.manager.active_tag_buttons)
        mock_callback.assert_called_once()
    
    def test_clear_tag_filters(self):
        """Test clearing all tag filters"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Mock the callback
        mock_callback = Mock()
        self.manager.set_filters_changed_callback(mock_callback)
        
        # Add some test data
        test_var1 = tk.BooleanVar(value=True)
        test_var2 = tk.BooleanVar(value=True)
        self.manager.tag_variables['Tag1'] = test_var1
        self.manager.tag_variables['Tag2'] = test_var2
        self.manager.active_tag_filters.update(['Tag1', 'Tag2'])
        
        # Clear filters
        self.manager.clear_tag_filters()
        
        # Check that everything is cleared
        self.assertEqual(len(self.manager.active_tag_filters), 0)
        self.assertFalse(test_var1.get())
        self.assertFalse(test_var2.get())
        mock_callback.assert_called_once()
    
    def test_clear_custom_tags(self):
        """Test clearing custom tags only"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Add test data
        self.manager.custom_tag_filters.add('CustomTag')
        self.manager.custom_tag_var.set('some text')
        
        # Create mock button frames
        mock_frame1 = Mock()
        mock_frame2 = Mock()
        self.manager.active_tag_buttons['CustomTag'] = mock_frame1
        self.manager.active_tag_buttons['AnotherTag'] = mock_frame2
        
        # Clear custom tags
        self.manager.clear_custom_tags()
        
        # Check results
        self.assertEqual(len(self.manager.custom_tag_filters), 0)
        self.assertEqual(self.manager.custom_tag_var.get(), "")
        self.assertEqual(len(self.manager.active_tag_buttons), 0)
        mock_frame1.destroy.assert_called_once()
        mock_frame2.destroy.assert_called_once()
    
    def test_auto_completion_functionality(self):
        """Test auto-completion features"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Set up available tags
        self.manager.available_other_tags = {'Prototype', 'Proto-Alpha', 'Beta', 'Demo'}
        
        # Test showing completion for partial match
        self.manager.custom_tag_var.set('Pro')
        self.manager.update_auto_completion()
        
        self.assertTrue(self.manager.completion_visible)
        
        # Test hiding completion for empty input
        self.manager.custom_tag_var.set('')
        self.manager.update_auto_completion()
        
        self.assertFalse(self.manager.completion_visible)
    
    def test_completion_navigation(self):
        """Test navigation through completion options"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Set up completion list
        matches = ['Prototype', 'Proto-Alpha', 'Beta']
        self.manager.show_completion(matches)
        
        # Test navigation down
        self.manager.navigate_completion('Down')
        selection = self.manager.completion_listbox.curselection()
        self.assertEqual(selection, (1,))
        
        # Test navigation up
        self.manager.navigate_completion('Up')
        selection = self.manager.completion_listbox.curselection()
        self.assertEqual(selection, (0,))
    
    def test_completion_selection(self):
        """Test selecting from completion list"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Set up completion list
        matches = ['Prototype', 'Beta', 'Demo']
        self.manager.show_completion(matches)
        
        # Clear the auto-selection and select the item we want
        self.manager.completion_listbox.selection_clear(0, tk.END)
        self.manager.completion_listbox.selection_set(1)
        self.manager.select_completion()
        
        # Check that the selected item is set in the entry
        self.assertEqual(self.manager.custom_tag_var.get(), 'Beta')
        self.assertFalse(self.manager.completion_visible)
    
    def test_get_active_filters(self):
        """Test getting active filters"""
        # Add some test filters
        self.manager.active_tag_filters.update(['Tag1', 'Tag2', 'CustomTag'])
        
        # Get active filters
        active = self.manager.get_active_filters()
        
        # Check that we get a copy, not the original set
        self.assertEqual(active, {'Tag1', 'Tag2', 'CustomTag'})
        self.assertIsNot(active, self.manager.active_tag_filters)
    
    def test_callback_functionality(self):
        """Test callback setting and invocation"""
        mock_callback = Mock()
        
        # Set callback
        self.manager.set_filters_changed_callback(mock_callback)
        self.assertEqual(self.manager.on_filters_changed, mock_callback)
        
        # Test that callback is called
        self.manager._notify_filters_changed()
        mock_callback.assert_called_once()
    
    def test_event_handlers(self):
        """Test various event handlers"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Test return key handling
        with patch.object(self.manager, 'add_custom_tag') as mock_add:
            result = self.manager.on_tag_entry_return(Mock())
            mock_add.assert_called_once()
            self.assertEqual(result, 'break')
        
        # Test completion selection event
        with patch.object(self.manager, 'select_completion') as mock_select:
            self.manager.on_completion_select()
            mock_select.assert_called_once()
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Test adding empty tag
        self.manager.custom_tag_var.set('')
        initial_count = len(self.manager.custom_tag_filters)
        self.manager.add_custom_tag()
        self.assertEqual(len(self.manager.custom_tag_filters), initial_count)
        
        # Test removing non-existent tag
        initial_count = len(self.manager.custom_tag_filters)
        self.manager.remove_custom_tag('NonExistentTag')
        self.assertEqual(len(self.manager.custom_tag_filters), initial_count)
        
        # Test navigation with empty completion list
        self.manager.completion_visible = True
        self.manager.navigate_completion('Down')  # Should not crash
        
        # Test selection with no completion visible
        self.manager.completion_visible = False
        self.manager.select_completion()  # Should not crash
    
    def test_duplicate_tag_handling(self):
        """Test handling of duplicate tags"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Add a tag
        self.manager.custom_tag_var.set('TestTag')
        self.manager.add_custom_tag()
        initial_count = len(self.manager.custom_tag_filters)
        
        # Try to add the same tag again
        self.manager.custom_tag_var.set('TestTag')
        self.manager.add_custom_tag()
        
        # Should not increase count
        self.assertEqual(len(self.manager.custom_tag_filters), initial_count)
    
    def test_case_insensitive_matching(self):
        """Test case-insensitive tag matching"""
        self.manager.setup_tag_filters(self.test_parent)
        
        # Set up available tags
        self.manager.available_other_tags = {'Prototype', 'Beta', 'Demo'}
        
        # Test case-insensitive match
        self.manager.custom_tag_var.set('prototype')  # lowercase
        self.manager.add_custom_tag()
        
        # Should match the exact case from available tags
        self.assertIn('Prototype', self.manager.custom_tag_filters)
        self.assertNotIn('prototype', self.manager.custom_tag_filters)


class TestTagFilterManagerIntegration(unittest.TestCase):
    """Integration tests for TagFilterManager"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Create a more realistic parent GUI mock
        self.mock_parent_gui = Mock()
        self.manager = TagFilterManager(self.mock_parent_gui)
        
        # Set up test data
        self.test_categorized_tags = {
            'language': {'English', 'Japanese', 'French', 'German'},
            'country': {'USA', 'Japan', 'Europe', 'World'},
            'other': {'Prototype', 'Beta', 'Demo', 'Final', 'Rev A', 'Rev B'}
        }
    
    def tearDown(self):
        """Clean up after integration tests"""
        self.root.destroy()
    
    def test_full_workflow(self):
        """Test complete tag filtering workflow"""
        # Set up UI
        test_parent = ttk.Frame(self.root)
        self.manager.setup_tag_filters(test_parent)
        
        # Set up callback
        filter_changes = []
        def capture_changes():
            filter_changes.append(self.manager.get_active_filters().copy())
        
        self.manager.set_filters_changed_callback(capture_changes)
        
        # Update with platform tags
        self.manager.update_tag_buttons('TestPlatform', self.test_categorized_tags)
        
        # Simulate user interactions
        # 1. Select a language tag
        if 'English' in self.manager.tag_variables:
            self.manager.tag_variables['English'].set(True)
            self.manager.on_tag_filter_change('English')
        
        # 2. Add a custom tag
        self.manager.custom_tag_var.set('Prototype')
        self.manager.add_custom_tag()
        
        # 3. Select a country tag
        if 'USA' in self.manager.tag_variables:
            self.manager.tag_variables['USA'].set(True)
            self.manager.on_tag_filter_change('USA')
        
        # Check that filters were applied correctly
        final_filters = self.manager.get_active_filters()
        expected_filters = {'English', 'USA', 'Prototype'}
        
        # We should have at least the filters we added
        self.assertTrue(expected_filters.issubset(final_filters))
        
        # Check that callback was called for each change
        self.assertGreater(len(filter_changes), 0)
        
        # Test clearing all filters
        self.manager.clear_tag_filters()
        self.assertEqual(len(self.manager.get_active_filters()), 0)
    
    def test_multiple_platform_switches(self):
        """Test switching between platforms"""
        test_parent = ttk.Frame(self.root)
        self.manager.setup_tag_filters(test_parent)
        
        # Test first platform
        platform1_tags = {
            'language': {'English', 'Japanese'},
            'country': {'USA', 'Japan'},
            'other': {'Prototype', 'Beta'}
        }
        
        self.manager.update_tag_buttons('Platform1', platform1_tags)
        initial_other_tags = self.manager.available_other_tags.copy()
        
        # Add some filters
        self.manager.custom_tag_var.set('Prototype')
        self.manager.add_custom_tag()
        
        # Switch to second platform
        platform2_tags = {
            'language': {'French', 'German'},
            'country': {'Europe', 'World'},
            'other': {'Demo', 'Final'}
        }
        
        self.manager.update_tag_buttons('Platform2', platform2_tags)
        
        # Check that available tags changed
        self.assertNotEqual(initial_other_tags, self.manager.available_other_tags)
        self.assertEqual(self.manager.available_other_tags, platform2_tags['other'])
        
        # Check that custom filters were cleared
        self.assertEqual(len(self.manager.custom_tag_filters), 0)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)