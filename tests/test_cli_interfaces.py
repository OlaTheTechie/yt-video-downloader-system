"""
Unit tests for CLI interfaces and argument validation.
"""

import pytest
from cli.interfaces import ArgumentValidator


class TestArgumentValidator:
    """Test cases for ArgumentValidator class."""
    
    def test_validate_url_valid_youtube_urls(self):
        """Test validation of valid YouTube URLs."""
        valid_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
            'http://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq3KuQEl'
        ]
        
        for url in valid_urls:
            assert ArgumentValidator.validate_url(url), f"URL should be valid: {url}"
    
    def test_validate_url_invalid_urls(self):
        """Test validation of invalid URLs."""
        invalid_urls = [
            'https://www.google.com',
            'https://vimeo.com/123456',
            'not_a_url',
            '',
            None,
            123,
            'https://www.dailymotion.com/video/x123456'
        ]
        
        for url in invalid_urls:
            assert not ArgumentValidator.validate_url(url), f"URL should be invalid: {url}"
    
    def test_validate_output_path_valid_paths(self):
        """Test validation of valid output paths."""
        valid_paths = [
            './downloads',
            '/home/user/videos',
            'C:\\Users\\User\\Downloads',
            'relative/path/to/downloads',
            '/absolute/path/to/downloads',
            '~/Downloads'
        ]
        
        for path in valid_paths:
            assert ArgumentValidator.validate_output_path(path), f"Path should be valid: {path}"
    
    def test_validate_output_path_invalid_paths(self):
        """Test validation of invalid output paths."""
        invalid_paths = [
            'path/with<invalid>chars',
            'path/with:colon',
            'path/with"quotes',
            'path/with|pipe',
            'path/with?question',
            'path/with*asterisk',
            '',
            None,
            123
        ]
        
        for path in invalid_paths:
            assert not ArgumentValidator.validate_output_path(path), f"Path should be invalid: {path}"
    
    def test_sanitize_filename_valid_names(self):
        """Test sanitizing valid filenames."""
        test_cases = [
            ('normal_filename.mp4', 'normal_filename.mp4'),
            ('file with spaces.mp4', 'file with spaces.mp4'),
            ('file-with-dashes.mp4', 'file-with-dashes.mp4'),
            ('file_with_underscores.mp4', 'file_with_underscores.mp4')
        ]
        
        for input_name, expected in test_cases:
            result = ArgumentValidator.sanitize_filename(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_sanitize_filename_invalid_chars(self):
        """Test sanitizing filenames with invalid characters."""
        test_cases = [
            ('file<with>invalid.mp4', 'file_with_invalid.mp4'),
            ('file:with:colons.mp4', 'file_with_colons.mp4'),
            ('file"with"quotes.mp4', 'file_with_quotes.mp4'),
            ('file/with/slashes.mp4', 'file_with_slashes.mp4'),
            ('file\\with\\backslashes.mp4', 'file_with_backslashes.mp4'),
            ('file|with|pipes.mp4', 'file_with_pipes.mp4'),
            ('file?with?questions.mp4', 'file_with_questions.mp4'),
            ('file*with*asterisks.mp4', 'file_with_asterisks.mp4')
        ]
        
        for input_name, expected in test_cases:
            result = ArgumentValidator.sanitize_filename(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_sanitize_filename_edge_cases(self):
        """Test sanitizing filenames with edge cases."""
        test_cases = [
            ('', 'untitled'),
            ('   ', 'untitled'),
            ('...', 'untitled'),
            ('   filename   ', 'filename'),
            ('filename...', 'filename'),
            ('...filename', 'filename'),
            (None, 'untitled')
        ]
        
        for input_name, expected in test_cases:
            result = ArgumentValidator.sanitize_filename(input_name)
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_validate_quality_valid_qualities(self):
        """Test validation of valid quality settings."""
        valid_qualities = [
            'worst', 'best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p'
        ]
        
        for quality in valid_qualities:
            assert ArgumentValidator.validate_quality(quality), f"Quality should be valid: {quality}"
    
    def test_validate_quality_invalid_qualities(self):
        """Test validation of invalid quality settings."""
        invalid_qualities = [
            '4K', '8K', '120p', '1200p', 'high', 'low', 'medium', '', None, 123
        ]
        
        for quality in invalid_qualities:
            assert not ArgumentValidator.validate_quality(quality), f"Quality should be invalid: {quality}"
    
    def test_validate_format_valid_formats(self):
        """Test validation of valid format settings."""
        valid_formats = ['mp4', 'webm', 'mkv']
        
        for format_name in valid_formats:
            assert ArgumentValidator.validate_format(format_name), f"Format should be valid: {format_name}"
    
    def test_validate_format_invalid_formats(self):
        """Test validation of invalid format settings."""
        invalid_formats = ['avi', 'mov', 'flv', 'wmv', '', None, 123]
        
        for format_name in invalid_formats:
            assert not ArgumentValidator.validate_format(format_name), f"Format should be invalid: {format_name}"
    
    def test_validate_parallel_count_valid_counts(self):
        """Test validation of valid parallel download counts."""
        valid_counts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        for count in valid_counts:
            assert ArgumentValidator.validate_parallel_count(count), f"Count should be valid: {count}"
    
    def test_validate_parallel_count_invalid_counts(self):
        """Test validation of invalid parallel download counts."""
        invalid_counts = [0, -1, 11, 15, 100, '5', None, 1.5]
        
        for count in invalid_counts:
            assert not ArgumentValidator.validate_parallel_count(count), f"Count should be invalid: {count}"