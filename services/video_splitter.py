"""
Video splitting service using FFmpeg for timestamp-based video segmentation.
"""

import os
import subprocess
import shutil
from typing import List, Optional, Tuple
from pathlib import Path
import logging
from models.core import Timestamp
from services.interfaces import VideoSplitterInterface

logger = logging.getLogger(__name__)


class VideoSplitter(VideoSplitterInterface):
    """
    Video splitter that uses FFmpeg to split videos based on timestamps.
    
    Uses stream copy (-c copy) to avoid re-encoding for faster processing
    and to maintain original quality.
    """
    
    def __init__(self):
        """Initialize the video splitter."""
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            logger.warning("FFmpeg not found in system PATH")
    
    def validate_ffmpeg_availability(self) -> bool:
        """
        Check if FFmpeg is available in the system.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        return self.ffmpeg_path is not None
    
    def split_video(self, video_path: str, timestamps: List[Timestamp], output_dir: str) -> List[str]:
        """
        Split video based on timestamps.
        
        Args:
            video_path: Path to the input video file
            timestamps: List of timestamps to split at
            output_dir: Directory to save split video files
            
        Returns:
            List of paths to the created split video files
            
        Raises:
            RuntimeError: If FFmpeg is not available or splitting fails
            FileNotFoundError: If input video file doesn't exist
        """
        if not self.validate_ffmpeg_availability():
            raise RuntimeError("FFmpeg is not available. Please install FFmpeg and ensure it's in your PATH.")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Input video file not found: {video_path}")
        
        if not timestamps:
            logger.warning("No timestamps provided for splitting")
            return []
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get video duration
        video_duration = self._get_video_duration(video_path)
        if video_duration is None:
            raise RuntimeError(f"Could not determine duration of video: {video_path}")
        
        # Calculate durations for each chapter
        durations = self.calculate_durations(timestamps, video_duration)
        
        # Generate output file paths
        video_name = Path(video_path).stem
        video_ext = Path(video_path).suffix
        
        split_files = []
        
        for i, (timestamp, duration) in enumerate(zip(timestamps, durations)):
            # Create chapter filename
            chapter_num = i + 1
            safe_label = self._sanitize_filename(timestamp.label)
            output_filename = f"{chapter_num:02d}_{safe_label}{video_ext}"
            output_path = os.path.join(output_dir, output_filename)
            
            try:
                # Split the video segment
                success = self._split_segment(
                    input_path=video_path,
                    output_path=output_path,
                    start_time=timestamp.time_seconds,
                    duration=duration
                )
                
                if success:
                    split_files.append(output_path)
                    logger.info(f"Created chapter {chapter_num}: {output_filename}")
                else:
                    logger.error(f"Failed to create chapter {chapter_num}: {output_filename}")
                    
            except Exception as e:
                logger.error(f"Error splitting chapter {chapter_num}: {e}")
                continue
        
        logger.info(f"Successfully split video into {len(split_files)} chapters")
        return split_files
    
    def calculate_durations(self, timestamps: List[Timestamp], total_duration: float) -> List[float]:
        """
        Calculate duration for each chapter based on timestamps.
        
        Args:
            timestamps: List of timestamps
            total_duration: Total duration of the video in seconds
            
        Returns:
            List of durations for each chapter
        """
        if not timestamps:
            return []
        
        durations = []
        
        for i in range(len(timestamps)):
            if i < len(timestamps) - 1:
                # Duration is the difference to the next timestamp
                duration = timestamps[i + 1].time_seconds - timestamps[i].time_seconds
            else:
                # Last chapter extends to the end of the video
                duration = total_duration - timestamps[i].time_seconds
            
            # Ensure minimum duration of 1 second
            duration = max(duration, 1.0)
            durations.append(duration)
        
        return durations
    
    def _find_ffmpeg(self) -> Optional[str]:
        """
        Find FFmpeg executable in system PATH.
        
        Returns:
            Path to FFmpeg executable or None if not found
        """
        # Try common FFmpeg executable names
        ffmpeg_names = ['ffmpeg', 'ffmpeg.exe']
        
        for name in ffmpeg_names:
            ffmpeg_path = shutil.which(name)
            if ffmpeg_path:
                logger.info(f"Found FFmpeg at: {ffmpeg_path}")
                return ffmpeg_path
        
        return None
    
    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get the duration of a video file using FFprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds or None if failed
        """
        try:
            # Try to find ffprobe
            ffprobe_path = shutil.which('ffprobe') or shutil.which('ffprobe.exe')
            if not ffprobe_path:
                # Fallback to using ffmpeg
                ffprobe_path = self.ffmpeg_path
                if not ffprobe_path:
                    return None
            
            # Use ffprobe to get duration
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                duration_str = data.get('format', {}).get('duration')
                if duration_str:
                    return float(duration_str)
            
            # Fallback: use ffmpeg to get duration
            return self._get_duration_with_ffmpeg(video_path)
            
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return None
    
    def _get_duration_with_ffmpeg(self, video_path: str) -> Optional[float]:
        """
        Get video duration using FFmpeg as fallback.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds or None if failed
        """
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Parse duration from stderr output
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    # Extract duration string (format: HH:MM:SS.ms)
                    duration_part = line.split('Duration:')[1].split(',')[0].strip()
                    return self._parse_duration_string(duration_part)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting duration with FFmpeg: {e}")
            return None
    
    def _parse_duration_string(self, duration_str: str) -> float:
        """
        Parse duration string in HH:MM:SS.ms format to seconds.
        
        Args:
            duration_str: Duration string
            
        Returns:
            Duration in seconds
        """
        try:
            # Remove any extra whitespace
            duration_str = duration_str.strip()
            
            # Split by colon
            parts = duration_str.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid duration format: {duration_str}")
            
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            
            return hours * 3600 + minutes * 60 + seconds
            
        except Exception as e:
            logger.error(f"Error parsing duration string '{duration_str}': {e}")
            return 0.0
    
    def _split_segment(self, input_path: str, output_path: str, start_time: float, duration: float) -> bool:
        """
        Split a single video segment using FFmpeg.
        
        Args:
            input_path: Path to input video
            output_path: Path for output video segment
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Format start time as HH:MM:SS.ms
            start_time_str = self._seconds_to_time_string(start_time)
            duration_str = self._seconds_to_time_string(duration)
            
            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-ss', start_time_str,
                '-t', duration_str,
                '-c', 'copy',  # Stream copy to avoid re-encoding
                '-avoid_negative_ts', 'make_zero',  # Handle timestamp issues
                '-y',  # Overwrite output file if it exists
                output_path
            ]
            
            logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Verify output file was created and has reasonable size
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                    return True
                else:
                    logger.error(f"Output file not created or too small: {output_path}")
                    return False
            else:
                logger.error(f"FFmpeg failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout while splitting segment: {output_path}")
            return False
        except Exception as e:
            logger.error(f"Error splitting segment: {e}")
            return False
    
    def _seconds_to_time_string(self, seconds: float) -> str:
        """
        Convert seconds to HH:MM:SS.ms format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Time string in HH:MM:SS.ms format
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing or replacing invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem
        """
        if not filename:
            return "untitled"
        
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        sanitized = filename
        
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove multiple underscores and trim
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_. ')
        
        # Limit length to avoid filesystem issues
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized
    
    def get_splitting_info(self, video_path: str, timestamps: List[Timestamp]) -> dict:
        """
        Get information about the splitting operation without actually splitting.
        
        Args:
            video_path: Path to the video file
            timestamps: List of timestamps
            
        Returns:
            Dictionary with splitting information
        """
        info = {
            'ffmpeg_available': self.validate_ffmpeg_availability(),
            'video_exists': os.path.exists(video_path),
            'timestamp_count': len(timestamps),
            'estimated_chapters': 0,
            'video_duration': None,
            'chapter_durations': []
        }
        
        if info['video_exists']:
            info['video_duration'] = self._get_video_duration(video_path)
            
            if info['video_duration'] and timestamps:
                info['chapter_durations'] = self.calculate_durations(timestamps, info['video_duration'])
                info['estimated_chapters'] = len(info['chapter_durations'])
        
        return info


# Import re module for sanitize_filename
import re