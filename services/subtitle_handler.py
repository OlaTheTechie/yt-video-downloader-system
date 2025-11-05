"""
Subtitle handler implementation for subtitle detection, download, and organization.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import yt_dlp
import logging

from models.core import SubtitleInfo, DownloadConfig, VideoMetadata


class SubtitleHandler:
    """Handles subtitle detection, download, and organization."""
    
    # Common subtitle formats supported by yt-dlp
    SUPPORTED_FORMATS = ['srt', 'vtt', 'ass', 'ttml', 'json3']
    
    # Language code mappings for common languages
    LANGUAGE_NAMES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'nl': 'Dutch',
        'sv': 'Swedish',
        'no': 'Norwegian',
        'da': 'Danish',
        'fi': 'Finnish',
        'pl': 'Polish',
        'tr': 'Turkish',
        'th': 'Thai',
        'vi': 'Vietnamese'
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize SubtitleHandler.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def get_available_subtitles(self, url: str) -> List[SubtitleInfo]:
        """
        Get list of available subtitles for a video.
        
        Args:
            url: Video URL
            
        Returns:
            List of SubtitleInfo objects
            
        Raises:
            ValueError: If subtitle information cannot be extracted
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("Could not extract video information")
                
                subtitle_info = []
                
                # Process manual subtitles
                subtitles = info.get('subtitles', {})
                for lang_code, formats in subtitles.items():
                    if formats:  # Check if formats list is not empty
                        available_formats = [fmt.get('ext', 'unknown') for fmt in formats if fmt.get('ext')]
                        subtitle_info.append(SubtitleInfo(
                            language=lang_code,
                            language_name=self._get_language_name(lang_code),
                            is_auto_generated=False,
                            formats=available_formats
                        ))
                
                # Process automatic captions
                auto_captions = info.get('automatic_captions', {})
                for lang_code, formats in auto_captions.items():
                    if formats:  # Check if formats list is not empty
                        available_formats = [fmt.get('ext', 'unknown') for fmt in formats if fmt.get('ext')]
                        subtitle_info.append(SubtitleInfo(
                            language=lang_code,
                            language_name=self._get_language_name(lang_code),
                            is_auto_generated=True,
                            formats=available_formats
                        ))
                
                self.logger.info(f"Found {len(subtitle_info)} subtitle tracks for video")
                return subtitle_info
                
        except yt_dlp.DownloadError as e:
            raise ValueError(f"yt-dlp error while getting subtitles: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error getting available subtitles: {str(e)}")
    
    def download_subtitles(self, url: str, output_dir: str, config: DownloadConfig, 
                          video_metadata: Optional[VideoMetadata] = None) -> List[str]:
        """
        Download subtitles for a video.
        
        Args:
            url: Video URL
            output_dir: Directory to save subtitles
            config: Download configuration
            video_metadata: Optional video metadata for filename generation
            
        Returns:
            List of downloaded subtitle file paths
            
        Raises:
            ValueError: If subtitles cannot be downloaded
        """
        if not config.download_subtitles:
            return []
        
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate base filename
            if video_metadata:
                base_filename = self._sanitize_filename(f"{video_metadata.title}_{video_metadata.video_id}")
            else:
                # Extract video ID from URL as fallback
                video_id = self._extract_video_id(url)
                base_filename = f"video_{video_id}" if video_id else "video"
            
            # Configure yt-dlp options for subtitle download
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'writesubtitles': True,
                'writeautomaticsub': config.auto_generated_subtitles,
                'subtitleslangs': config.subtitle_languages,
                'subtitlesformat': config.subtitle_format,
                'skip_download': True,  # Only download subtitles, not video
                'outtmpl': os.path.join(output_dir, f"{base_filename}.%(ext)s")
            }
            
            downloaded_files = []
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download subtitles
                ydl.download([url])
                
                # Find downloaded subtitle files
                for lang in config.subtitle_languages:
                    subtitle_patterns = [
                        f"{base_filename}.{lang}.{config.subtitle_format}",
                        f"{base_filename}.{lang}.{config.subtitle_format}",
                        f"{base_filename}-{lang}.{config.subtitle_format}"
                    ]
                    
                    for pattern in subtitle_patterns:
                        subtitle_path = os.path.join(output_dir, pattern)
                        if os.path.exists(subtitle_path):
                            downloaded_files.append(subtitle_path)
                            self.logger.info(f"Downloaded subtitle: {subtitle_path}")
                            break
            
            # Also check for auto-generated subtitles if enabled
            if config.auto_generated_subtitles:
                for lang in config.subtitle_languages:
                    auto_patterns = [
                        f"{base_filename}.{lang}.auto.{config.subtitle_format}",
                        f"{base_filename}-{lang}-auto.{config.subtitle_format}"
                    ]
                    
                    for pattern in auto_patterns:
                        subtitle_path = os.path.join(output_dir, pattern)
                        if os.path.exists(subtitle_path) and subtitle_path not in downloaded_files:
                            downloaded_files.append(subtitle_path)
                            self.logger.info(f"Downloaded auto-generated subtitle: {subtitle_path}")
                            break
            
            return downloaded_files
            
        except yt_dlp.DownloadError as e:
            raise ValueError(f"yt-dlp error while downloading subtitles: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error downloading subtitles: {str(e)}")
    
    def organize_subtitles_with_video(self, video_path: str, subtitle_files: List[str]) -> List[str]:
        """
        Organize subtitle files alongside the video file.
        
        Args:
            video_path: Path to the video file
            subtitle_files: List of subtitle file paths
            
        Returns:
            List of organized subtitle file paths
        """
        if not subtitle_files or not os.path.exists(video_path):
            return subtitle_files
        
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        
        organized_files = []
        
        for subtitle_file in subtitle_files:
            if not os.path.exists(subtitle_file):
                continue
            
            # Extract language and format from subtitle filename
            subtitle_basename = os.path.basename(subtitle_file)
            subtitle_ext = os.path.splitext(subtitle_basename)[1]
            
            # Try to extract language code from filename
            lang_match = re.search(r'\.([a-z]{2,3})(?:\.auto)?\.', subtitle_basename)
            if lang_match:
                lang_code = lang_match.group(1)
                is_auto = '.auto.' in subtitle_basename
                
                # Create new filename matching video
                if is_auto:
                    new_filename = f"{video_name}.{lang_code}.auto{subtitle_ext}"
                else:
                    new_filename = f"{video_name}.{lang_code}{subtitle_ext}"
            else:
                # Fallback to simple naming
                new_filename = f"{video_name}{subtitle_ext}"
            
            new_path = os.path.join(video_dir, new_filename)
            
            # Move/rename subtitle file if needed
            if subtitle_file != new_path:
                try:
                    os.rename(subtitle_file, new_path)
                    organized_files.append(new_path)
                    self.logger.info(f"Organized subtitle: {new_path}")
                except OSError as e:
                    self.logger.warning(f"Could not organize subtitle {subtitle_file}: {e}")
                    organized_files.append(subtitle_file)
            else:
                organized_files.append(subtitle_file)
        
        return organized_files
    
    def filter_preferred_languages(self, available_subtitles: List[SubtitleInfo], 
                                 preferred_languages: List[str]) -> List[SubtitleInfo]:
        """
        Filter subtitles by preferred languages.
        
        Args:
            available_subtitles: List of available subtitle info
            preferred_languages: List of preferred language codes
            
        Returns:
            Filtered list of subtitle info
        """
        if not preferred_languages:
            return available_subtitles
        
        # Convert to set for faster lookup
        preferred_set = set(preferred_languages)
        
        filtered = []
        for subtitle in available_subtitles:
            if subtitle.language in preferred_set:
                filtered.append(subtitle)
        
        # If no preferred languages found, return English if available
        if not filtered and 'en' not in preferred_set:
            for subtitle in available_subtitles:
                if subtitle.language == 'en':
                    filtered.append(subtitle)
                    break
        
        return filtered
    
    def get_subtitle_summary(self, available_subtitles: List[SubtitleInfo]) -> Dict[str, Any]:
        """
        Get summary information about available subtitles.
        
        Args:
            available_subtitles: List of available subtitle info
            
        Returns:
            Dictionary with subtitle summary
        """
        if not available_subtitles:
            return {
                'total_count': 0,
                'manual_count': 0,
                'auto_generated_count': 0,
                'languages': [],
                'formats': []
            }
        
        manual_count = sum(1 for sub in available_subtitles if not sub.is_auto_generated)
        auto_count = sum(1 for sub in available_subtitles if sub.is_auto_generated)
        
        languages = list(set(sub.language for sub in available_subtitles))
        all_formats = set()
        for sub in available_subtitles:
            all_formats.update(sub.formats)
        
        return {
            'total_count': len(available_subtitles),
            'manual_count': manual_count,
            'auto_generated_count': auto_count,
            'languages': sorted(languages),
            'formats': sorted(list(all_formats))
        }
    
    def validate_subtitle_format(self, format_name: str) -> bool:
        """
        Validate if subtitle format is supported.
        
        Args:
            format_name: Format name to validate
            
        Returns:
            True if format is supported
        """
        return format_name.lower() in self.SUPPORTED_FORMATS
    
    def _get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name from code."""
        return self.LANGUAGE_NAMES.get(lang_code.lower(), lang_code.upper())
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from URL."""
        # YouTube video ID extraction
        youtube_patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file operations."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Limit length and strip whitespace
        filename = filename.strip()[:150]
        
        return filename or 'video'
    
    def create_subtitle_filename(self, video_title: str, video_id: str, 
                               language: str, format_ext: str, is_auto: bool = False) -> str:
        """
        Create a standardized subtitle filename.
        
        Args:
            video_title: Video title
            video_id: Video ID
            language: Language code
            format_ext: File extension (e.g., 'srt')
            is_auto: Whether subtitle is auto-generated
            
        Returns:
            Standardized subtitle filename
        """
        safe_title = self._sanitize_filename(video_title)
        
        if is_auto:
            filename = f"{safe_title}_{video_id}.{language}.auto.{format_ext}"
        else:
            filename = f"{safe_title}_{video_id}.{language}.{format_ext}"
        
        return filename