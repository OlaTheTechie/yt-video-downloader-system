"""
Unit tests for QualitySelector class.
"""

import pytest
from unittest.mock import Mock, patch

from services.quality_selector import QualitySelector
from models.core import FormatPreferences


class TestQualitySelector:
    """Test cases for QualitySelector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.quality_selector = QualitySelector()
        
        # Mock format data for testing
        self.mock_formats = [
            {
                'format_id': '137',
                'ext': 'mp4',
                'height': 1080,
                'width': 1920,
                'vcodec': 'avc1.640028',
                'acodec': 'none',
                'vbr': 2500,
                'abr': None
            },
            {
                'format_id': '136',
                'ext': 'mp4',
                'height': 720,
                'width': 1280,
                'vcodec': 'avc1.4d401f',
                'acodec': 'none',
                'vbr': 1500,
                'abr': None
            },
            {
                'format_id': '135',
                'ext': 'mp4',
                'height': 480,
                'width': 854,
                'vcodec': 'avc1.4d401e',
                'acodec': 'none',
                'vbr': 800,
                'abr': None
            },
            {
                'format_id': '140',
                'ext': 'm4a',
                'height': None,
                'width': None,
                'vcodec': 'none',
                'acodec': 'mp4a.40.2',
                'vbr': None,
                'abr': 128
            },
            {
                'format_id': '251',
                'ext': 'webm',
                'height': None,
                'width': None,
                'vcodec': 'none',
                'acodec': 'opus',
                'vbr': None,
                'abr': 160
            }
        ]
    
    def test_select_best_overall(self):
        """Test selecting best overall quality format."""
        result = self.quality_selector._select_best_overall(self.mock_formats)
        
        # Should select 1080p format (highest resolution)
        assert result['height'] == 1080
        assert result['format_id'] == '137'
    
    def test_select_worst_overall(self):
        """Test selecting worst overall quality format."""
        result = self.quality_selector._select_worst_overall(self.mock_formats)
        
        # Should select 480p format (lowest resolution)
        assert result['height'] == 480
        assert result['format_id'] == '135'
    
    def test_select_by_resolution_exact(self):
        """Test selecting format by exact resolution."""
        result = self.quality_selector._select_by_resolution(self.mock_formats, '720p')
        
        # Should select 720p format
        assert result['height'] == 720
        assert result['format_id'] == '136'
    
    def test_select_by_resolution_lower(self):
        """Test selecting format by resolution when exact not available."""
        result = self.quality_selector._select_by_resolution(self.mock_formats, '600p')
        
        # Should select 480p format (highest available below 600p)
        assert result['height'] == 480
        assert result['format_id'] == '135'
    
    def test_select_audio_only(self):
        """Test selecting audio-only format."""
        result = self.quality_selector._select_audio_only(self.mock_formats)
        
        # Should select opus format (higher bitrate)
        assert result['vcodec'] == 'none'
        assert result['acodec'] == 'opus'
        assert result['format_id'] == '251'
    
    def test_extract_audio_formats(self):
        """Test extracting audio-only formats."""
        audio_formats = self.quality_selector.extract_audio_formats(self.mock_formats)
        
        assert len(audio_formats) == 2
        format_ids = [fmt['format_id'] for fmt in audio_formats]
        assert '140' in format_ids  # m4a format
        assert '251' in format_ids  # webm/opus format
    
    def test_select_best_quality_best(self):
        """Test select_best_quality with 'best' preference."""
        result = self.quality_selector.select_best_quality(self.mock_formats, 'best')
        
        assert result['height'] == 1080
        assert result['format_id'] == '137'
    
    def test_select_best_quality_worst(self):
        """Test select_best_quality with 'worst' preference."""
        result = self.quality_selector.select_best_quality(self.mock_formats, 'worst')
        
        assert result['height'] == 480
        assert result['format_id'] == '135'
    
    def test_select_best_quality_resolution(self):
        """Test select_best_quality with resolution preference."""
        result = self.quality_selector.select_best_quality(self.mock_formats, '720p')
        
        assert result['height'] == 720
        assert result['format_id'] == '136'
    
    def test_select_best_quality_audio(self):
        """Test select_best_quality with audio preference."""
        result = self.quality_selector.select_best_quality(self.mock_formats, 'audio')
        
        assert result['vcodec'] == 'none'
        assert result['acodec'] == 'opus'
    
    def test_select_best_quality_empty_formats(self):
        """Test select_best_quality with empty formats list."""
        result = self.quality_selector.select_best_quality([], 'best')
        
        assert result == {}
    
    def test_apply_format_preferences(self):
        """Test applying format preferences."""
        preferences = FormatPreferences(
            video_codec='h264',
            audio_codec='aac',
            container='mp4',
            prefer_free_formats=False
        )
        
        result = self.quality_selector.apply_format_preferences(self.mock_formats, preferences)
        
        # Should prefer mp4 container and h264 codec
        assert result['ext'] == 'mp4'
        assert 'avc1' in result['vcodec']  # h264 variant
    
    def test_apply_format_preferences_free_formats(self):
        """Test applying format preferences with free format preference."""
        preferences = FormatPreferences(
            video_codec='vp9',
            audio_codec='opus',
            container='webm',
            prefer_free_formats=True
        )
        
        # Add webm video format for testing
        webm_formats = self.mock_formats + [{
            'format_id': '248',
            'ext': 'webm',
            'height': 1080,
            'width': 1920,
            'vcodec': 'vp9',
            'acodec': 'none',
            'vbr': 2000,
            'abr': None
        }]
        
        result = self.quality_selector.apply_format_preferences(webm_formats, preferences)
        
        # Should prefer webm format when prefer_free_formats is True
        assert result['ext'] == 'webm'
        assert result['vcodec'] == 'vp9'
    
    def test_calculate_format_score(self):
        """Test format scoring algorithm."""
        preferences = FormatPreferences(
            video_codec='h264',
            audio_codec='aac',
            container='mp4',
            prefer_free_formats=False
        )
        
        # Test mp4 format with h264
        mp4_format = self.mock_formats[0]  # 1080p mp4
        score_mp4 = self.quality_selector._calculate_format_score(mp4_format, preferences)
        
        # Test webm format
        webm_format = {
            'format_id': '248',
            'ext': 'webm',
            'height': 1080,
            'vcodec': 'vp9',
            'acodec': 'none',
            'vbr': 2000
        }
        score_webm = self.quality_selector._calculate_format_score(webm_format, preferences)
        
        # MP4 should score higher due to preferences
        assert score_mp4 > score_webm
    
    def test_create_format_selector_best(self):
        """Test creating format selector for 'best' quality."""
        preferences = FormatPreferences()
        selector = self.quality_selector.create_format_selector('best', preferences)
        
        assert 'best' in selector
        assert 'h264' in selector
        assert 'mp4' in selector
    
    def test_create_format_selector_resolution(self):
        """Test creating format selector for specific resolution."""
        preferences = FormatPreferences()
        selector = self.quality_selector.create_format_selector('720p', preferences)
        
        assert '720' in selector
        assert 'best' in selector  # fallback
    
    def test_create_format_selector_audio_only(self):
        """Test creating format selector for audio-only."""
        preferences = FormatPreferences(audio_codec='opus')
        selector = self.quality_selector._create_audio_format_selector(preferences)
        
        assert 'bestaudio' in selector
        assert 'opus' in selector
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_available_qualities_success(self, mock_ydl_class):
        """Test getting available qualities successfully."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'formats': self.mock_formats
        }
        mock_ydl.extract_info.return_value = mock_info
        
        test_url = 'https://youtube.com/watch?v=test123'
        qualities = self.quality_selector.get_available_qualities(test_url)
        
        assert 'best' in qualities
        assert '1080p' in qualities
        assert '720p' in qualities
        assert '480p' in qualities
        assert 'worst' in qualities
        
        # Should be sorted from highest to lowest
        height_qualities = [q for q in qualities if q.endswith('p') and q not in ['best', 'worst']]
        heights = [int(q[:-1]) for q in height_qualities]
        assert heights == sorted(heights, reverse=True)
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_available_qualities_failure(self, mock_ydl_class):
        """Test getting available qualities with extraction failure."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Extraction failed")
        
        test_url = 'https://youtube.com/watch?v=test123'
        qualities = self.quality_selector.get_available_qualities(test_url)
        
        # Should return default qualities on failure
        assert 'best' in qualities
        assert 'worst' in qualities
        assert '1080p' in qualities
        assert '720p' in qualities
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_format_info_success(self, mock_ydl_class):
        """Test getting format information successfully."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'title': 'Test Video',
            'duration': 300,
            'formats': self.mock_formats
        }
        mock_ydl.extract_info.return_value = mock_info
        
        test_url = 'https://youtube.com/watch?v=test123'
        format_info = self.quality_selector.get_format_info(test_url)
        
        assert format_info['title'] == 'Test Video'
        assert format_info['duration'] == 300
        assert format_info['format_count'] == len(self.mock_formats)
        assert format_info['has_audio_only'] is True
        assert format_info['max_height'] == 1080
        assert any('avc1' in codec for codec in format_info['available_codecs'])
    
    @patch('yt_dlp.YoutubeDL')
    def test_get_format_info_failure(self, mock_ydl_class):
        """Test getting format information with extraction failure."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Extraction failed")
        
        test_url = 'https://youtube.com/watch?v=test123'
        format_info = self.quality_selector.get_format_info(test_url)
        
        # Should return empty dict on failure
        assert format_info == {}
    
    def test_validate_quality_preference_valid(self):
        """Test validating valid quality preferences."""
        valid_qualities = ['best', 'worst', 'audio', 'audio-only', '720p', '1080p']
        available_qualities = ['best', '1080p', '720p', '480p', 'worst']
        
        for quality in valid_qualities:
            assert self.quality_selector.validate_quality_preference(quality, available_qualities)
    
    def test_validate_quality_preference_invalid(self):
        """Test validating invalid quality preferences."""
        invalid_qualities = ['4K', 'high', 'medium', '']
        available_qualities = ['best', '1080p', '720p', '480p', 'worst']
        
        for quality in invalid_qualities:
            assert not self.quality_selector.validate_quality_preference(quality, available_qualities)
    
    def test_format_priority_scoring(self):
        """Test format priority scoring."""
        # MP4 should have higher priority than WebM
        assert self.quality_selector._format_priority['mp4'] > self.quality_selector._format_priority['webm']
        
        # H264 should have higher priority than VP9
        assert self.quality_selector._codec_priority['h264'] > self.quality_selector._codec_priority['vp9']
        
        # AAC should have higher priority than Opus
        assert self.quality_selector._audio_codec_priority['aac'] > self.quality_selector._audio_codec_priority['opus']