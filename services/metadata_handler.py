"""
Metadata handler implementation for video information extraction and preservation.
"""

import json
import os
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
import yt_dlp

from models.core import VideoMetadata, SubtitleInfo
from services.interfaces import MetadataHandlerInterface


class MetadataHandler(MetadataHandlerInterface):
    """Handles video metadata extraction, processing, and preservation."""
    
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_metadata(self, url: str) -> VideoMetadata:
        """Extract metadata from a video URL."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writeinfojson': False,
                'writethumbnail': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("Could not extract video information")
                
                return self._create_metadata_from_info(info)
                
        except yt_dlp.DownloadError as e:
            raise ValueError(f"yt-dlp error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Metadata extraction error: {str(e)}")
    
    def save_metadata(self, metadata: VideoMetadata, output_path: str) -> None:
        """Save metadata to a JSON file."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Convert metadata to dictionary and save
            metadata_dict = metadata.to_dict()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise IOError(f"Could not save metadata to {output_path}: {str(e)}")
    
    def download_thumbnail(self, thumbnail_url: str, output_path: str) -> None:
        """Download and save video thumbnail."""
        if not thumbnail_url:
            raise ValueError("No thumbnail URL provided")
        
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Download thumbnail with timeout
            response = self._session.get(thumbnail_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save thumbnail to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
        except requests.RequestException as e:
            raise IOError(f"Could not download thumbnail from {thumbnail_url}: {str(e)}")
        except Exception as e:
            raise IOError(f"Could not save thumbnail to {output_path}: {str(e)}")
    
    def extract_enhanced_metadata(self, url: str) -> Dict[str, Any]:
        """Extract enhanced metadata including additional fields."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writeinfojson': False,
                'writethumbnail': False,
                'writesubtitles': False,
                'writeautomaticsub': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return {}
                
                # Extract comprehensive metadata
                enhanced_metadata = {
                    'basic_info': self._create_metadata_from_info(info).to_dict(),
                    'technical_info': {
                        'format_count': len(info.get('formats', [])),
                        'has_subtitles': bool(info.get('subtitles')),
                        'has_automatic_captions': bool(info.get('automatic_captions')),
                        'available_qualities': self._extract_available_qualities(info.get('formats', [])),
                        'available_formats': self._extract_format_summary(info.get('formats', [])),
                        'chapters': self._extract_chapters(info),
                        'thumbnails': info.get('thumbnails', [])
                    },
                    'platform_info': {
                        'extractor': info.get('extractor'),
                        'extractor_key': info.get('extractor_key'),
                        'webpage_url': info.get('webpage_url'),
                        'original_url': info.get('original_url'),
                        'playlist': info.get('playlist'),
                        'playlist_index': info.get('playlist_index')
                    },
                    'content_info': {
                        'age_limit': info.get('age_limit'),
                        'is_live': info.get('is_live', False),
                        'was_live': info.get('was_live', False),
                        'live_status': info.get('live_status'),
                        'availability': info.get('availability'),
                        'language': info.get('language'),
                        'subtitles_languages': list(info.get('subtitles', {}).keys()),
                        'automatic_captions_languages': list(info.get('automatic_captions', {}).keys())
                    }
                }
                
                return enhanced_metadata
                
        except Exception as e:
            print(f"Warning: Could not extract enhanced metadata: {e}")
            return {}
    
    def save_enhanced_metadata(self, enhanced_metadata: Dict[str, Any], output_path: str) -> None:
        """Save enhanced metadata to a JSON file."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise IOError(f"Could not save enhanced metadata to {output_path}: {str(e)}")
    
    def get_best_thumbnail_url(self, url: str) -> Optional[str]:
        """Get the best quality thumbnail URL for a video."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                thumbnails = info.get('thumbnails', [])
                if not thumbnails:
                    return info.get('thumbnail')
                
                # Sort thumbnails by preference (resolution, then format)
                def thumbnail_score(thumb):
                    width = thumb.get('width', 0) or 0
                    height = thumb.get('height', 0) or 0
                    resolution = width * height
                    
                    # Prefer certain formats
                    url_str = thumb.get('url', '').lower()
                    format_bonus = 0
                    if 'maxresdefault' in url_str:
                        format_bonus = 1000
                    elif 'hqdefault' in url_str:
                        format_bonus = 500
                    elif 'mqdefault' in url_str:
                        format_bonus = 250
                    
                    return resolution + format_bonus
                
                best_thumbnail = max(thumbnails, key=thumbnail_score)
                return best_thumbnail.get('url')
                
        except Exception as e:
            print(f"Warning: Could not get best thumbnail URL: {e}")
            return None
    
    def download_best_thumbnail(self, url: str, output_path: str) -> bool:
        """Download the best quality thumbnail for a video."""
        thumbnail_url = self.get_best_thumbnail_url(url)
        
        if not thumbnail_url:
            return False
        
        try:
            self.download_thumbnail(thumbnail_url, output_path)
            return True
        except Exception as e:
            print(f"Warning: Could not download best thumbnail: {e}")
            return False
    
    def extract_description_metadata(self, description: str) -> Dict[str, Any]:
        """Extract structured information from video description."""
        if not description:
            return {}
        
        metadata = {
            'has_timestamps': False,
            'has_links': False,
            'has_social_media': False,
            'word_count': len(description.split()),
            'line_count': len(description.split('\n')),
            'timestamps': [],
            'links': [],
            'social_media_links': [],
            'hashtags': []
        }
        
        # Extract timestamps
        import re
        timestamp_patterns = [
            r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b',  # 1:23 or 1:23:45
            r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]',  # [1:23] or [1:23:45]
            r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]'  # 1:23 - or 1:23:45 -
        ]
        
        for pattern in timestamp_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                if match not in [t['timestamp'] for t in metadata['timestamps']]:
                    metadata['timestamps'].append({
                        'timestamp': match,
                        'seconds': self._timestamp_to_seconds(match)
                    })
        
        metadata['has_timestamps'] = len(metadata['timestamps']) > 0
        
        # Extract links
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        links = re.findall(url_pattern, description)
        metadata['links'] = list(set(links))
        metadata['has_links'] = len(metadata['links']) > 0
        
        # Extract social media links
        social_patterns = [
            r'https?://(?:www\.)?(?:twitter|x)\.com/[^\s]+',
            r'https?://(?:www\.)?instagram\.com/[^\s]+',
            r'https?://(?:www\.)?facebook\.com/[^\s]+',
            r'https?://(?:www\.)?linkedin\.com/[^\s]+',
            r'https?://(?:www\.)?tiktok\.com/[^\s]+',
            r'https?://(?:www\.)?discord\.gg/[^\s]+'
        ]
        
        for pattern in social_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            metadata['social_media_links'].extend(matches)
        
        metadata['social_media_links'] = list(set(metadata['social_media_links']))
        metadata['has_social_media'] = len(metadata['social_media_links']) > 0
        
        # Extract hashtags
        hashtag_pattern = r'#\w+'
        hashtags = re.findall(hashtag_pattern, description)
        metadata['hashtags'] = list(set(hashtags))
        
        return metadata
    
    def _create_metadata_from_info(self, info: Dict[str, Any]) -> VideoMetadata:
        """Create VideoMetadata object from yt-dlp info dict."""
        # Extract subtitle information
        available_subtitles = []
        
        # Process manual subtitles
        subtitles = info.get('subtitles', {})
        for lang_code, formats in subtitles.items():
            if formats:
                available_formats = [fmt.get('ext', 'unknown') for fmt in formats if fmt.get('ext')]
                available_subtitles.append(SubtitleInfo(
                    language=lang_code,
                    language_name=self._get_language_name(lang_code),
                    is_auto_generated=False,
                    formats=available_formats
                ))
        
        # Process automatic captions
        auto_captions = info.get('automatic_captions', {})
        for lang_code, formats in auto_captions.items():
            if formats:
                available_formats = [fmt.get('ext', 'unknown') for fmt in formats if fmt.get('ext')]
                available_subtitles.append(SubtitleInfo(
                    language=lang_code,
                    language_name=self._get_language_name(lang_code),
                    is_auto_generated=True,
                    formats=available_formats
                ))
        
        return VideoMetadata(
            title=info.get('title', 'Unknown'),
            uploader=info.get('uploader', 'Unknown'),
            description=info.get('description', ''),
            upload_date=info.get('upload_date', ''),
            duration=float(info.get('duration', 0)),
            view_count=int(info.get('view_count', 0)),
            thumbnail_url=info.get('thumbnail', ''),
            video_id=info.get('id', ''),
            webpage_url=info.get('webpage_url', ''),
            tags=info.get('tags', []) or [],
            categories=info.get('categories', []) or [],
            like_count=info.get('like_count'),
            dislike_count=info.get('dislike_count'),
            available_subtitles=available_subtitles
        )
    
    def _extract_available_qualities(self, formats: List[Dict[str, Any]]) -> List[str]:
        """Extract available video qualities from formats."""
        qualities = set()
        
        for fmt in formats:
            height = fmt.get('height')
            if height and isinstance(height, int):
                qualities.add(f"{height}p")
        
        # Sort from highest to lowest
        return sorted(qualities, key=lambda x: int(x[:-1]), reverse=True)
    
    def _extract_format_summary(self, formats: List[Dict[str, Any]]) -> Dict[str, int]:
        """Extract summary of available formats."""
        format_counts = {}
        
        for fmt in formats:
            ext = fmt.get('ext', 'unknown')
            format_counts[ext] = format_counts.get(ext, 0) + 1
        
        return format_counts
    
    def _extract_chapters(self, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract chapter information if available."""
        chapters = info.get('chapters', [])
        
        if not chapters:
            return []
        
        chapter_list = []
        for chapter in chapters:
            chapter_info = {
                'title': chapter.get('title', 'Untitled Chapter'),
                'start_time': chapter.get('start_time', 0),
                'end_time': chapter.get('end_time', 0)
            }
            chapter_list.append(chapter_info)
        
        return chapter_list
    
    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert timestamp string to seconds."""
        try:
            parts = timestamp.split(':')
            if len(parts) == 2:
                # MM:SS format
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:
                # HH:MM:SS format
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0.0
        except (ValueError, IndexError):
            return 0.0
    
    def create_metadata_filename(self, title: str, video_id: str) -> str:
        """Create a safe filename for metadata files."""
        # Sanitize title
        safe_title = self._sanitize_filename(title)
        
        # Create filename with video ID for uniqueness
        if video_id:
            filename = f"{safe_title}_{video_id}.info.json"
        else:
            filename = f"{safe_title}.info.json"
        
        return filename
    
    def create_thumbnail_filename(self, title: str, video_id: str, extension: str = 'jpg') -> str:
        """Create a safe filename for thumbnail files."""
        # Sanitize title
        safe_title = self._sanitize_filename(title)
        
        # Create filename with video ID for uniqueness
        if video_id:
            filename = f"{safe_title}_{video_id}.{extension}"
        else:
            filename = f"{safe_title}.{extension}"
        
        return filename
    
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
    
    def _get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name from code."""
        # Common language code mappings
        language_names = {
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
        return language_names.get(lang_code.lower(), lang_code.upper())