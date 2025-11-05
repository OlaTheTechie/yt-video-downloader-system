"""
End-to-end integration tests for the YouTube Video Downloader application.

These tests verify complete workflows from CLI input to file output,
testing integration between all major components and real-world scenarios.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from cli.main_cli import main
from core.application import YouTubeDownloaderApp
from models.core import DownloadConfig, DownloadResult, VideoMetadata, ProgressInfo
from config.error_handling import YouTubeDownloaderError


class TestEndToEndIntegration:
    """End-to-end integration tests for the complete application workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test configuration
        self.test_config_path = self.temp_path / 'test_config.json'
        self.test_config = {
            "output_directory": str(self.temp_path / 'downloads'),
            "quality": "720p",
            "format_preference": "mp4",
            "audio_format": "mp3",
            "split_timestamps": False,
            "max_parallel_downloads": 2,
            "save_thumbnails": True,
            "save_metadata": True,
            "resume_downloads": True,
            "retry_attempts": 3,
            "video_codec": "h264",
            "audio_codec": "aac",
            "container": "mp4",
            "download_subtitles": False,
            "subtitle_languages": ["en"],
            "subtitle_format": "srt",
            "auto_subs": False,
            "use_archive": False,
            "skip_duplicates": False
        }
        
        # Save test configuration
        with open(self.test_config_path, 'w') as f:
            json.dump(self.test_config, f, indent=2)
        
        # Create test metadata
        self.test_metadata = VideoMetadata(
            title='Test Video - Programming Tutorial',
            uploader='Test Channel',
            description='0:00 Introduction\n5:30 Main Content\n10:00 Conclusion',
            upload_date='20231201',
            duration=600.0,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123'
        )
        
        # Create test batch file
        self.batch_file_path = self.temp_path / 'test_urls.txt'
        batch_content = """# Test batch file for YouTube Video Downloader
https://www.youtube.com/watch?v=test_video_1
https://youtu.be/test_video_2
https://www.youtube.com/watch?v=test_video_3

# Playlist example
https://www.youtube.com/playlist?list=test_playlist_1
"""
        self.batch_file_path.write_text(batch_content)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_mock_download_result(self, success=True, with_splits=False, with_metadata=True):
        """Create a mock download result for testing."""
        result = DownloadResult(success=False)
        
        if success:
            video_path = str(self.temp_path / 'downloads' / 'test_video.mp4')
            result.mark_success(video_path, 10.0)
            
            if with_metadata:
                result.video_metadata = self.test_metadata
                result.metadata_path = str(self.temp_path / 'downloads' / 'test_video.info.json')
                result.thumbnail_path = str(self.temp_path / 'downloads' / 'test_video.jpg')
            
            if with_splits:
                result.split_files = [
                    str(self.temp_path / 'downloads' / 'test_video_01_Introduction.mp4'),
                    str(self.temp_path / 'downloads' / 'test_video_02_Main_Content.mp4'),
                    str(self.temp_path / 'downloads' / 'test_video_03_Conclusion.mp4')
                ]
        else:
            result.mark_failure('Mock download failure for testing')
        
        return result
    
    @patch('core.application.YouTubeDownloaderApp.download_single_video')
    def test_cli_single_video_download_success(self, mock_download):
        """Test successful single video download through CLI."""
        # Mock successful download
        mock_result = self.create_mock_download_result(success=True)
        mock_download.return_value = mock_result
        
        # Run CLI command
        result = self.runner.invoke(main, [
            '--config', str(self.test_config_path),
            'download',
            'https://www.youtube.com/watch?v=test123',
            '--output', str(self.temp_path / 'downloads'),
            '--quality', '720p'
        ])
        
        # Verify CLI execution
        assert result.exit_code == 0
        assert 'Download completed successfully!' in result.output
        assert 'Video saved to:' in result.output
        
        # Verify download was called with correct parameters
        mock_download.assert_called_once()
        call_args = mock_download.call_args
        assert call_args[0][0] == 'https://www.youtube.com/watch?v=test123'  # URL
        assert isinstance(call_args[0][1], DownloadConfig)  # Config
        assert call_args[1]['interactive'] == False  # Interactive mode
    
    @patch('core.application.YouTubeDownloaderApp.download_single_video')
    def test_cli_single_video_download_with_splitting(self, mock_download):
        """Test single video download with timestamp splitting through CLI."""
        # Mock successful download with splits
        mock_result = self.create_mock_download_result(success=True, with_splits=True)
        mock_download.return_value = mock_result
        
        # Run CLI command with splitting enabled
        result = self.runner.invoke(main, [
            '--config', str(self.test_config_path),
            'download',
            'https://www.youtube.com/watch?v=test123',
            '--split-timestamps',
            '--interactive'
        ])
        
        # Verify CLI execution
        assert result.exit_code == 0
        assert 'Download completed successfully!' in result.output
        assert 'Video split into 3 chapters' in result.output
        
        # Verify interactive mode was enabled
        call_args = mock_download.call_args
        assert call_args[1]['interactive'] == True
    
    @patch('core.application.YouTubeDownloaderApp.download_single_video')
    def test_cli_single_video_download_failure(self, mock_download):
        """Test failed single video download through CLI."""
        # Mock failed download
        mock_result = self.create_mock_download_result(success=False)
        mock_download.return_value = mock_result
        
        # Run CLI command
        result = self.runner.invoke(main, [
            'download',
            'https://www.youtube.com/watch?v=test123'
        ])
        
        # Verify CLI execution failed
        assert result.exit_code == 1
        assert 'Download failed:' in result.output
        assert 'Mock download failure for testing' in result.output
    
    @patch('core.application.YouTubeDownloaderApp.download_playlist')
    def test_cli_playlist_download_success(self, mock_download):
        """Test successful playlist download through CLI."""
        # Mock successful playlist download
        mock_results = [
            self.create_mock_download_result(success=True),
            self.create_mock_download_result(success=True, with_splits=True),
            self.create_mock_download_result(success=False)
        ]
        mock_download.return_value = mock_results
        
        # Mock workflow summary
        with patch('core.application.YouTubeDownloaderApp.get_workflow_summary') as mock_summary:
            mock_summary.return_value = {
                'total_downloads': 3,
                'successful_downloads': 2,
                'failed_downloads': 1,
                'videos_with_splits': 1,
                'total_split_files': 3,
                'total_download_time': 25.0,
                'average_download_time': 12.5
            }
            
            # Run CLI command
            result = self.runner.invoke(main, [
                'playlist',
                'https://www.youtube.com/playlist?list=test123',
                '--parallel', '3'
            ])
        
        # Verify CLI execution
        assert result.exit_code == 1  # Exit code 1 because some downloads failed
        assert 'Playlist download completed!' in result.output
        assert 'Total downloads: 3' in result.output
        assert 'Successful: 2' in result.output
        assert 'Failed: 1' in result.output
        assert 'Videos split into chapters: 1' in result.output
    
    @patch('core.application.YouTubeDownloaderApp.download_batch_from_file')
    def test_cli_batch_download_success(self, mock_download):
        """Test successful batch download through CLI."""
        # Mock successful batch download
        mock_results = [
            self.create_mock_download_result(success=True),
            self.create_mock_download_result(success=True)
        ]
        mock_download.return_value = mock_results
        
        # Mock workflow summary
        with patch('core.application.YouTubeDownloaderApp.get_workflow_summary') as mock_summary:
            mock_summary.return_value = {
                'total_downloads': 2,
                'successful_downloads': 2,
                'failed_downloads': 0,
                'videos_with_splits': 0,
                'total_split_files': 0,
                'total_download_time': 20.0,
                'average_download_time': 10.0
            }
            
            # Run CLI command
            result = self.runner.invoke(main, [
                'batch',
                str(self.batch_file_path),
                '--parallel', '2'
            ])
        
        # Verify CLI execution
        assert result.exit_code == 0
        assert 'Batch download completed!' in result.output
        assert 'Total downloads: 2' in result.output
        assert 'Successful: 2' in result.output
        assert 'Failed: 0' in result.output
    
    def test_cli_config_generation(self):
        """Test configuration file generation through CLI."""
        config_output_path = self.temp_path / 'generated_config.json'
        
        # Run CLI command to generate config
        result = self.runner.invoke(main, [
            'init-config',
            '--output', str(config_output_path)
        ])
        
        # Verify CLI execution
        assert result.exit_code == 0
        assert 'Default configuration saved to:' in result.output
        assert str(config_output_path) in result.output
        
        # Verify config file was created
        assert config_output_path.exists()
        
        # Verify config file content
        with open(config_output_path, 'r') as f:
            config_data = json.load(f)
        
        # Check for expected configuration keys
        expected_keys = [
            'output_directory', 'quality', 'format_preference',
            'max_parallel_downloads', 'save_metadata'
        ]
        for key in expected_keys:
            assert key in config_data
    
    def test_cli_config_validation_success(self):
        """Test successful configuration validation through CLI."""
        # Run CLI command to validate config
        result = self.runner.invoke(main, [
            'validate-config',
            '--config', str(self.test_config_path)
        ])
        
        # Verify CLI execution
        assert result.exit_code == 0
        assert 'Configuration file is valid:' in result.output
        assert 'Configuration Summary:' in result.output
        assert 'Output Directory:' in result.output
        assert 'Quality: 720p' in result.output
    
    def test_cli_config_validation_failure(self):
        """Test failed configuration validation through CLI."""
        # Create invalid config file
        invalid_config_path = self.temp_path / 'invalid_config.json'
        with open(invalid_config_path, 'w') as f:
            f.write('invalid json content')
        
        # Run CLI command to validate config
        result = self.runner.invoke(main, [
            'validate-config',
            '--config', str(invalid_config_path)
        ])
        
        # Verify CLI execution failed
        assert result.exit_code == 1
        assert 'Configuration validation failed:' in result.output
    
    def test_cli_help_and_usage(self):
        """Test CLI help and usage information."""
        # Test main help
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'YouTube Video Downloader' in result.output
        assert 'EXAMPLES:' in result.output
        assert 'CONFIGURATION:' in result.output
        
        # Test command-specific help
        result = self.runner.invoke(main, ['download', '--help'])
        assert result.exit_code == 0
        assert 'Download a single YouTube video' in result.output
        assert 'EXAMPLES:' in result.output
        
        # Test comprehensive examples
        result = self.runner.invoke(main, ['help-examples'])
        assert result.exit_code == 0
        assert 'Comprehensive Usage Examples' in result.output
        assert 'BASIC DOWNLOADS:' in result.output
        assert 'ADVANCED FEATURES:' in result.output
    
    def test_cli_invalid_url_handling(self):
        """Test CLI handling of invalid URLs."""
        # Test invalid URL
        result = self.runner.invoke(main, [
            'download',
            'https://www.google.com/invalid-url'
        ])
        
        # Verify CLI execution failed
        assert result.exit_code == 1
        assert 'Invalid YouTube URL provided' in result.output
    
    def test_cli_missing_batch_file(self):
        """Test CLI handling of missing batch file."""
        # Test non-existent batch file
        result = self.runner.invoke(main, [
            'batch',
            '/nonexistent/file.txt'
        ])
        
        # Verify CLI execution failed
        assert result.exit_code != 0
    
    def test_application_controller_initialization(self):
        """Test application controller initialization and component wiring."""
        # Create application instance
        app = YouTubeDownloaderApp()
        
        # Verify components are initialized
        assert app.config_manager is not None
        assert app.download_manager is not None
        assert app.workflow_manager is not None
        assert app.error_handler is not None
        assert hasattr(app, 'logger')
        assert hasattr(app, '_is_running')
        assert hasattr(app, '_cleanup_registered')
    
    def test_application_workflow_routing(self):
        """Test application workflow routing based on input type."""
        app = YouTubeDownloaderApp()
        
        # Test workflow type detection
        assert app.detect_workflow_type('https://www.youtube.com/watch?v=test123') == 'single'
        assert app.detect_workflow_type('https://www.youtube.com/playlist?list=test123') == 'playlist'
        assert app.detect_workflow_type(str(self.batch_file_path)) == 'batch'
    
    @patch('core.application.YouTubeDownloaderApp.download_single_video')
    @patch('core.application.YouTubeDownloaderApp.download_playlist')
    @patch('core.application.YouTubeDownloaderApp.download_batch_from_file')
    def test_application_workflow_routing_execution(self, mock_batch, mock_playlist, mock_single):
        """Test application workflow routing execution."""
        app = YouTubeDownloaderApp()
        config = DownloadConfig()
        
        # Mock return values
        mock_single.return_value = self.create_mock_download_result(success=True)
        mock_playlist.return_value = [self.create_mock_download_result(success=True)]
        mock_batch.return_value = [self.create_mock_download_result(success=True)]
        
        # Test single video routing
        results = app.route_workflow('single', 'https://www.youtube.com/watch?v=test123', config)
        assert len(results) == 1
        mock_single.assert_called_once()
        
        # Test playlist routing
        results = app.route_workflow('playlist', 'https://www.youtube.com/playlist?list=test123', config)
        assert len(results) == 1
        mock_playlist.assert_called_once()
        
        # Test batch routing
        results = app.route_workflow('batch', str(self.batch_file_path), config)
        assert len(results) == 1
        mock_batch.assert_called_once()
    
    def test_application_invalid_workflow_type(self):
        """Test application handling of invalid workflow type."""
        app = YouTubeDownloaderApp()
        config = DownloadConfig()
        
        with pytest.raises(YouTubeDownloaderError) as exc_info:
            app.route_workflow('invalid_type', 'some_input', config)
        
        assert 'Invalid workflow type: invalid_type' in str(exc_info.value)
    
    @patch('core.application.YouTubeDownloaderApp.download_single_video')
    def test_application_progress_callback(self, mock_download):
        """Test application progress callback functionality."""
        app = YouTubeDownloaderApp()
        
        # Set up progress callback
        progress_updates = []
        def progress_callback(progress: ProgressInfo):
            progress_updates.append(progress)
        
        app.set_progress_callback(progress_callback)
        
        # Mock download with progress updates
        mock_result = self.create_mock_download_result(success=True)
        mock_download.return_value = mock_result
        
        # Simulate download
        config = DownloadConfig()
        result = app.download_single_video('https://www.youtube.com/watch?v=test123', config)
        
        # Verify download was successful
        assert result.success
    
    def test_application_graceful_shutdown(self):
        """Test application graceful shutdown functionality."""
        app = YouTubeDownloaderApp()
        
        # Test shutdown doesn't raise exceptions
        app.shutdown()
        
        # Test multiple shutdowns don't cause issues
        app.shutdown()
        app.shutdown()
    
    @patch('core.application.signal.signal')
    def test_application_signal_handling(self, mock_signal):
        """Test application signal handling for graceful shutdown."""
        app = YouTubeDownloaderApp()
        
        # Verify signal handlers were registered
        assert mock_signal.call_count >= 2  # At least SIGINT and SIGTERM
    
    def test_configuration_loading_and_merging(self):
        """Test configuration loading and CLI argument merging."""
        app = YouTubeDownloaderApp()
        
        # Test loading configuration from file
        config = app.load_configuration(str(self.test_config_path))
        assert config.quality == '720p'
        assert config.format_preference == 'mp4'
        
        # Test merging with CLI arguments
        cli_args = {'quality': '1080p', 'parallel': 5}
        merged_config = app.load_configuration(str(self.test_config_path), cli_args)
        assert merged_config.quality == '1080p'  # CLI override
        assert merged_config.max_parallel_downloads == 5  # CLI override
        assert merged_config.format_preference == 'mp4'  # From file
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        app = YouTubeDownloaderApp()
        
        # Test handling of missing download manager
        app.download_manager = None
        
        with pytest.raises(YouTubeDownloaderError) as exc_info:
            config = DownloadConfig()
            app.download_single_video('https://www.youtube.com/watch?v=test123', config)
        
        assert 'Download manager not initialized' in str(exc_info.value)
    
    @patch('services.archive_manager.ArchiveManager')
    def test_cli_archive_management(self, mock_archive_manager):
        """Test CLI archive management functionality."""
        # Mock archive manager
        mock_manager = Mock()
        mock_archive_manager.return_value = mock_manager
        
        # Mock archive stats
        mock_manager.get_archive_stats.return_value = {
            'total_downloads': 10,
            'total_size': 1024**3,  # 1GB
            'first_download': '2023-01-01',
            'last_download': '2023-12-01',
            'total_duration_hours': 5.5,
            'top_uploaders': [('Channel 1', 5), ('Channel 2', 3)]
        }
        
        # Test archive stats command
        result = self.runner.invoke(main, [
            'archive',
            '--archive-dir', str(self.temp_path),
            '--action', 'stats'
        ])
        
        assert result.exit_code == 0
        assert 'Archive Statistics:' in result.output
        assert 'Total downloads: 10' in result.output
        assert 'Total size: 1.00 GB' in result.output
    
    def test_real_world_scenario_mixed_content(self):
        """Test real-world scenario with mixed content types."""
        # This test simulates a real-world scenario where a user:
        # 1. Downloads a single video with splitting
        # 2. Downloads a playlist
        # 3. Processes a batch file
        # 4. Manages archive
        
        app = YouTubeDownloaderApp()
        config = DownloadConfig(
            output_directory=str(self.temp_path / 'downloads'),
            split_timestamps=True,
            save_metadata=True,
            max_parallel_downloads=2
        )
        
        # Mock all download operations
        with patch.object(app, 'download_single_video') as mock_single, \
             patch.object(app, 'download_playlist') as mock_playlist, \
             patch.object(app, 'download_batch_from_file') as mock_batch:
            
            # Set up mock returns
            mock_single.return_value = self.create_mock_download_result(success=True, with_splits=True)
            mock_playlist.return_value = [
                self.create_mock_download_result(success=True),
                self.create_mock_download_result(success=True, with_splits=True)
            ]
            mock_batch.return_value = [
                self.create_mock_download_result(success=True),
                self.create_mock_download_result(success=False)
            ]
            
            # Execute mixed workflow
            single_results = app.route_workflow('single', 'https://www.youtube.com/watch?v=test123', config)
            playlist_results = app.route_workflow('playlist', 'https://www.youtube.com/playlist?list=test123', config)
            batch_results = app.route_workflow('batch', str(self.batch_file_path), config)
            
            # Verify all operations completed
            assert len(single_results) == 1
            assert len(playlist_results) == 2
            assert len(batch_results) == 2
            
            # Verify success/failure counts
            all_results = single_results + playlist_results + batch_results
            successful = sum(1 for r in all_results if r.success)
            failed = sum(1 for r in all_results if not r.success)
            
            assert successful == 4
            assert failed == 1
    
    def test_integration_with_all_components(self):
        """Test integration between all major components."""
        # This test verifies that all components work together correctly
        # by testing the complete pipeline from CLI to file output
        
        app = YouTubeDownloaderApp()
        
        # Verify all components are properly initialized
        assert app.config_manager is not None
        assert app.download_manager is not None
        assert app.workflow_manager is not None
        assert app.error_handler is not None
        
        # Test component interaction through configuration loading
        config = app.load_configuration()
        assert isinstance(config, DownloadConfig)
        
        # Test workflow summary functionality
        mock_results = [
            self.create_mock_download_result(success=True, with_splits=True),
            self.create_mock_download_result(success=False)
        ]
        
        summary = app.get_workflow_summary(mock_results)
        assert summary['total_downloads'] == 2
        assert summary['successful_downloads'] == 1
        assert summary['failed_downloads'] == 1
        assert summary['videos_with_splits'] == 1
    
    def test_cli_comprehensive_options(self):
        """Test CLI with comprehensive option combinations."""
        # Test download command with all options
        with patch('core.application.YouTubeDownloaderApp.download_single_video') as mock_download:
            mock_download.return_value = self.create_mock_download_result(success=True)
            
            result = self.runner.invoke(main, [
                '--log-level', 'DEBUG',
                'download',
                'https://www.youtube.com/watch?v=test123',
                '--output', str(self.temp_path / 'downloads'),
                '--quality', '1080p',
                '--format', 'mp4',
                '--audio-format', 'mp3',
                '--split-timestamps',
                '--parallel', '3',
                '--thumbnails',
                '--metadata',
                '--resume',
                '--retries', '5',
                '--video-codec', 'h264',
                '--audio-codec', 'aac',
                '--container', 'mp4',
                '--subtitles',
                '--subtitle-languages', 'en,es,fr',
                '--subtitle-format', 'srt',
                '--auto-subs',
                '--archive',
                '--skip-duplicates',
                '--interactive'
            ])
            
            # Verify command executed successfully
            assert result.exit_code == 0
            
            # Verify download was called with correct configuration
            mock_download.assert_called_once()
            call_args = mock_download.call_args
            config = call_args[0][1]
            
            # Verify configuration values
            assert config.quality == '1080p'
            assert config.format_preference == 'mp4'
            assert config.audio_format == 'mp3'
            assert config.split_timestamps == True
            assert config.max_parallel_downloads == 3
            assert config.save_thumbnails == True
            assert config.save_metadata == True
            assert config.resume_downloads == True
            assert config.retry_attempts == 5