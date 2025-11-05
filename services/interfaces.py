"""
Interface definitions for all major service components.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from models.core import (
    DownloadConfig, VideoMetadata, Timestamp, DownloadResult, 
    ProgressInfo, FormatPreferences, SubtitleInfo
)


class DownloadManagerInterface(ABC):
    """Interface for download management operations."""
    
    @abstractmethod
    def download_single(self, url: str, config: DownloadConfig) -> DownloadResult:
        """Download a single video."""
        pass
    
    @abstractmethod
    def download_playlist(self, url: str, config: DownloadConfig) -> List[DownloadResult]:
        """Download all videos in a playlist."""
        pass
    
    @abstractmethod
    def download_batch(self, urls: List[str], config: DownloadConfig) -> List[DownloadResult]:
        """Download multiple videos from a list of URLs."""
        pass
    
    @abstractmethod
    def set_parallel_workers(self, count: int) -> None:
        """Set the number of parallel download workers."""
        pass
    
    @abstractmethod
    def set_progress_callback(self, callback: Callable[[ProgressInfo], None]) -> None:
        """Set callback function for progress updates."""
        pass


class TimestampParserInterface(ABC):
    """Interface for timestamp parsing operations."""
    
    @abstractmethod
    def parse_description(self, description: str) -> List[Timestamp]:
        """Parse timestamps from video description."""
        pass
    
    @abstractmethod
    def validate_timestamps(self, timestamps: List[Timestamp]) -> bool:
        """Validate that timestamps are in chronological order."""
        pass
    
    @abstractmethod
    def extract_chapter_names(self, description: str, timestamps: List[Timestamp]) -> List[str]:
        """Extract chapter names from timestamp lines."""
        pass


class VideoSplitterInterface(ABC):
    """Interface for video splitting operations."""
    
    @abstractmethod
    def split_video(self, video_path: str, timestamps: List[Timestamp], output_dir: str) -> List[str]:
        """Split video based on timestamps."""
        pass
    
    @abstractmethod
    def validate_ffmpeg_availability(self) -> bool:
        """Check if FFmpeg is available in the system."""
        pass
    
    @abstractmethod
    def calculate_durations(self, timestamps: List[Timestamp], total_duration: float) -> List[float]:
        """Calculate duration for each chapter."""
        pass


class QualitySelectorInterface(ABC):
    """Interface for video quality selection operations."""
    
    @abstractmethod
    def select_best_quality(self, available_formats: List[Dict[str, Any]], preference: str) -> Dict[str, Any]:
        """Select the best quality format based on preference."""
        pass
    
    @abstractmethod
    def get_available_qualities(self, url: str) -> List[str]:
        """Get list of available quality options for a video."""
        pass
    
    @abstractmethod
    def apply_format_preferences(self, formats: List[Dict[str, Any]], preferences: FormatPreferences) -> Dict[str, Any]:
        """Apply format preferences to select the best format."""
        pass


class MetadataHandlerInterface(ABC):
    """Interface for metadata handling operations."""
    
    @abstractmethod
    def extract_metadata(self, url: str) -> VideoMetadata:
        """Extract metadata from a video URL."""
        pass
    
    @abstractmethod
    def save_metadata(self, metadata: VideoMetadata, output_path: str) -> None:
        """Save metadata to a JSON file."""
        pass
    
    @abstractmethod
    def download_thumbnail(self, thumbnail_url: str, output_path: str) -> None:
        """Download and save video thumbnail."""
        pass


class ConfigManagerInterface(ABC):
    """Interface for configuration management operations."""
    
    @abstractmethod
    def load_config(self, config_path: str) -> DownloadConfig:
        """Load configuration from a file."""
        pass
    
    @abstractmethod
    def merge_cli_args(self, config: DownloadConfig, cli_args: Dict[str, Any]) -> DownloadConfig:
        """Merge CLI arguments with configuration."""
        pass
    
    @abstractmethod
    def save_default_config(self, output_path: str) -> None:
        """Save default configuration to a file."""
        pass
    
    @abstractmethod
    def validate_config(self, config: DownloadConfig) -> bool:
        """Validate configuration values."""
        pass


class SubtitleHandlerInterface(ABC):
    """Interface for subtitle handling operations."""
    
    @abstractmethod
    def get_available_subtitles(self, url: str) -> List[SubtitleInfo]:
        """Get list of available subtitles for a video."""
        pass
    
    @abstractmethod
    def download_subtitles(self, url: str, output_dir: str, config: DownloadConfig, 
                          video_metadata: Optional[VideoMetadata] = None) -> List[str]:
        """Download subtitles for a video."""
        pass
    
    @abstractmethod
    def organize_subtitles_with_video(self, video_path: str, subtitle_files: List[str]) -> List[str]:
        """Organize subtitle files alongside the video file."""
        pass
    
    @abstractmethod
    def filter_preferred_languages(self, available_subtitles: List[SubtitleInfo], 
                                 preferred_languages: List[str]) -> List[SubtitleInfo]:
        """Filter subtitles by preferred languages."""
        pass


class ArchiveManagerInterface(ABC):
    """Interface for archive management and duplicate detection operations."""
    
    @abstractmethod
    def is_downloaded(self, video_id: str) -> bool:
        """Check if a video has already been downloaded."""
        pass
    
    @abstractmethod
    def add_download_record(self, video_metadata: VideoMetadata, download_result: DownloadResult) -> None:
        """Add a download record to the archive."""
        pass
    
    @abstractmethod
    def get_download_record(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get download record for a video."""
        pass
    
    @abstractmethod
    def find_duplicates_by_content(self) -> List[List[Dict[str, Any]]]:
        """Find potential duplicate downloads based on content hash."""
        pass
    
    @abstractmethod
    def cleanup_missing_files(self) -> List[str]:
        """Remove archive records for files that no longer exist."""
        pass