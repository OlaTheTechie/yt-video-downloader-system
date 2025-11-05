"""
Unit tests for SubtitleHandler class.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from services.subtitle_handler import SubtitleHandler
from models.core import SubtitleInfo, DownloadConfig, VideoMetadata


class TestSubtitleHandler:
    """Test cases for SubtitleHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.subtitle_handler = SubtitleHandler()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Mock video metadata
        self.mock_metadata = VideoMetadata(
            title='Test Video',
            uploader='Test Channel',
            description='Test description',
            upload_date='20231201',
            duration=615.5,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123',
            webpage_url='https://youtube.com/watch?v=test123'
        )
        
        # Mock download config
        self.mock_config = DownloadConfig(
            output_directory=str(self.temp_path),
            download_subtitles=True,
            subtitle_languages=['en', 'es'],
            subtitle_format='srt',
            auto_generated_subtitles=True
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_language_name(self):
        """Test language name mapping."""
        assert self.subtitle_handler._get_language_name('en') == 'English'
        assert self.subtitle_handler._get_language_name('es') == 'Spanish'
        assert self.subtitle_handler._get_language_name('unknown') == 'UNKNOWN'
    
    def test_extract_video_id_youtube(self):
        """Test video ID extraction from YouTube URLs."""
        test_urls = [
            ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
            ('https://youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
            ('https://youtube.com/embed/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
            ('https://youtube.com/v/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
            ('https://example.com/video', None)
        ]
        
        for url, expected_id in test_urls:
            result = self.subtitle_handler._extract_video_id(url)
            assert result == expected_id
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ('Normal Title', 'Normal Title'),
            ('Title with <invalid> chars', 'Title with _invalid_ chars'),
            ('Title/with\\path|chars', 'Title_with_path_chars'),
            ('Very long title ' * 20, 'Very long title ' * 7 + 'Very long title Ver'),  # Truncated
            ('', 'video')  # Empty fallback
        ]
        
        for input_title, expected in test_cases:
            result = self.subtitle_handler._sanitize_filename(input_title)
            assert len(result) <= 150
            if expected == 'video':
                assert result == expected
            else:
                assert result.startswith(expected[:50])  # Check prefix due to truncation
    
    def test_validate_subtitle_format(self):
        """Test subtitle format validation."""
        valid_formats = ['srt', 'vtt', 'ass', 'ttml', 'json3']
        invalid_formats = ['txt', 'doc', 'invalid']
        
        for fmt in valid_formats:
            assert self.subtitle_handler.validate_subtitle_format(fmt) is True
        
        for fmt in invalid_formats:
            assert self.subtitle_handler.validate_subtitle_format(fmt) is False
    
    def test_filter_preferred_languages(self):
        """Test filtering subtitles by preferred languages."""
        available_subtitles = [
            SubtitleInfo('en', 'English', False, ['srt']),
            SubtitleInfo('es', 'Spanish', False, ['srt']),
            SubtitleInfo('fr', 'French', True, ['vtt']),
            SubtitleInfo('de', 'German', False, ['srt'])
        ]
        
        # Test with specific preferences
        filtered = self.subtitle_handler.filter_preferred_languages(
            available_subtitles, ['en', 'es']
        )
        assert len(filtered) == 2
        assert all(sub.language in ['en', 'es'] for sub in filtered)
        
        # Test with no preferences (should return all)
        filtered = self.subtitle_handler.filter_preferred_languages(
            available_subtitles, []
        )
        assert len(filtered) == 4
        
        # Test with unavailable language (should fallback to English)
        filtered = self.subtitle_handler.filter_preferred_languages(
            available_subtitles, ['zh']
        )
        assert len(filtered) == 1
        assert filtered[0].language == 'en'
    
    def test_get_subtitle_summary(self):
        """Test subtitle summary generation."""
        available_subtitles = [
            SubtitleInfo('en', 'English', False, ['srt', 'vtt']),
            SubtitleInfo('es', 'Spanish', True, ['srt']),
            SubtitleInfo('fr', 'French', False, ['vtt'])
        ]
        
        summary = self.subtitle_handler.get_subtitle_summary(available_subtitles)
        
        assert summary['total_count'] == 3
        assert summary['manual_count'] == 2
        assert summary['auto_generated_count'] == 1
        assert set(summary['languages']) == {'en', 'es', 'fr'}
        assert set(summary['formats']) == {'srt', 'vtt'}
        
        # Test empty list
        empty_summary = self.subtitle_handler.get_subtitle_summary([])
        assert empty_summary['total_count'] == 0
        assert empty_summary['languages'] == []
    
    def test_create_subtitle_filename(self):
        """Test subtitle filename creation."""
        # Test manual subtitle
        filename = self.subtitle_handler.create_subtitle_filename(
            'Test Video', 'abc123', 'en', 'srt', False
        )
        assert filename == 'Test Video_abc123.en.srt'
        
        # Test auto-generated subtitle
        filename = self.subtitle_handler.create_subtitle_filename(
            'Test Video', 'abc123', 'en', 'srt', True
        )
        assert filename == 'Test Video_abc123.en.auto.srt'
        
        # Test with special characters in title
        filename = self.subtitle_handler.create_subtitle_filename(
            'Test/Video<>Title', 'abc123', 'es', 'vtt', False
        )
        assert filename == 'Test_Video__Title_abc123.es.vtt'
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_available_subtitles(self, mock_ydl_class):
        """Test getting available subtitles from video."""
        # Mock yt-dlp response
        mock_info = {
            'subtitles': {
                'en': [{'ext': 'srt'}, {'ext': 'vtt'}],
                'es': [{'ext': 'srt'}]
            },
            'automatic_captions': {
                'en': [{'ext': 'srt'}],
                'fr': [{'ext': 'vtt'}]
            }
        }
        
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Test subtitle extraction
        subtitles = self.subtitle_handler.get_available_subtitles('https://youtube.com/watch?v=test')
        
        assert len(subtitles) == 4  # 2 manual + 2 auto
        
        # Check manual subtitles
        manual_subs = [s for s in subtitles if not s.is_auto_generated]
        assert len(manual_subs) == 2
        
        # Check auto-generated subtitles
        auto_subs = [s for s in subtitles if s.is_auto_generated]
        assert len(auto_subs) == 2
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_available_subtitles_error(self, mock_ydl_class):
        """Test error handling in subtitle extraction."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = None
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        with pytest.raises(ValueError, match="Could not extract video information"):
            self.subtitle_handler.get_available_subtitles('https://youtube.com/watch?v=invalid')
    
    def test_organize_subtitles_with_video(self):
        """Test organizing subtitle files alongside video."""
        # Create test video file
        video_path = self.temp_path / 'test_video.mp4'
        video_path.touch()
        
        # Create test subtitle files
        subtitle_files = [
            str(self.temp_path / 'subtitle.en.srt'),
            str(self.temp_path / 'subtitle.es.auto.srt')
        ]
        
        for sub_file in subtitle_files:
            Path(sub_file).touch()
        
        # Test organization
        organized = self.subtitle_handler.organize_subtitles_with_video(
            str(video_path), subtitle_files
        )
        
        assert len(organized) == 2
        
        # Check that files were renamed to match video
        expected_files = [
            str(self.temp_path / 'test_video.en.srt'),
            str(self.temp_path / 'test_video.es.auto.srt')
        ]
        
        for expected_file in expected_files:
            assert any(expected_file in org_file for org_file in organized)
    
    def test_organize_subtitles_missing_video(self):
        """Test organizing subtitles when video file doesn't exist."""
        subtitle_files = [str(self.temp_path / 'subtitle.en.srt')]
        Path(subtitle_files[0]).touch()
        
        # Test with non-existent video
        organized = self.subtitle_handler.organize_subtitles_with_video(
            str(self.temp_path / 'nonexistent.mp4'), subtitle_files
        )
        
        # Should return original files unchanged
        assert organized == subtitle_files
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_subtitles_disabled(self, mock_ydl_class):
        """Test subtitle download when disabled in config."""
        config = DownloadConfig(download_subtitles=False)
        
        result = self.subtitle_handler.download_subtitles(
            'https://youtube.com/watch?v=test',
            str(self.temp_path),
            config
        )
        
        assert result == []
        mock_ydl_class.assert_not_called()
    
    @patch('yt_dlp.YoutubeDL')
    @patch('os.path.exists')
    def test_download_subtitles_success(self, mock_exists, mock_ydl_class):
        """Test successful subtitle download."""
        # Mock yt-dlp
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Mock file existence checks
        def mock_exists_side_effect(path):
            return 'test_video_test123.en.srt' in path or 'test_video_test123.es.srt' in path
        
        mock_exists.side_effect = mock_exists_side_effect
        
        # Test download
        result = self.subtitle_handler.download_subtitles(
            'https://youtube.com/watch?v=test123',
            str(self.temp_path),
            self.mock_config,
            self.mock_metadata
        )
        
        # Verify yt-dlp was called with correct options
        mock_ydl.download.assert_called_once_with(['https://youtube.com/watch?v=test123'])
        
        # Check that download was attempted
        call_args = mock_ydl_class.call_args[0][0]
        assert call_args['writesubtitles'] is True
        assert call_args['subtitleslangs'] == ['en', 'es']
        assert call_args['subtitlesformat'] == 'srt'
        assert call_args['skip_download'] is True