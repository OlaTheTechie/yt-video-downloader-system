"""
Unit tests for WorkflowManager class.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from services.workflow_manager import WorkflowManager
from models.core import DownloadConfig, DownloadResult, VideoMetadata, DownloadStatus


class TestWorkflowManager:
    """Test cases for WorkflowManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.workflow_manager = WorkflowManager()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test config
        self.test_config = DownloadConfig(
            output_directory=str(self.temp_path),
            quality='720p',
            format_preference='mp4',
            split_timestamps=False,
            save_metadata=True,
            save_thumbnails=True
        )
        
        # Create test metadata
        self.test_metadata = VideoMetadata(
            title='Test Video',
            uploader='Test Channel',
            description='0:00 Introduction\n5:30 Main Content\n10:00 Conclusion',
            upload_date='20231201',
            duration=600.0,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123'
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch.object(WorkflowManager, '_prompt_user_for_splitting')
    def test_download_with_optional_splitting_interactive_yes(self, mock_prompt):
        """Test interactive download with user choosing to split."""
        mock_prompt.return_value = True
        
        # Mock download manager methods
        mock_preview = {
            'title': 'Test Video',
            'timestamps_found': 3,
            'ffmpeg_available': True
        }
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        mock_result.video_metadata = self.test_metadata
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                self.test_config,
                interactive=True
            )
        
        assert result.success
        mock_prompt.assert_called_once()
    
    @patch.object(WorkflowManager, '_prompt_user_for_splitting')
    def test_download_with_optional_splitting_interactive_no(self, mock_prompt):
        """Test interactive download with user choosing not to split."""
        mock_prompt.return_value = False
        
        # Mock download manager methods
        mock_preview = {
            'title': 'Test Video',
            'timestamps_found': 3,
            'ffmpeg_available': True
        }
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                self.test_config,
                interactive=True
            )
        
        assert result.success
        mock_prompt.assert_called_once()
    
    def test_download_with_optional_splitting_non_interactive_enabled(self):
        """Test non-interactive download with splitting enabled in config."""
        config = DownloadConfig(**self.test_config.__dict__)
        config.split_timestamps = True
        
        # Mock download manager methods
        mock_preview = {
            'title': 'Test Video',
            'timestamps_found': 3,
            'ffmpeg_available': True
        }
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                config,
                interactive=False
            )
        
        assert result.success
    
    def test_download_with_optional_splitting_no_timestamps(self):
        """Test download when no timestamps are found."""
        # Mock download manager methods
        mock_preview = {
            'title': 'Test Video',
            'timestamps_found': 0,
            'ffmpeg_available': True
        }
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                self.test_config,
                interactive=True
            )
        
        assert result.success
    
    def test_download_with_optional_splitting_ffmpeg_not_available(self):
        """Test download when FFmpeg is not available."""
        config = DownloadConfig(**self.test_config.__dict__)
        config.split_timestamps = True
        
        # Mock download manager methods
        mock_preview = {
            'title': 'Test Video',
            'timestamps_found': 3,
            'ffmpeg_available': False
        }
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                config,
                interactive=False
            )
        
        assert result.success
    
    def test_download_with_optional_splitting_preview_error(self):
        """Test download when preview fails."""
        # Mock download manager methods
        mock_preview = {'error': 'Failed to get preview'}
        
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'get_splitting_preview', return_value=mock_preview), \
             patch.object(self.workflow_manager.download_manager, 'download_single', return_value=mock_result):
            
            result = self.workflow_manager.download_with_optional_splitting(
                'https://youtube.com/watch?v=test123',
                self.test_config,
                interactive=True
            )
        
        assert result.success
    
    @patch('builtins.input')
    def test_prompt_user_for_splitting_yes(self, mock_input):
        """Test user prompt returning yes."""
        mock_input.return_value = 'y'
        
        preview = {
            'title': 'Test Video',
            'duration': 600.0,
            'timestamps_found': 3,
            'timestamps': [
                {'time': '0:00', 'label': 'Introduction', 'seconds': 0},
                {'time': '5:30', 'label': 'Main Content', 'seconds': 330},
                {'time': '10:00', 'label': 'Conclusion', 'seconds': 600}
            ],
            'ffmpeg_available': True
        }
        
        result = self.workflow_manager._prompt_user_for_splitting(preview)
        assert result is True
    
    @patch('builtins.input')
    def test_prompt_user_for_splitting_no(self, mock_input):
        """Test user prompt returning no."""
        mock_input.return_value = 'n'
        
        preview = {
            'title': 'Test Video',
            'duration': 600.0,
            'timestamps_found': 3,
            'timestamps': [
                {'time': '0:00', 'label': 'Introduction', 'seconds': 0},
                {'time': '5:30', 'label': 'Main Content', 'seconds': 330},
                {'time': '10:00', 'label': 'Conclusion', 'seconds': 600}
            ],
            'ffmpeg_available': True
        }
        
        result = self.workflow_manager._prompt_user_for_splitting(preview)
        assert result is False
    
    @patch('builtins.input')
    def test_prompt_user_for_splitting_invalid_then_valid(self, mock_input):
        """Test user prompt with invalid input then valid."""
        mock_input.side_effect = ['invalid', 'maybe', 'yes']
        
        preview = {
            'title': 'Test Video',
            'duration': 600.0,
            'timestamps_found': 3,
            'timestamps': [],
            'ffmpeg_available': True
        }
        
        result = self.workflow_manager._prompt_user_for_splitting(preview)
        assert result is True
        assert mock_input.call_count == 3
    
    def test_prompt_user_for_splitting_no_ffmpeg(self):
        """Test user prompt when FFmpeg is not available."""
        preview = {
            'title': 'Test Video',
            'duration': 600.0,
            'timestamps_found': 3,
            'timestamps': [],
            'ffmpeg_available': False
        }
        
        result = self.workflow_manager._prompt_user_for_splitting(preview)
        assert result is False
    
    def test_organize_split_videos_no_split_files(self):
        """Test organizing split videos when no split files exist."""
        result = DownloadResult(success=True)
        result.video_metadata = self.test_metadata
        result.split_files = []
        
        # Should not raise any exceptions
        self.workflow_manager.organize_split_videos(result, str(self.temp_path))
    
    def test_organize_split_videos_no_metadata(self):
        """Test organizing split videos when no metadata exists."""
        result = DownloadResult(success=True)
        result.video_metadata = None
        result.split_files = ['/path/to/chapter1.mp4']
        
        # Should not raise any exceptions
        self.workflow_manager.organize_split_videos(result, str(self.temp_path))
    
    @patch('os.rename')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_organize_split_videos_success(self, mock_makedirs, mock_exists, mock_rename):
        """Test successful organization of split videos."""
        mock_exists.return_value = True
        
        result = DownloadResult(success=True)
        result.video_metadata = self.test_metadata
        result.split_files = ['/path/to/chapter1.mp4', '/path/to/chapter2.mp4']
        result.metadata_path = '/path/to/metadata.json'
        result.thumbnail_path = '/path/to/thumbnail.jpg'
        
        self.workflow_manager.organize_split_videos(result, str(self.temp_path))
        
        mock_makedirs.assert_called_once()
        # Should attempt to rename metadata and thumbnail files
        assert mock_rename.call_count == 2
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal Title", "Normal Title"),
            ("Title with <invalid> chars", "Title with _invalid_ chars"),
            ("Title/with\\slashes", "Title_with_slashes"),
            ("", "untitled"),
            ("   ", "untitled"),
            ("A" * 250, "A" * 200),  # Length limit
        ]
        
        for input_filename, expected in test_cases:
            result = self.workflow_manager._sanitize_filename(input_filename)
            assert result == expected
    
    def test_get_workflow_summary_empty(self):
        """Test getting workflow summary for empty results."""
        summary = self.workflow_manager.get_workflow_summary([])
        
        assert summary['total_downloads'] == 0
        assert summary['successful_downloads'] == 0
        assert summary['failed_downloads'] == 0
        assert summary['videos_with_splits'] == 0
        assert summary['total_split_files'] == 0
        assert summary['total_download_time'] == 0
        assert summary['average_download_time'] == 0
    
    def test_get_workflow_summary_mixed_results(self):
        """Test getting workflow summary for mixed results."""
        # Create test results
        result1 = DownloadResult(success=False)
        result1.mark_success('/path/to/video1.mp4', 10.0)
        result1.split_files = ['/path/to/ch1.mp4', '/path/to/ch2.mp4']
        
        result2 = DownloadResult(success=False)
        result2.mark_failure('Download failed')
        
        result3 = DownloadResult(success=False)
        result3.mark_success('/path/to/video3.mp4', 15.0)
        result3.split_files = ['/path/to/ch3.mp4']
        
        results = [result1, result2, result3]
        summary = self.workflow_manager.get_workflow_summary(results)
        
        assert summary['total_downloads'] == 3
        assert summary['successful_downloads'] == 2
        assert summary['failed_downloads'] == 1
        assert summary['videos_with_splits'] == 2
        assert summary['total_split_files'] == 3
        assert summary['total_download_time'] == 25.0
        assert summary['average_download_time'] == 12.5
    
    @patch('builtins.input')
    def test_download_playlist_with_splitting_options_apply_all(self, mock_input):
        """Test playlist download with apply splitting to all option."""
        mock_input.return_value = '1'  # Apply to all
        
        mock_results = [
            DownloadResult(success=False),
            DownloadResult(success=False)
        ]
        for result in mock_results:
            result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'download_playlist', return_value=mock_results):
            results = self.workflow_manager.download_playlist_with_splitting_options(
                'https://youtube.com/playlist?list=test123',
                self.test_config,
                interactive=True
            )
        
        assert len(results) == 2
        assert all(result.success for result in results)
    
    @patch('builtins.input')
    def test_download_playlist_with_splitting_options_no_splitting(self, mock_input):
        """Test playlist download with no splitting option."""
        mock_input.return_value = '2'  # No splitting
        
        mock_results = [
            DownloadResult(success=False),
            DownloadResult(success=False)
        ]
        for result in mock_results:
            result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'download_playlist', return_value=mock_results):
            results = self.workflow_manager.download_playlist_with_splitting_options(
                'https://youtube.com/playlist?list=test123',
                self.test_config,
                interactive=True
            )
        
        assert len(results) == 2
        assert all(result.success for result in results)
    
    @patch('builtins.input')
    def test_download_playlist_with_splitting_options_individual(self, mock_input):
        """Test playlist download with individual choice option."""
        mock_input.return_value = '3'  # Individual choices
        
        with patch.object(self.workflow_manager, '_download_playlist_interactive') as mock_interactive:
            mock_interactive.return_value = [DownloadResult(success=True)]
            
            results = self.workflow_manager.download_playlist_with_splitting_options(
                'https://youtube.com/playlist?list=test123',
                self.test_config,
                interactive=True
            )
        
        mock_interactive.assert_called_once()
        assert len(results) == 1
    
    @patch('builtins.input')
    def test_download_playlist_with_splitting_options_invalid_then_valid(self, mock_input):
        """Test playlist download with invalid input then valid."""
        mock_input.side_effect = ['invalid', '4', '2']  # Invalid, invalid, valid
        
        mock_results = [DownloadResult(success=True)]
        
        with patch.object(self.workflow_manager.download_manager, 'download_playlist', return_value=mock_results):
            results = self.workflow_manager.download_playlist_with_splitting_options(
                'https://youtube.com/playlist?list=test123',
                self.test_config,
                interactive=True
            )
        
        assert len(results) == 1
        assert mock_input.call_count == 3
    
    def test_read_batch_file_success(self):
        """Test successful batch file reading."""
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_content = """# Test batch file
https://youtube.com/watch?v=video1
https://youtu.be/video2

# Another comment
https://youtube.com/watch?v=video3
invalid_url_should_be_skipped
https://youtube.com/playlist?list=playlist1
"""
        batch_file.write_text(batch_content)
        
        urls = self.workflow_manager._read_batch_file(str(batch_file))
        
        assert len(urls) == 4
        assert 'https://youtube.com/watch?v=video1' in urls
        assert 'https://youtu.be/video2' in urls
        assert 'https://youtube.com/watch?v=video3' in urls
        assert 'https://youtube.com/playlist?list=playlist1' in urls
        assert 'invalid_url_should_be_skipped' not in urls
    
    def test_read_batch_file_empty(self):
        """Test reading empty batch file."""
        batch_file = self.temp_path / 'empty_batch.txt'
        batch_file.write_text('# Only comments\n\n# More comments\n')
        
        urls = self.workflow_manager._read_batch_file(str(batch_file))
        
        assert len(urls) == 0
    
    def test_read_batch_file_not_found(self):
        """Test reading non-existent batch file."""
        with pytest.raises(FileNotFoundError):
            self.workflow_manager._read_batch_file('/nonexistent/file.txt')
    
    def test_is_valid_youtube_url(self):
        """Test YouTube URL validation."""
        test_cases = [
            ('https://youtube.com/watch?v=test123', True),
            ('https://www.youtube.com/watch?v=test123', True),
            ('https://youtu.be/test123', True),
            ('https://m.youtube.com/watch?v=test123', True),
            ('https://youtube.com/playlist?list=test123', True),
            ('https://example.com/video', False),
            ('not_a_url', False),
            ('', False),
        ]
        
        for url, expected in test_cases:
            result = self.workflow_manager._is_valid_youtube_url(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_download_batch_from_file_success(self):
        """Test successful batch download from file."""
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_content = """https://youtube.com/watch?v=video1
https://youtube.com/watch?v=video2
"""
        batch_file.write_text(batch_content)
        
        # Mock download results
        mock_results = [
            DownloadResult(success=False),
            DownloadResult(success=False)
        ]
        for result in mock_results:
            result.mark_success('/path/to/video.mp4', 10.0)
        
        with patch.object(self.workflow_manager.download_manager, 'download_batch', return_value=mock_results):
            results = self.workflow_manager.download_batch_from_file(
                str(batch_file), self.test_config, interactive=False
            )
        
        assert len(results) == 2
        assert all(result.success for result in results)
    
    def test_download_batch_from_file_empty(self):
        """Test batch download from empty file."""
        # Create empty batch file
        batch_file = self.temp_path / 'empty_batch.txt'
        batch_file.write_text('# Only comments\n')
        
        results = self.workflow_manager.download_batch_from_file(
            str(batch_file), self.test_config, interactive=False
        )
        
        assert len(results) == 1
        assert not results[0].success
        assert "No valid URLs found" in results[0].error_message
    
    def test_download_batch_from_file_not_found(self):
        """Test batch download from non-existent file."""
        results = self.workflow_manager.download_batch_from_file(
            '/nonexistent/file.txt', self.test_config, interactive=False
        )
        
        assert len(results) == 1
        assert not results[0].success
        assert "Batch file processing error" in results[0].error_message
    
    @patch('builtins.input')
    def test_download_batch_from_file_interactive_enable_splitting(self, mock_input):
        """Test interactive batch download with splitting enabled."""
        mock_input.return_value = '1'  # Enable splitting
        
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_file.write_text('https://youtube.com/watch?v=video1\n')
        
        mock_results = [DownloadResult(success=True)]
        
        with patch.object(self.workflow_manager.download_manager, 'download_batch', return_value=mock_results):
            results = self.workflow_manager.download_batch_from_file(
                str(batch_file), self.test_config, interactive=True
            )
        
        assert len(results) == 1
        assert results[0].success
        mock_input.assert_called_once()
    
    @patch('builtins.input')
    def test_download_batch_from_file_interactive_disable_splitting(self, mock_input):
        """Test interactive batch download with splitting disabled."""
        mock_input.return_value = '2'  # Disable splitting
        
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_file.write_text('https://youtube.com/watch?v=video1\n')
        
        mock_results = [DownloadResult(success=True)]
        
        with patch.object(self.workflow_manager.download_manager, 'download_batch', return_value=mock_results):
            results = self.workflow_manager.download_batch_from_file(
                str(batch_file), self.test_config, interactive=True
            )
        
        assert len(results) == 1
        assert results[0].success
        mock_input.assert_called_once()
    
    @patch('builtins.input')
    def test_download_batch_from_file_interactive_invalid_then_valid(self, mock_input):
        """Test interactive batch download with invalid input then valid."""
        mock_input.side_effect = ['invalid', '3', '1']  # Invalid, invalid, valid
        
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_file.write_text('https://youtube.com/watch?v=video1\n')
        
        mock_results = [DownloadResult(success=True)]
        
        with patch.object(self.workflow_manager.download_manager, 'download_batch', return_value=mock_results):
            results = self.workflow_manager.download_batch_from_file(
                str(batch_file), self.test_config, interactive=True
            )
        
        assert len(results) == 1
        assert results[0].success
        assert mock_input.call_count == 3
    
    def test_download_batch_from_file_with_split_videos(self):
        """Test batch download with videos that get split."""
        # Create test batch file
        batch_file = self.temp_path / 'test_batch.txt'
        batch_file.write_text('https://youtube.com/watch?v=video1\n')
        
        # Mock download result with split files
        mock_result = DownloadResult(success=False)
        mock_result.mark_success('/path/to/video.mp4', 10.0)
        mock_result.video_metadata = self.test_metadata
        mock_result.split_files = ['/path/to/chapter1.mp4', '/path/to/chapter2.mp4']
        
        with patch.object(self.workflow_manager.download_manager, 'download_batch', return_value=[mock_result]), \
             patch.object(self.workflow_manager, 'organize_split_videos') as mock_organize:
            
            results = self.workflow_manager.download_batch_from_file(
                str(batch_file), self.test_config, interactive=False
            )
        
        assert len(results) == 1
        assert results[0].success
        mock_organize.assert_called_once_with(mock_result, self.test_config.output_directory)
    
    def test_create_batch_file_template(self):
        """Test creating batch file template."""
        template_path = self.temp_path / 'template.txt'
        
        self.workflow_manager.create_batch_file_template(str(template_path))
        
        assert template_path.exists()
        content = template_path.read_text()
        
        assert '# YouTube Video Downloader Batch File' in content
        assert 'Instructions:' in content
        assert 'Examples:' in content
        assert 'Add your URLs below:' in content
    
    def test_create_batch_file_template_error(self):
        """Test creating batch file template with error."""
        # Try to create template in non-existent directory
        invalid_path = '/nonexistent/directory/template.txt'
        
        with pytest.raises(Exception) as exc_info:
            self.workflow_manager.create_batch_file_template(invalid_path)
        
        assert "Failed to create batch file template" in str(exc_info.value)