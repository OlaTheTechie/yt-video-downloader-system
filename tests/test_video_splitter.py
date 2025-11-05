"""
Unit tests for VideoSplitter class.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from services.video_splitter import VideoSplitter
from models.core import Timestamp


class TestVideoSplitter:
    """Test cases for VideoSplitter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.splitter = VideoSplitter()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test video file
        self.test_video = self.temp_path / "test_video.mp4"
        self.test_video.touch()
        
        # Create test timestamps
        self.test_timestamps = [
            Timestamp(0, "Introduction", "0:00 Introduction"),
            Timestamp(300, "Main Content", "5:00 Main Content"),
            Timestamp(600, "Conclusion", "10:00 Conclusion")
        ]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('shutil.which')
    def test_find_ffmpeg_found(self, mock_which):
        """Test finding FFmpeg when it exists."""
        mock_which.return_value = '/usr/bin/ffmpeg'
        
        splitter = VideoSplitter()
        assert splitter.ffmpeg_path == '/usr/bin/ffmpeg'
    
    @patch('shutil.which')
    def test_find_ffmpeg_not_found(self, mock_which):
        """Test finding FFmpeg when it doesn't exist."""
        mock_which.return_value = None
        
        splitter = VideoSplitter()
        assert splitter.ffmpeg_path is None
    
    def test_validate_ffmpeg_availability_true(self):
        """Test FFmpeg availability validation when available."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        assert self.splitter.validate_ffmpeg_availability() is True
    
    def test_validate_ffmpeg_availability_false(self):
        """Test FFmpeg availability validation when not available."""
        self.splitter.ffmpeg_path = None
        assert self.splitter.validate_ffmpeg_availability() is False
    
    def test_calculate_durations(self):
        """Test calculating chapter durations."""
        total_duration = 900.0  # 15 minutes
        
        durations = self.splitter.calculate_durations(self.test_timestamps, total_duration)
        
        assert len(durations) == 3
        assert durations[0] == 300.0  # 0 to 5:00
        assert durations[1] == 300.0  # 5:00 to 10:00
        assert durations[2] == 300.0  # 10:00 to end (15:00)
    
    def test_calculate_durations_empty(self):
        """Test calculating durations for empty timestamp list."""
        durations = self.splitter.calculate_durations([], 900.0)
        assert len(durations) == 0
    
    def test_calculate_durations_single(self):
        """Test calculating durations for single timestamp."""
        timestamps = [Timestamp(300, "Only Chapter", "5:00 Only Chapter")]
        total_duration = 900.0
        
        durations = self.splitter.calculate_durations(timestamps, total_duration)
        
        assert len(durations) == 1
        assert durations[0] == 600.0  # 5:00 to end (15:00)
    
    def test_calculate_durations_minimum(self):
        """Test calculating durations with minimum duration enforcement."""
        # Create timestamps very close together
        timestamps = [
            Timestamp(0, "Start", "0:00 Start"),
            Timestamp(0.5, "Almost Immediate", "0:00 Almost Immediate")
        ]
        total_duration = 10.0
        
        durations = self.splitter.calculate_durations(timestamps, total_duration)
        
        # Should enforce minimum 1 second duration
        assert durations[0] == 1.0
        assert durations[1] == 9.5  # 10.0 - 0.5
    
    def test_seconds_to_time_string(self):
        """Test converting seconds to time string format."""
        test_cases = [
            (0, "00:00:00.000"),
            (30, "00:00:30.000"),
            (90, "00:01:30.000"),
            (3661.5, "01:01:01.500"),
            (7323.123, "02:02:03.123")
        ]
        
        for seconds, expected in test_cases:
            result = self.splitter._seconds_to_time_string(seconds)
            assert result == expected
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("Normal Title", "Normal Title"),
            ("Title with <invalid> chars", "Title with _invalid_ chars"),
            ("Title/with\\slashes", "Title_with_slashes"),
            ("Title:with|pipes?", "Title_with_pipes"),
            ("Title*with\"quotes", "Title_with_quotes"),
            ("Multiple___underscores", "Multiple_underscores"),
            ("  Trimmed  ", "Trimmed"),
            ("", "untitled"),
            ("   ", "untitled"),
            ("A" * 150, "A" * 100),  # Length limit
        ]
        
        for input_filename, expected in test_cases:
            result = self.splitter._sanitize_filename(input_filename)
            assert result == expected
    
    def test_parse_duration_string(self):
        """Test parsing duration strings."""
        test_cases = [
            ("00:05:30.25", 330.25),
            ("01:23:45.00", 5025.0),
            ("10:00:00.50", 36000.5),
            ("00:00:15.123", 15.123)
        ]
        
        for duration_str, expected in test_cases:
            result = self.splitter._parse_duration_string(duration_str)
            assert abs(result - expected) < 0.001  # Allow small floating point differences
    
    def test_parse_duration_string_invalid(self):
        """Test parsing invalid duration strings."""
        invalid_cases = [
            "invalid",
            "5:30",  # Missing hours
            "1:2:3:4",  # Too many parts
            "",
            "   "
        ]
        
        for invalid_str in invalid_cases:
            result = self.splitter._parse_duration_string(invalid_str)
            assert result == 0.0
    
    @patch('subprocess.run')
    def test_get_video_duration_with_ffprobe(self, mock_run):
        """Test getting video duration using ffprobe."""
        # Mock successful ffprobe response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"format": {"duration": "300.5"}}'
        mock_run.return_value = mock_result
        
        with patch('shutil.which', return_value='/usr/bin/ffprobe'):
            duration = self.splitter._get_video_duration(str(self.test_video))
        
        assert duration == 300.5
    
    @patch.object(VideoSplitter, '_get_duration_with_ffmpeg')
    @patch('subprocess.run')
    def test_get_video_duration_with_ffmpeg_fallback(self, mock_run, mock_ffmpeg_duration):
        """Test getting video duration using FFmpeg fallback."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock ffprobe failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result
        
        # Mock ffmpeg fallback success
        mock_ffmpeg_duration.return_value = 330.25
        
        with patch('shutil.which', return_value=None):  # ffprobe not found
            duration = self.splitter._get_video_duration(str(self.test_video))
        
        assert abs(duration - 330.25) < 0.01
        mock_ffmpeg_duration.assert_called_once()
    
    @patch('subprocess.run')
    def test_get_video_duration_failure(self, mock_run):
        """Test getting video duration when both methods fail."""
        mock_run.side_effect = Exception("Command failed")
        
        duration = self.splitter._get_video_duration(str(self.test_video))
        assert duration is None
    
    @patch('subprocess.run')
    def test_split_segment_success(self, mock_run):
        """Test successful video segment splitting."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock successful FFmpeg execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Create output file to simulate successful split
        output_path = str(self.temp_path / "output.mp4")
        
        # Mock os.path.exists and os.path.getsize
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=2048):
            
            success = self.splitter._split_segment(
                input_path=str(self.test_video),
                output_path=output_path,
                start_time=300.0,
                duration=180.0
            )
        
        assert success is True
        mock_run.assert_called_once()
        
        # Verify FFmpeg command structure
        call_args = mock_run.call_args[0][0]
        assert '/usr/bin/ffmpeg' in call_args
        assert '-i' in call_args
        assert '-ss' in call_args
        assert '-t' in call_args
        assert '-c' in call_args
        assert 'copy' in call_args
    
    @patch('subprocess.run')
    def test_split_segment_ffmpeg_failure(self, mock_run):
        """Test video segment splitting when FFmpeg fails."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock FFmpeg failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "FFmpeg error message"
        mock_run.return_value = mock_result
        
        output_path = str(self.temp_path / "output.mp4")
        
        success = self.splitter._split_segment(
            input_path=str(self.test_video),
            output_path=output_path,
            start_time=300.0,
            duration=180.0
        )
        
        assert success is False
    
    @patch('subprocess.run')
    def test_split_segment_timeout(self, mock_run):
        """Test video segment splitting with timeout."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired('ffmpeg', 300)
        
        output_path = str(self.temp_path / "output.mp4")
        
        success = self.splitter._split_segment(
            input_path=str(self.test_video),
            output_path=output_path,
            start_time=300.0,
            duration=180.0
        )
        
        assert success is False
    
    def test_split_video_no_ffmpeg(self):
        """Test splitting video when FFmpeg is not available."""
        self.splitter.ffmpeg_path = None
        
        with pytest.raises(RuntimeError, match="FFmpeg is not available"):
            self.splitter.split_video(
                str(self.test_video),
                self.test_timestamps,
                str(self.temp_path)
            )
    
    def test_split_video_file_not_found(self):
        """Test splitting video when input file doesn't exist."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        with pytest.raises(FileNotFoundError):
            self.splitter.split_video(
                "/nonexistent/video.mp4",
                self.test_timestamps,
                str(self.temp_path)
            )
    
    def test_split_video_no_timestamps(self):
        """Test splitting video with no timestamps."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        result = self.splitter.split_video(
            str(self.test_video),
            [],
            str(self.temp_path)
        )
        
        assert result == []
    
    @patch.object(VideoSplitter, '_get_video_duration')
    @patch.object(VideoSplitter, '_split_segment')
    def test_split_video_success(self, mock_split_segment, mock_get_duration):
        """Test successful video splitting."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock video duration
        mock_get_duration.return_value = 900.0  # 15 minutes
        
        # Mock successful segment splitting
        mock_split_segment.return_value = True
        
        # Create output directory
        output_dir = str(self.temp_path / "chapters")
        
        result = self.splitter.split_video(
            str(self.test_video),
            self.test_timestamps,
            output_dir
        )
        
        assert len(result) == 3
        assert mock_split_segment.call_count == 3
        
        # Verify output directory was created
        assert os.path.exists(output_dir)
        
        # Verify filenames are properly formatted
        for file_path in result:
            assert output_dir in file_path
            assert file_path.endswith('.mp4')
    
    @patch.object(VideoSplitter, '_get_video_duration')
    def test_split_video_duration_failure(self, mock_get_duration):
        """Test splitting video when duration cannot be determined."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock duration failure
        mock_get_duration.return_value = None
        
        with pytest.raises(RuntimeError, match="Could not determine duration"):
            self.splitter.split_video(
                str(self.test_video),
                self.test_timestamps,
                str(self.temp_path)
            )
    
    @patch.object(VideoSplitter, '_get_video_duration')
    @patch.object(VideoSplitter, '_split_segment')
    def test_split_video_partial_failure(self, mock_split_segment, mock_get_duration):
        """Test video splitting with some segments failing."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        
        # Mock video duration
        mock_get_duration.return_value = 900.0
        
        # Mock partial success (first and third succeed, second fails)
        mock_split_segment.side_effect = [True, False, True]
        
        output_dir = str(self.temp_path / "chapters")
        
        result = self.splitter.split_video(
            str(self.test_video),
            self.test_timestamps,
            output_dir
        )
        
        # Should only return successful splits
        assert len(result) == 2
        assert mock_split_segment.call_count == 3
    
    def test_get_splitting_info_ffmpeg_not_available(self):
        """Test getting splitting info when FFmpeg is not available."""
        self.splitter.ffmpeg_path = None
        
        info = self.splitter.get_splitting_info(str(self.test_video), self.test_timestamps)
        
        assert info['ffmpeg_available'] is False
        assert info['video_exists'] is True
        assert info['timestamp_count'] == 3
        assert info['estimated_chapters'] == 0
    
    @patch.object(VideoSplitter, '_get_video_duration')
    def test_get_splitting_info_success(self, mock_get_duration):
        """Test getting splitting info successfully."""
        self.splitter.ffmpeg_path = '/usr/bin/ffmpeg'
        mock_get_duration.return_value = 900.0
        
        info = self.splitter.get_splitting_info(str(self.test_video), self.test_timestamps)
        
        assert info['ffmpeg_available'] is True
        assert info['video_exists'] is True
        assert info['timestamp_count'] == 3
        assert info['video_duration'] == 900.0
        assert info['estimated_chapters'] == 3
        assert len(info['chapter_durations']) == 3
    
    def test_get_splitting_info_file_not_exists(self):
        """Test getting splitting info for non-existent file."""
        info = self.splitter.get_splitting_info("/nonexistent/video.mp4", self.test_timestamps)
        
        assert info['video_exists'] is False
        assert info['video_duration'] is None
        assert info['estimated_chapters'] == 0