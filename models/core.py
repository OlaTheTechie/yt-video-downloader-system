"""
Core data models for the YouTube Video Downloader application.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class DownloadStatus(Enum):
    """Status enumeration for download operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VideoFormat(Enum):
    """Supported video formats."""
    MP4 = "mp4"
    WEBM = "webm"
    MKV = "mkv"


class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    M4A = "m4a"
    OGG = "ogg"
    WAV = "wav"


@dataclass
class FormatPreferences:
    """User preferences for video and audio formats."""
    video_codec: str = "h264"
    audio_codec: str = "aac"
    container: str = "mp4"
    prefer_free_formats: bool = False


@dataclass
class DownloadConfig:
    """Configuration settings for download operations."""
    output_directory: str = "./downloads"
    quality: str = "best"
    format_preference: str = "mp4"
    audio_format: str = "mp3"
    split_timestamps: bool = False
    max_parallel_downloads: int = 3
    save_thumbnails: bool = True
    save_metadata: bool = True
    resume_downloads: bool = True
    retry_attempts: int = 3
    format_preferences: FormatPreferences = field(default_factory=FormatPreferences)
    download_subtitles: bool = False
    subtitle_languages: List[str] = field(default_factory=lambda: ['en'])
    subtitle_format: str = "srt"
    auto_generated_subtitles: bool = True
    use_archive: bool = True
    skip_duplicates: bool = True
    
    def __post_init__(self):
        """Validate configuration values after initialization."""
        if self.max_parallel_downloads < 1:
            self.max_parallel_downloads = 1
        elif self.max_parallel_downloads > 10:
            self.max_parallel_downloads = 10
            
        if self.retry_attempts < 0:
            self.retry_attempts = 0
        elif self.retry_attempts > 10:
            self.retry_attempts = 10


@dataclass
class Timestamp:
    """Represents a timestamp marker in video content."""
    time_seconds: float
    label: str
    original_text: str
    
    def __post_init__(self):
        """Validate timestamp values after initialization."""
        if self.time_seconds < 0:
            raise ValueError("Timestamp cannot be negative")
        if not self.label.strip():
            self.label = f"Chapter at {self.format_time()}"
    
    def format_time(self) -> str:
        """Format timestamp as HH:MM:SS or MM:SS string."""
        hours = int(self.time_seconds // 3600)
        minutes = int((self.time_seconds % 3600) // 60)
        seconds = int(self.time_seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"


@dataclass
class SubtitleInfo:
    """Information about available subtitles."""
    language: str
    language_name: str
    is_auto_generated: bool
    formats: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate subtitle info after initialization."""
        if not self.language:
            raise ValueError("Language code cannot be empty")


@dataclass
class VideoMetadata:
    """Metadata information for a video."""
    title: str
    uploader: str
    description: str
    upload_date: str
    duration: float
    view_count: int
    thumbnail_url: str
    video_id: str
    webpage_url: str = ""
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    like_count: Optional[int] = None
    dislike_count: Optional[int] = None
    available_subtitles: List[SubtitleInfo] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'uploader': self.uploader,
            'description': self.description,
            'upload_date': self.upload_date,
            'duration': self.duration,
            'view_count': self.view_count,
            'thumbnail_url': self.thumbnail_url,
            'video_id': self.video_id,
            'webpage_url': self.webpage_url,
            'tags': self.tags,
            'categories': self.categories,
            'like_count': self.like_count,
            'dislike_count': self.dislike_count,
            'available_subtitles': [
                {
                    'language': sub.language,
                    'language_name': sub.language_name,
                    'is_auto_generated': sub.is_auto_generated,
                    'formats': sub.formats
                } for sub in self.available_subtitles
            ]
        }


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    video_path: str = ""
    metadata_path: str = ""
    thumbnail_path: str = ""
    split_files: List[str] = field(default_factory=list)
    subtitle_files: List[str] = field(default_factory=list)
    error_message: str = ""
    download_time: float = 0.0
    status: DownloadStatus = DownloadStatus.PENDING
    video_metadata: Optional[VideoMetadata] = None
    
    def add_split_file(self, file_path: str) -> None:
        """Add a split file to the result."""
        if file_path not in self.split_files:
            self.split_files.append(file_path)
    
    def add_subtitle_file(self, file_path: str) -> None:
        """Add a subtitle file to the result."""
        if file_path not in self.subtitle_files:
            self.subtitle_files.append(file_path)
    
    def mark_success(self, video_path: str, download_time: float) -> None:
        """Mark the download as successful."""
        self.success = True
        self.video_path = video_path
        self.download_time = download_time
        self.status = DownloadStatus.COMPLETED
        self.error_message = ""
    
    def mark_failure(self, error_message: str) -> None:
        """Mark the download as failed."""
        self.success = False
        self.error_message = error_message
        self.status = DownloadStatus.FAILED


@dataclass
class ProgressInfo:
    """Progress information for download operations."""
    current_file: str
    progress_percent: float
    download_speed: str
    eta: str
    files_completed: int
    total_files: int
    current_file_size: int = 0
    total_downloaded: int = 0
    
    def __post_init__(self):
        """Validate progress values after initialization."""
        if self.progress_percent < 0:
            self.progress_percent = 0.0
        elif self.progress_percent > 100:
            self.progress_percent = 100.0
            
        if self.files_completed < 0:
            self.files_completed = 0
        if self.total_files < 0:
            self.total_files = 0
    
    def is_complete(self) -> bool:
        """Check if the operation is complete."""
        return self.files_completed >= self.total_files and self.progress_percent >= 100.0