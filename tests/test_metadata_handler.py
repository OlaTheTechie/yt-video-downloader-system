"""
Unit tests for MetadataHandler class.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from services.metadata_handler import MetadataHandler
from models.core import VideoMetadata


class TestMetadataHandler:
    """Test cases for MetadataHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.metadata_handler = MetadataHandler()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Mock video metadata
        self.mock_metadata = VideoMetadata(
            title='Test Video',
            uploader='Test Channel',
            description='Test description with timestamps\n0:00 Introduction\n5:30 Main content\n10:15 Conclusion',
            upload_date='20231201',
            duration=615.5,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123',
            webpage_url='https://youtube.com/watch?v=test123',
            tags=['test', 'video', 'tutorial'],
            categories=['Education'],
            like_count=50,
            dislike_count=5
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_metadata(self):
        """Test saving metadata to JSON file."""
        output_path = self.temp_path / 'test_metadata.json'
        
        self.metadata_handler.save_metadata(self.mock_metadata, str(output_path))
        
        assert output_path.exists()
        
        # Verify content
        with open(output_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data['title'] == 'Test Video'
        assert saved_data['uploader'] == 'Test Channel'
        assert saved_data['video_id'] == 'test123'
        assert saved_data['duration'] == 615.5
        assert saved_data['tags'] == ['test', 'video', 'tutorial']
    
    def test_save_metadata_creates_directory(self):
        """Test that save_metadata creates directory if it doesn't exist."""
        nested_path = self.temp_path / 'nested' / 'directory' / 'metadata.json'
        
        self.metadata_handler.save_metadata(self.mock_metadata, str(nested_path))
        
        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_save_metadata_invalid_path(self):
        """Test saving metadata with invalid path."""
        # Try to save to a path that can't be created (e.g., file as directory)
        invalid_path = self.temp_path / 'file.txt'
        invalid_path.touch()  # Create file
        invalid_nested_path = invalid_path / 'metadata.json'  # Try to use file as directory
        
        with pytest.raises(IOError):
            self.metadata_handler.save_metadata(self.mock_metadata, str(invalid_nested_path))
    
    @patch('requests.Session.get')
    def test_download_thumbnail_success(self, mock_get):
        """Test successful thumbnail download."""
        # Mock successful response
        mock_response = Mock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [b'fake_image_data']
        mock_get.return_value = mock_response
        
        thumbnail_url = 'https://example.com/thumb.jpg'
        output_path = self.temp_path / 'thumbnail.jpg'
        
        self.metadata_handler.download_thumbnail(thumbnail_url, str(output_path))
        
        assert output_path.exists()
        
        # Verify content
        with open(output_path, 'rb') as f:
            content = f.read()
        assert content == b'fake_image_data'
    
    @patch('requests.Session.get')
    def test_download_thumbnail_network_error(self, mock_get):
        """Test thumbnail download with network error."""
        # Mock network error
        import requests
        mock_get.side_effect = requests.RequestException("Network error")
        
        thumbnail_url = 'https://example.com/thumb.jpg'
        output_path = self.temp_path / 'thumbnail.jpg'
        
        with pytest.raises(IOError) as exc_info:
            self.metadata_handler.download_thumbnail(thumbnail_url, str(output_path))
        
        assert "Network error" in str(exc_info.value)
    
    def test_download_thumbnail_empty_url(self):
        """Test thumbnail download with empty URL."""
        output_path = self.temp_path / 'thumbnail.jpg'
        
        with pytest.raises(ValueError) as exc_info:
            self.metadata_handler.download_thumbnail('', str(output_path))
        
        assert "No thumbnail URL provided" in str(exc_info.value)
    
    @patch('yt_dlp.YoutubeDL')
    def test_extract_metadata_success(self, mock_ydl_class):
        """Test successful metadata extraction."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'title': 'Test Video',
            'uploader': 'Test Channel',
            'description': 'Test description',
            'upload_date': '20231201',
            'duration': 300,
            'view_count': 1000,
            'thumbnail': 'https://example.com/thumb.jpg',
            'id': 'test123',
            'webpage_url': 'https://youtube.com/watch?v=test123',
            'tags': ['test', 'video'],
            'categories': ['Education'],
            'like_count': 50,
            'dislike_count': 5
        }
        mock_ydl.extract_info.return_value = mock_info
        
        test_url = 'https://youtube.com/watch?v=test123'
        metadata = self.metadata_handler.extract_metadata(test_url)
        
        assert isinstance(metadata, VideoMetadata)
        assert metadata.title == 'Test Video'
        assert metadata.uploader == 'Test Channel'
        assert metadata.video_id == 'test123'
        assert metadata.duration == 300
        assert metadata.tags == ['test', 'video']
    
    @patch('yt_dlp.YoutubeDL')
    def test_extract_metadata_failure(self, mock_ydl_class):
        """Test metadata extraction failure."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Extraction failed")
        
        test_url = 'https://youtube.com/watch?v=test123'
        
        with pytest.raises(ValueError) as exc_info:
            self.metadata_handler.extract_metadata(test_url)
        
        assert "Extraction failed" in str(exc_info.value)
    
    @patch('yt_dlp.YoutubeDL')
    def test_extract_metadata_no_info(self, mock_ydl_class):
        """Test metadata extraction when no info is returned."""
        # Mock yt-dlp to return None
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = None
        
        test_url = 'https://youtube.com/watch?v=test123'
        
        with pytest.raises(ValueError) as exc_info:
            self.metadata_handler.extract_metadata(test_url)
        
        assert "Could not extract video information" in str(exc_info.value)
    
    def test_extract_description_metadata_with_timestamps(self):
        """Test extracting metadata from description with timestamps."""
        description = """
        This is a test video with timestamps.
        
        0:00 Introduction
        5:30 Main content starts here
        10:15 Advanced topics
        [15:45] Conclusion
        20:30 - Final thoughts
        
        Check out my website: https://example.com
        Follow me on Twitter: https://twitter.com/testuser
        """
        
        metadata = self.metadata_handler.extract_description_metadata(description)
        
        assert metadata['has_timestamps'] is True
        assert len(metadata['timestamps']) >= 5
        assert metadata['has_links'] is True
        assert len(metadata['links']) >= 1
        assert metadata['has_social_media'] is True
        assert len(metadata['social_media_links']) >= 1
        assert metadata['word_count'] > 0
        assert metadata['line_count'] > 0
        
        # Check specific timestamps
        timestamp_values = [t['timestamp'] for t in metadata['timestamps']]
        assert '0:00' in timestamp_values
        assert '5:30' in timestamp_values
        assert '15:45' in timestamp_values
    
    def test_extract_description_metadata_no_timestamps(self):
        """Test extracting metadata from description without timestamps."""
        description = "This is a simple video description without any timestamps."
        
        metadata = self.metadata_handler.extract_description_metadata(description)
        
        assert metadata['has_timestamps'] is False
        assert len(metadata['timestamps']) == 0
        assert metadata['has_links'] is False
        assert metadata['has_social_media'] is False
        assert metadata['word_count'] == 9
    
    def test_extract_description_metadata_empty(self):
        """Test extracting metadata from empty description."""
        metadata = self.metadata_handler.extract_description_metadata('')
        
        assert metadata == {}
    
    def test_timestamp_to_seconds(self):
        """Test converting timestamp strings to seconds."""
        test_cases = [
            ('0:30', 30.0),
            ('5:45', 345.0),
            ('1:23:45', 5025.0),
            ('0:00', 0.0),
            ('invalid', 0.0),
            ('', 0.0)
        ]
        
        for timestamp, expected_seconds in test_cases:
            result = self.metadata_handler._timestamp_to_seconds(timestamp)
            assert result == expected_seconds
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ('Normal Title', 'Normal Title'),
            ('Title with <invalid> chars', 'Title with _invalid_ chars'),
            ('Title/with\\slashes', 'Title_with_slashes'),
            ('Title:with|pipes?', 'Title_with_pipes_'),
            ('Title with "quotes"', 'Title with _quotes_'),
            ('Title*with*asterisks', 'Title_with_asterisks'),
            ('', 'video'),
            ('   ', 'video')
        ]
        
        for input_title, expected in test_cases:
            result = self.metadata_handler._sanitize_filename(input_title)
            assert result == expected
    
    def test_create_metadata_filename(self):
        """Test creating metadata filename."""
        title = 'Test Video Title'
        video_id = 'abc123'
        
        filename = self.metadata_handler.create_metadata_filename(title, video_id)
        
        assert 'Test Video Title' in filename
        assert 'abc123' in filename
        assert filename.endswith('.info.json')
    
    def test_create_metadata_filename_no_id(self):
        """Test creating metadata filename without video ID."""
        title = 'Test Video Title'
        video_id = ''
        
        filename = self.metadata_handler.create_metadata_filename(title, video_id)
        
        assert 'Test Video Title' in filename
        assert filename.endswith('.info.json')
        assert 'abc123' not in filename
    
    def test_create_thumbnail_filename(self):
        """Test creating thumbnail filename."""
        title = 'Test Video Title'
        video_id = 'abc123'
        extension = 'jpg'
        
        filename = self.metadata_handler.create_thumbnail_filename(title, video_id, extension)
        
        assert 'Test Video Title' in filename
        assert 'abc123' in filename
        assert filename.endswith('.jpg')
    
    def test_create_thumbnail_filename_default_extension(self):
        """Test creating thumbnail filename with default extension."""
        title = 'Test Video Title'
        video_id = 'abc123'
        
        filename = self.metadata_handler.create_thumbnail_filename(title, video_id)
        
        assert filename.endswith('.jpg')  # Default extension
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_best_thumbnail_url_success(self, mock_ydl_class):
        """Test getting best thumbnail URL successfully."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'thumbnails': [
                {
                    'url': 'https://example.com/thumb_low.jpg',
                    'width': 320,
                    'height': 180
                },
                {
                    'url': 'https://example.com/maxresdefault.jpg',
                    'width': 1280,
                    'height': 720
                },
                {
                    'url': 'https://example.com/hqdefault.jpg',
                    'width': 480,
                    'height': 360
                }
            ]
        }
        mock_ydl.extract_info.return_value = mock_info
        
        test_url = 'https://youtube.com/watch?v=test123'
        thumbnail_url = self.metadata_handler.get_best_thumbnail_url(test_url)
        
        # Should select maxresdefault (highest quality)
        assert thumbnail_url == 'https://example.com/maxresdefault.jpg'
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_best_thumbnail_url_fallback(self, mock_ydl_class):
        """Test getting best thumbnail URL with fallback."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'thumbnail': 'https://example.com/fallback_thumb.jpg',
            'thumbnails': []  # Empty thumbnails list
        }
        mock_ydl.extract_info.return_value = mock_info
        
        test_url = 'https://youtube.com/watch?v=test123'
        thumbnail_url = self.metadata_handler.get_best_thumbnail_url(test_url)
        
        # Should fallback to main thumbnail
        assert thumbnail_url == 'https://example.com/fallback_thumb.jpg'
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_best_thumbnail_url_failure(self, mock_ydl_class):
        """Test getting best thumbnail URL with extraction failure."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Extraction failed")
        
        test_url = 'https://youtube.com/watch?v=test123'
        thumbnail_url = self.metadata_handler.get_best_thumbnail_url(test_url)
        
        assert thumbnail_url is None
    
    @patch.object(MetadataHandler, 'get_best_thumbnail_url')
    @patch.object(MetadataHandler, 'download_thumbnail')
    def test_download_best_thumbnail_success(self, mock_download, mock_get_url):
        """Test downloading best thumbnail successfully."""
        mock_get_url.return_value = 'https://example.com/best_thumb.jpg'
        mock_download.return_value = None  # Successful download
        
        test_url = 'https://youtube.com/watch?v=test123'
        output_path = str(self.temp_path / 'thumbnail.jpg')
        
        result = self.metadata_handler.download_best_thumbnail(test_url, output_path)
        
        assert result is True
        mock_get_url.assert_called_once_with(test_url)
        mock_download.assert_called_once_with('https://example.com/best_thumb.jpg', output_path)
    
    @patch.object(MetadataHandler, 'get_best_thumbnail_url')
    def test_download_best_thumbnail_no_url(self, mock_get_url):
        """Test downloading best thumbnail when no URL is available."""
        mock_get_url.return_value = None
        
        test_url = 'https://youtube.com/watch?v=test123'
        output_path = str(self.temp_path / 'thumbnail.jpg')
        
        result = self.metadata_handler.download_best_thumbnail(test_url, output_path)
        
        assert result is False