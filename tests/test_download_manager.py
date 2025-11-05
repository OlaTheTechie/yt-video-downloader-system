"""
Unit tests for DownloadManager class.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from services.download_manager import DownloadManager
from models.core import DownloadConfig, DownloadResult, ProgressInfo, VideoMetadata, DownloadStatus


class TestDownloadManager:
    """Test cases for DownloadManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.download_manager = DownloadManager()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test config
        self.test_config = DownloadConfig(
            output_directory=str(self.temp_path),
            quality='720p',
            format_preference='mp4',
            max_parallel_downloads=2,
            save_metadata=True,
            save_thumbnails=True
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_set_parallel_workers(self):
        """Test setting parallel worker count."""
        self.download_manager.set_parallel_workers(5)
        assert self.download_manager._parallel_workers == 5
        
        # Test bounds
        self.download_manager.set_parallel_workers(0)
        assert self.download_manager._parallel_workers == 1
        
        self.download_manager.set_parallel_workers(15)
        assert self.download_manager._parallel_workers == 10
    
    def test_set_progress_callback(self):
        """Test setting progress callback."""
        callback = Mock()
        self.download_manager.set_progress_callback(callback)
        assert self.download_manager._progress_callback == callback
    
    def test_build_ydl_options(self):
        """Test building yt-dlp options from config."""
        options = self.download_manager._build_ydl_options(self.test_config, str(self.temp_path))
        
        assert 'outtmpl' in options
        assert 'format' in options
        assert 'retries' in options
        assert options['retries'] == self.test_config.retry_attempts
        assert str(self.temp_path) in options['outtmpl']
    
    def test_build_format_selector_best(self):
        """Test building format selector for 'best' quality."""
        config = DownloadConfig(quality='best')
        selector = self.download_manager._build_format_selector(config)
        assert 'best' in selector
    
    def test_build_format_selector_worst(self):
        """Test building format selector for 'worst' quality."""
        config = DownloadConfig(quality='worst')
        selector = self.download_manager._build_format_selector(config)
        assert 'worst' in selector
    
    def test_build_format_selector_resolution(self):
        """Test building format selector for specific resolution."""
        config = DownloadConfig(quality='720p')
        selector = self.download_manager._build_format_selector(config)
        assert '720' in selector
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ('Normal Title', 'Normal Title'),
            ('Title with <invalid> chars', 'Title with _invalid_ chars'),
            ('Title/with\\slashes', 'Title_with_slashes'),
            ('Title:with|pipes?', 'Title_with_pipes_'),
            ('', 'video'),
            ('   ', 'video')
        ]
        
        for input_title, expected in test_cases:
            result = self.download_manager._sanitize_filename(input_title)
            assert result == expected
    
    def test_extract_metadata_from_info(self):
        """Test extracting metadata from yt-dlp info dict."""
        mock_info = {
            'title': 'Test Video',
            'uploader': 'Test Channel',
            'description': 'Test description',
            'upload_date': '20231201',
            'duration': 300.5,
            'view_count': 1000,
            'thumbnail': 'https://example.com/thumb.jpg',
            'id': 'test123',
            'webpage_url': 'https://youtube.com/watch?v=test123',
            'tags': ['test', 'video'],
            'categories': ['Education'],
            'like_count': 50,
            'dislike_count': 5
        }
        
        metadata = self.download_manager._extract_metadata_from_info(mock_info)
        
        assert isinstance(metadata, VideoMetadata)
        assert metadata.title == 'Test Video'
        assert metadata.uploader == 'Test Channel'
        assert metadata.duration == 300.5
        assert metadata.view_count == 1000
        assert metadata.video_id == 'test123'
        assert metadata.tags == ['test', 'video']
        assert metadata.like_count == 50
    
    def test_save_metadata(self):
        """Test saving metadata to JSON file."""
        metadata = VideoMetadata(
            title='Test Video',
            uploader='Test Channel',
            description='Test description',
            upload_date='20231201',
            duration=300.5,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123'
        )
        
        metadata_path = self.download_manager._save_metadata(
            metadata, str(self.temp_path), 'test_video'
        )
        
        assert metadata_path
        assert os.path.exists(metadata_path)
        
        # Verify content
        with open(metadata_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data['title'] == 'Test Video'
        assert saved_data['video_id'] == 'test123'
        assert saved_data['duration'] == 300.5
    
    @patch('requests.get')
    def test_download_thumbnail_success(self, mock_get):
        """Test successful thumbnail download."""
        # Mock successful response
        mock_response = Mock()
        mock_response.content = b'fake_image_data'
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        thumbnail_url = 'https://example.com/thumb.jpg'
        thumbnail_path = self.download_manager._download_thumbnail(
            thumbnail_url, str(self.temp_path), 'test_video'
        )
        
        assert thumbnail_path
        assert os.path.exists(thumbnail_path)
        assert thumbnail_path.endswith('.jpg')
        
        # Verify content
        with open(thumbnail_path, 'rb') as f:
            content = f.read()
        assert content == b'fake_image_data'
    
    @patch('requests.get')
    def test_download_thumbnail_failure(self, mock_get):
        """Test thumbnail download failure."""
        # Mock failed response
        mock_get.side_effect = Exception("Network error")
        
        thumbnail_url = 'https://example.com/thumb.jpg'
        thumbnail_path = self.download_manager._download_thumbnail(
            thumbnail_url, str(self.temp_path), 'test_video'
        )
        
        # Should return empty string on failure
        assert thumbnail_path == ""
    
    def test_find_downloaded_file_exact_match(self):
        """Test finding downloaded file with exact title match."""
        # Create test file
        test_file = self.temp_path / 'test_video.mp4'
        test_file.touch()
        
        found_path = self.download_manager._find_downloaded_file(
            str(self.temp_path), 'test_video', 'mp4'
        )
        
        assert found_path == str(test_file)
    
    def test_find_downloaded_file_partial_match(self):
        """Test finding downloaded file with partial title match."""
        # Create test file with different name
        test_file = self.temp_path / 'test_video_with_extra_info.mp4'
        test_file.touch()
        
        found_path = self.download_manager._find_downloaded_file(
            str(self.temp_path), 'test_video', 'mp4'
        )
        
        assert found_path == str(test_file)
    
    def test_find_downloaded_file_not_found(self):
        """Test finding downloaded file when no match exists."""
        found_path = self.download_manager._find_downloaded_file(
            str(self.temp_path), 'nonexistent_video', 'mp4'
        )
        
        assert found_path is None
    
    def test_create_progress_hook(self):
        """Test creating progress hook for yt-dlp."""
        test_url = 'https://youtube.com/watch?v=test123'
        callback = Mock()
        self.download_manager.set_progress_callback(callback)
        
        hook = self.download_manager._create_progress_hook(test_url)
        
        # Test progress data
        progress_data = {
            'status': 'downloading',
            'filename': '/path/to/video.mp4',
            'total_bytes': 1000000,
            'downloaded_bytes': 500000,
            'speed': 1024000,  # 1 MB/s
            'eta': 30
        }
        
        hook(progress_data)
        
        # Verify callback was called
        callback.assert_called_once()
        
        # Verify progress info
        call_args = callback.call_args[0][0]
        assert isinstance(call_args, ProgressInfo)
        assert call_args.progress_percent == 50.0
        assert '1.0 MB/s' in call_args.download_speed
        assert call_args.eta == '30s'
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_single_success(self, mock_ydl_class):
        """Test successful single video download."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Mock extract_info
        mock_info = {
            'title': 'Test Video',
            'uploader': 'Test Channel',
            'description': 'Test description',
            'upload_date': '20231201',
            'duration': 300,
            'view_count': 1000,
            'thumbnail': 'https://example.com/thumb.jpg',
            'id': 'test123',
            'webpage_url': 'https://youtube.com/watch?v=test123'
        }
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.download.return_value = None
        
        # Create fake downloaded file
        test_file = self.temp_path / 'Test Video.mp4'
        test_file.touch()
        
        # Test download
        test_url = 'https://youtube.com/watch?v=test123'
        result = self.download_manager.download_single(test_url, self.test_config)
        
        assert result.success
        assert result.status == DownloadStatus.COMPLETED
        assert result.video_path == str(test_file)
        assert result.video_metadata is not None
        assert result.video_metadata.title == 'Test Video'
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_single_failure(self, mock_ydl_class):
        """Test failed single video download."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Download failed")
        
        test_url = 'https://youtube.com/watch?v=test123'
        result = self.download_manager.download_single(test_url, self.test_config)
        
        assert not result.success
        assert result.status == DownloadStatus.FAILED
        assert "Download failed" in result.error_message
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_playlist_success(self, mock_ydl_class):
        """Test successful playlist download."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Mock playlist info
        mock_playlist_info = {
            'title': 'Test Playlist',
            'entries': [
                {'url': 'https://youtube.com/watch?v=video1', 'title': 'Video 1'},
                {'url': 'https://youtube.com/watch?v=video2', 'title': 'Video 2'}
            ]
        }
        mock_ydl.extract_info.return_value = mock_playlist_info
        
        # Mock individual video downloads
        with patch.object(self.download_manager, 'download_single') as mock_download:
            mock_result1 = DownloadResult(success=False)
            mock_result1.mark_success('/path/to/video1.mp4', 10.0)
            mock_result2 = DownloadResult(success=False)
            mock_result2.mark_success('/path/to/video2.mp4', 15.0)
            mock_download.side_effect = [mock_result1, mock_result2]
            
            test_url = 'https://youtube.com/playlist?list=test123'
            results = self.download_manager.download_playlist(test_url, self.test_config)
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert mock_download.call_count == 2
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_playlist_failure(self, mock_ydl_class):
        """Test failed playlist download."""
        # Mock yt-dlp to raise exception
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Playlist extraction failed")
        
        test_url = 'https://youtube.com/playlist?list=test123'
        results = self.download_manager.download_playlist(test_url, self.test_config)
        
        assert len(results) == 1
        assert not results[0].success
        assert "Playlist extraction failed" in results[0].error_message
    
    def test_download_batch_sequential(self):
        """Test batch download in sequential mode."""
        urls = [
            'https://youtube.com/watch?v=video1',
            'https://youtube.com/watch?v=video2'
        ]
        
        # Use sequential mode
        config = DownloadConfig(max_parallel_downloads=1)
        
        with patch.object(self.download_manager, 'download_single') as mock_download:
            mock_result1 = DownloadResult(success=False)
            mock_result1.mark_success('/path/to/video1.mp4', 10.0)
            mock_result2 = DownloadResult(success=False)
            mock_result2.mark_success('/path/to/video2.mp4', 15.0)
            mock_download.side_effect = [mock_result1, mock_result2]
            
            results = self.download_manager.download_batch(urls, config)
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert mock_download.call_count == 2
    
    def test_download_batch_parallel(self):
        """Test batch download in parallel mode."""
        urls = [
            'https://youtube.com/watch?v=video1',
            'https://youtube.com/watch?v=video2'
        ]
        
        # Use parallel mode
        config = DownloadConfig(max_parallel_downloads=2)
        
        with patch.object(self.download_manager, 'download_single') as mock_download:
            mock_result1 = DownloadResult(success=False)
            mock_result1.mark_success('/path/to/video1.mp4', 10.0)
            mock_result2 = DownloadResult(success=False)
            mock_result2.mark_success('/path/to/video2.mp4', 15.0)
            mock_download.side_effect = [mock_result1, mock_result2]
            
            results = self.download_manager.download_batch(urls, config)
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert mock_download.call_count == 2
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_playlist_with_private_videos(self, mock_ydl_class):
        """Test playlist download with private/deleted videos."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Mock playlist info with some private videos (None entries)
        mock_playlist_info = {
            'title': 'Test Playlist',
            'uploader': 'Test Channel',
            'entries': [
                {'url': 'https://youtube.com/watch?v=video1', 'title': 'Video 1'},
                None,  # Private/deleted video
                {'url': 'https://youtube.com/watch?v=video3', 'title': 'Video 3'},
                None,  # Another private/deleted video
            ]
        }
        mock_ydl.extract_info.return_value = mock_playlist_info
        
        # Mock individual video downloads
        with patch.object(self.download_manager, 'download_single') as mock_download:
            mock_result1 = DownloadResult(success=False)
            mock_result1.mark_success('/path/to/video1.mp4', 10.0)
            mock_result3 = DownloadResult(success=False)
            mock_result3.mark_success('/path/to/video3.mp4', 15.0)
            mock_download.side_effect = [mock_result1, mock_result3]
            
            test_url = 'https://youtube.com/playlist?list=test123'
            results = self.download_manager.download_playlist(test_url, self.test_config)
            
            # Should only download accessible videos
            assert len(results) == 2
            assert all(result.success for result in results)
            assert mock_download.call_count == 2
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_playlist_empty(self, mock_ydl_class):
        """Test playlist download with no accessible videos."""
        # Mock yt-dlp
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        # Mock playlist info with only private videos
        mock_playlist_info = {
            'title': 'Empty Playlist',
            'entries': [None, None, None]  # All private/deleted
        }
        mock_ydl.extract_info.return_value = mock_playlist_info
        
        test_url = 'https://youtube.com/playlist?list=test123'
        results = self.download_manager.download_playlist(test_url, self.test_config)
        
        assert len(results) == 1
        assert not results[0].success
        assert "No accessible videos found" in results[0].error_message
    
    def test_save_playlist_metadata(self):
        """Test saving playlist metadata to JSON file."""
        playlist_info = {
            'title': 'Test Playlist',
            'uploader': 'Test Channel',
            'uploader_id': 'testchannel123',
            'description': 'A test playlist',
            'playlist_count': 10,
            'webpage_url': 'https://youtube.com/playlist?list=test123',
            'id': 'test123',
            'entries': [
                {'url': 'https://youtube.com/watch?v=video1'},
                {'url': 'https://youtube.com/watch?v=video2'},
                None  # Private video
            ]
        }
        
        metadata_path = self.download_manager._save_playlist_metadata(
            playlist_info, str(self.temp_path)
        )
        
        assert metadata_path
        assert os.path.exists(metadata_path)
        assert metadata_path.endswith('playlist.info.json')
        
        # Verify content
        with open(metadata_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data['title'] == 'Test Playlist'
        assert saved_data['uploader'] == 'Test Channel'
        assert saved_data['entries_count'] == 3
        assert saved_data['accessible_entries'] == 2
        assert 'extracted_at' in saved_data
    
    def test_is_playlist_url(self):
        """Test playlist URL detection."""
        test_cases = [
            ('https://youtube.com/playlist?list=test123', True),
            ('https://youtube.com/watch?v=test123&list=playlist123', True),
            ('https://youtube.com/c/testchannel', True),
            ('https://youtube.com/channel/UC123456789', True),
            ('https://youtube.com/user/testuser', True),
            ('https://youtube.com/watch?v=test123', False),
            ('https://youtu.be/test123', False),
        ]
        
        for url, expected in test_cases:
            result = self.download_manager._is_playlist_url(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_download_batch_mixed_urls(self):
        """Test batch download with mixed single videos and playlists."""
        urls = [
            'https://youtube.com/watch?v=video1',
            'https://youtube.com/playlist?list=playlist1',
            'https://youtube.com/watch?v=video2'
        ]
        
        config = DownloadConfig(max_parallel_downloads=1)
        
        with patch.object(self.download_manager, 'download_single') as mock_single, \
             patch.object(self.download_manager, 'download_playlist') as mock_playlist:
            
            # Mock single video results
            mock_result1 = DownloadResult(success=False)
            mock_result1.mark_success('/path/to/video1.mp4', 10.0)
            mock_result2 = DownloadResult(success=False)
            mock_result2.mark_success('/path/to/video2.mp4', 15.0)
            mock_single.side_effect = [mock_result1, mock_result2]
            
            # Mock playlist results
            mock_playlist_result1 = DownloadResult(success=False)
            mock_playlist_result1.mark_success('/path/to/playlist_video1.mp4', 20.0)
            mock_playlist_result2 = DownloadResult(success=False)
            mock_playlist_result2.mark_success('/path/to/playlist_video2.mp4', 25.0)
            mock_playlist.return_value = [mock_playlist_result1, mock_playlist_result2]
            
            results = self.download_manager.download_batch(urls, config)
            
            # Should have 2 single video results + 2 playlist results = 4 total
            assert len(results) == 4
            assert all(result.success for result in results)
            assert mock_single.call_count == 2
            assert mock_playlist.call_count == 1
    
    def test_print_batch_summary(self):
        """Test batch summary printing."""
        # Create mock results
        results = []
        
        # Successful result with split files
        result1 = DownloadResult(success=False)
        result1.mark_success('/path/to/video1.mp4', 10.0)
        result1.split_files = ['/path/to/chapter1.mp4', '/path/to/chapter2.mp4']
        results.append(result1)
        
        # Failed result
        result2 = DownloadResult(success=False)
        result2.mark_failure("Download failed")
        results.append(result2)
        
        # Successful result without splits
        result3 = DownloadResult(success=False)
        result3.mark_success('/path/to/video3.mp4', 15.0)
        results.append(result3)
        
        # Test that it doesn't raise an exception
        try:
            self.download_manager._print_batch_summary(results, 2, 1)
        except Exception as e:
            pytest.fail(f"print_batch_summary raised an exception: {e}")
    
    def test_download_batch_empty_list(self):
        """Test batch download with empty URL list."""
        results = self.download_manager.download_batch([], self.test_config)
        assert len(results) == 0
    
    def test_download_batch_error_handling(self):
        """Test batch download error handling."""
        urls = ['https://youtube.com/watch?v=video1']
        
        with patch.object(self.download_manager, 'download_single') as mock_download:
            mock_download.side_effect = Exception("Network error")
            
            results = self.download_manager.download_batch(urls, self.test_config)
            
            assert len(results) == 1
            assert not results[0].success
            assert "Network error" in results[0].error_message


class TestDownloadManagerPerformance:
    """Performance tests for DownloadManager parallel processing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.download_manager = DownloadManager()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test config
        self.test_config = DownloadConfig(
            output_directory=str(self.temp_path),
            quality='720p',
            format_preference='mp4',
            max_parallel_downloads=4,
            save_metadata=False,
            save_thumbnails=False,
            resume_downloads=True
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        self.download_manager.shutdown(wait=True)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_thread_pool_initialization(self):
        """Test thread pool executor initialization."""
        # Test initial state
        assert self.download_manager._executor is None
        
        # Test executor creation
        executor = self.download_manager._ensure_executor()
        assert executor is not None
        assert executor._max_workers == self.download_manager._max_workers
        
        # Test executor reuse
        executor2 = self.download_manager._ensure_executor()
        assert executor2 is executor
    
    def test_thread_pool_restart(self):
        """Test thread pool executor restart when worker count changes."""
        # Initialize executor
        executor1 = self.download_manager._ensure_executor()
        original_workers = self.download_manager._max_workers
        
        # Change worker count
        self.download_manager.set_parallel_workers(original_workers + 2)
        
        # Executor should be restarted
        executor2 = self.download_manager._ensure_executor()
        assert executor2._max_workers == original_workers + 2
    
    def test_download_queue_operations(self):
        """Test download queue basic operations."""
        queue = self.download_manager._download_queue
        
        # Test empty queue
        assert queue.get_queue_size() == 0
        assert len(queue.get_all_tasks()) == 0
        
        # Add tasks
        task_id1 = queue.add_task("https://example.com/video1", self.test_config)
        task_id2 = queue.add_task("https://example.com/video2", self.test_config)
        
        assert queue.get_queue_size() == 2
        assert len(queue.get_all_tasks()) == 2
        
        # Get task status
        status1 = queue.get_task_status(task_id1)
        assert status1 is not None
        
        # Complete task
        from services.download_manager import DownloadResult
        result = DownloadResult(success=True)
        queue.complete_task(task_id1, result)
        
        # Check completion
        task = next((t for t in queue.get_all_tasks() if t.task_id == task_id1), None)
        assert task is not None
        assert task.result == result
    
    def test_parallel_download_efficiency(self):
        """Test parallel download efficiency compared to sequential."""
        import time
        from unittest.mock import patch
        
        # Mock URLs for testing
        test_urls = [
            f"https://example.com/video{i}" for i in range(1, 6)
        ]
        
        def mock_download_single(url, config):
            """Mock download that takes some time."""
            time.sleep(0.1)  # Simulate download time
            result = DownloadResult(success=False)
            result.mark_success(f"/path/to/{url.split('/')[-1]}.mp4", 0.1)
            return result
        
        with patch.object(self.download_manager, 'download_single', side_effect=mock_download_single):
            # Test sequential download (1 worker)
            self.download_manager.set_parallel_workers(1)
            start_time = time.time()
            results_sequential = self.download_manager._download_batch_parallel(test_urls, self.test_config)
            sequential_time = time.time() - start_time
            
            # Test parallel download (4 workers)
            self.download_manager.set_parallel_workers(4)
            start_time = time.time()
            results_parallel = self.download_manager._download_batch_parallel(test_urls, self.test_config)
            parallel_time = time.time() - start_time
            
            # Verify results
            assert len(results_sequential) == len(test_urls)
            assert len(results_parallel) == len(test_urls)
            assert all(r.success for r in results_sequential)
            assert all(r.success for r in results_parallel)
            
            # Parallel should be faster (with some tolerance for test environment)
            speedup_ratio = sequential_time / parallel_time
            assert speedup_ratio > 1.5, f"Expected speedup > 1.5x, got {speedup_ratio:.2f}x"
    
    def test_thread_pool_worker_limits(self):
        """Test thread pool worker count limits."""
        # Test minimum limit
        self.download_manager.set_parallel_workers(0)
        assert self.download_manager._max_workers == 1
        
        # Test maximum limit
        self.download_manager.set_parallel_workers(20)
        assert self.download_manager._max_workers == 10
        
        # Test valid range
        self.download_manager.set_parallel_workers(5)
        assert self.download_manager._max_workers == 5
    
    def test_concurrent_download_tracking(self):
        """Test tracking of concurrent downloads."""
        from unittest.mock import patch
        import threading
        import time
        
        # Mock URLs
        test_urls = [f"https://example.com/video{i}" for i in range(1, 4)]
        
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()
        
        def mock_download_single(url, config):
            nonlocal concurrent_count, max_concurrent
            
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            time.sleep(0.2)  # Simulate download time
            
            with lock:
                concurrent_count -= 1
            
            result = DownloadResult(success=False)
            result.mark_success(f"/path/to/{url.split('/')[-1]}.mp4", 0.2)
            return result
        
        with patch.object(self.download_manager, 'download_single', side_effect=mock_download_single):
            self.download_manager.set_parallel_workers(3)
            results = self.download_manager._download_batch_parallel(test_urls, self.test_config)
            
            # Verify results
            assert len(results) == len(test_urls)
            assert all(r.success for r in results)
            
            # Verify concurrency
            assert max_concurrent <= 3, f"Expected max concurrent <= 3, got {max_concurrent}"
            assert max_concurrent >= 2, f"Expected some concurrency, got {max_concurrent}"
    
    def test_resume_capability_performance(self):
        """Test resume capability and its impact on performance."""
        from unittest.mock import patch, Mock
        
        test_url = "https://example.com/large_video"
        
        # Mock resume state
        from services.download_manager import ResumeState
        mock_resume_state = ResumeState(
            url=test_url,
            video_id="test123",
            title="Test Video",
            output_path="/path/to/video.mp4",
            partial_file_path="/path/to/video.mp4.part",
            downloaded_bytes=500000,  # 50% downloaded
            total_bytes=1000000,
            last_modified=time.time(),
            config_hash="test_hash"
        )
        
        # Test resume detection
        with patch.object(self.download_manager._resume_handler, 'load_resume_state') as mock_load:
            with patch.object(self.download_manager._resume_handler, 'can_resume') as mock_can_resume:
                mock_load.return_value = mock_resume_state
                mock_can_resume.return_value = True
                
                # Test that resume state is detected
                can_resume = self.download_manager.can_resume_download(test_url, self.test_config)
                assert can_resume
                
                # Test resume state loading
                resume_states = self.download_manager.get_resumable_downloads()
                # This will be empty in test environment, but method should work
                assert isinstance(resume_states, list)
    
    def test_progress_reporting_performance(self):
        """Test progress reporting system performance."""
        from unittest.mock import patch
        import time
        
        # Test progress reporter initialization
        reporter = self.download_manager._progress_reporter
        assert reporter is not None
        
        # Test progress tracking for multiple downloads
        test_urls = [f"https://example.com/video{i}" for i in range(1, 4)]
        
        for i, url in enumerate(test_urls):
            reporter.start_download(url, f"Test Video {i+1}", 1000000)
        
        # Simulate progress updates
        for i, url in enumerate(test_urls):
            for progress in [25, 50, 75, 100]:
                downloaded = (progress / 100) * 1000000
                reporter.update_download(
                    url=url,
                    downloaded_bytes=int(downloaded),
                    total_bytes=1000000,
                    speed="1.0 MB/s",
                    eta="30s",
                    status="downloading"
                )
        
        # Complete downloads
        for url in test_urls:
            reporter.complete_download(url, True, 1000000)
        
        # Get summary
        summary = reporter.get_summary()
        assert summary['total_files'] == 3
        assert summary['completed_files'] == 3
        assert summary['failed_files'] == 0
    
    def test_memory_usage_with_large_queues(self):
        """Test memory usage with large download queues."""
        import gc
        
        # Create large number of tasks
        large_url_list = [f"https://example.com/video{i}" for i in range(100)]
        
        # Add tasks to queue
        queue = self.download_manager._download_queue
        task_ids = []
        
        for url in large_url_list:
            task_id = queue.add_task(url, self.test_config)
            task_ids.append(task_id)
        
        # Verify queue size
        assert queue.get_queue_size() == 100
        
        # Complete half the tasks
        for i in range(50):
            result = DownloadResult(success=True)
            queue.complete_task(task_ids[i], result)
        
        # Clear completed tasks
        queue.clear_completed_tasks()
        
        # Force garbage collection
        gc.collect()
        
        # Verify cleanup
        remaining_tasks = queue.get_all_tasks()
        completed_tasks = [t for t in remaining_tasks if t.status.value in ['completed', 'failed']]
        assert len(completed_tasks) == 0, "Completed tasks should be cleared"
    
    def test_error_handling_in_parallel_downloads(self):
        """Test error handling in parallel download scenarios."""
        from unittest.mock import patch
        
        test_urls = [
            "https://example.com/video1",  # Will succeed
            "https://example.com/video2",  # Will fail
            "https://example.com/video3",  # Will succeed
        ]
        
        def mock_download_single(url, config):
            if "video2" in url:
                raise Exception("Network error")
            
            result = DownloadResult(success=False)
            result.mark_success(f"/path/to/{url.split('/')[-1]}.mp4", 0.1)
            return result
        
        with patch.object(self.download_manager, 'download_single', side_effect=mock_download_single):
            results = self.download_manager._download_batch_parallel(test_urls, self.test_config)
            
            # Verify results
            assert len(results) == 3
            assert results[0].success  # video1
            assert not results[1].success  # video2 (failed)
            assert results[2].success  # video3
            
            # Verify error message
            assert "Network error" in results[1].error_message
    
    def test_download_statistics_tracking(self):
        """Test download statistics tracking."""
        from unittest.mock import patch
        
        # Initial stats
        initial_stats = self.download_manager._stats.copy()
        assert initial_stats['total_downloads'] == 0
        
        # Mock successful download
        result1 = DownloadResult(success=False)
        result1.mark_success("/path/to/video1.mp4", 10.5)
        
        # Mock failed download
        result2 = DownloadResult(success=False)
        result2.mark_failure("Download failed")
        
        # Update statistics
        self.download_manager._update_statistics(result1)
        self.download_manager._update_statistics(result2)
        
        # Check updated stats
        stats = self.download_manager._stats
        assert stats['total_downloads'] == 2
        assert stats['successful_downloads'] == 1
        assert stats['failed_downloads'] == 1
        assert stats['total_download_time'] == 10.5
        assert stats['average_download_time'] == 10.5
    
    def test_queue_status_reporting(self):
        """Test queue status and statistics reporting."""
        # Add some tasks
        queue = self.download_manager._download_queue
        task_id1 = queue.add_task("https://example.com/video1", self.test_config)
        task_id2 = queue.add_task("https://example.com/video2", self.test_config)
        
        # Get queue status
        status = self.download_manager.get_queue_status()
        
        assert 'queue_size' in status
        assert 'active_downloads' in status
        assert 'max_workers' in status
        assert 'statistics' in status
        assert 'all_tasks' in status
        
        assert status['queue_size'] == 2
        assert status['max_workers'] == self.download_manager._max_workers
        assert len(status['all_tasks']) == 2
    
    def test_shutdown_cleanup(self):
        """Test proper cleanup during shutdown."""
        from unittest.mock import patch
        import threading
        import time
        
        # Start some mock downloads
        test_urls = [f"https://example.com/video{i}" for i in range(1, 4)]
        
        def slow_download(url, config):
            time.sleep(1.0)  # Slow download
            result = DownloadResult(success=False)
            result.mark_success(f"/path/to/{url.split('/')[-1]}.mp4", 1.0)
            return result
        
        with patch.object(self.download_manager, 'download_single', side_effect=slow_download):
            # Start downloads in background
            executor = self.download_manager._ensure_executor()
            futures = []
            
            for url in test_urls:
                task_id = self.download_manager._download_queue.add_task(url, self.test_config)
                future = executor.submit(self.download_manager._execute_download_task, task_id)
                futures.append(future)
                
                with self.download_manager._lock:
                    self.download_manager._active_futures[task_id] = future
            
            # Give downloads time to start
            time.sleep(0.1)
            
            # Shutdown
            self.download_manager.shutdown(wait=False)
            
            # Verify cleanup
            assert self.download_manager._shutdown_event.is_set()
            assert len(self.download_manager._active_futures) == 0
    
    def test_performance_with_different_worker_counts(self):
        """Test performance scaling with different worker counts."""
        from unittest.mock import patch
        import time
        
        test_urls = [f"https://example.com/video{i}" for i in range(1, 9)]  # 8 videos
        
        def mock_download_single(url, config):
            time.sleep(0.1)  # Consistent download time
            result = DownloadResult(success=False)
            result.mark_success(f"/path/to/{url.split('/')[-1]}.mp4", 0.1)
            return result
        
        performance_results = {}
        
        with patch.object(self.download_manager, 'download_single', side_effect=mock_download_single):
            # Test different worker counts
            for worker_count in [1, 2, 4, 8]:
                self.download_manager.set_parallel_workers(worker_count)
                
                start_time = time.time()
                results = self.download_manager._download_batch_parallel(test_urls, self.test_config)
                end_time = time.time()
                
                performance_results[worker_count] = {
                    'time': end_time - start_time,
                    'success_count': sum(1 for r in results if r.success)
                }
        
        # Verify all downloads succeeded
        for worker_count, perf in performance_results.items():
            assert perf['success_count'] == len(test_urls)
        
        # Verify performance scaling (more workers should be faster, up to a point)
        assert performance_results[1]['time'] > performance_results[2]['time']
        assert performance_results[2]['time'] > performance_results[4]['time']
        
        # Print performance results for manual verification
        print("\nPerformance scaling results:")
        for worker_count, perf in performance_results.items():
            print(f"  {worker_count} workers: {perf['time']:.3f}s")
    
    def test_resume_state_validation(self):
        """Test resume state validation and cleanup."""
        from services.download_manager import ResumeState
        import tempfile
        import os
        
        # Create temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"partial download data")
            temp_file_path = temp_file.name
        
        try:
            # Create valid resume state
            resume_state = ResumeState(
                url="https://example.com/video",
                video_id="test123",
                title="Test Video",
                output_path="/path/to/video.mp4",
                partial_file_path=temp_file_path,
                downloaded_bytes=len(b"partial download data"),
                total_bytes=1000000,
                last_modified=time.time(),
                config_hash="test_hash"
            )
            
            # Test validation
            assert resume_state.is_valid()
            
            # Test percentage calculation
            percentage = resume_state.get_resume_percentage()
            expected_percentage = (len(b"partial download data") / 1000000) * 100
            assert abs(percentage - expected_percentage) < 0.01
            
            # Test invalid state (file doesn't exist)
            os.unlink(temp_file_path)
            assert not resume_state.is_valid()
            
        finally:
            # Cleanup
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)