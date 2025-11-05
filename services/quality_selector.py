"""
Quality selector implementation for video format selection and handling.
"""

import re
from typing import List, Dict, Any, Optional
import yt_dlp

from models.core import FormatPreferences
from services.interfaces import QualitySelectorInterface


class QualitySelector(QualitySelectorInterface):
    """Handles video quality selection and format preferences."""
    
    def __init__(self):
        self._format_priority = {
            'mp4': 10,
            'webm': 8,
            'mkv': 6,
            'avi': 4,
            'mov': 2
        }
        
        self._codec_priority = {
            'h264': 10,
            'avc1': 9,
            'vp9': 8,
            'vp8': 6,
            'av01': 7,
            'h265': 5,
            'hevc': 5
        }
        
        self._audio_codec_priority = {
            'aac': 10,
            'mp3': 8,
            'opus': 6,
            'vorbis': 4,
            'm4a': 9
        }
    
    def get_available_qualities(self, url: str) -> List[str]:
        """Get list of available quality options for a video."""
        qualities = []
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'listformats': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and 'formats' in info:
                    heights = set()
                    
                    for fmt in info['formats']:
                        height = fmt.get('height')
                        if height and isinstance(height, int):
                            heights.add(f"{height}p")
                    
                    # Sort qualities from highest to lowest
                    qualities = sorted(heights, key=lambda x: int(x[:-1]), reverse=True)
                    
                    # Add standard quality options
                    if qualities:
                        qualities = ['best'] + qualities + ['worst']
                    else:
                        qualities = ['best', 'worst']
                        
        except Exception as e:
            print(f"Warning: Could not extract quality information: {e}")
            qualities = ['best', '1080p', '720p', '480p', '360p', 'worst']
        
        return qualities
    
    def select_best_quality(self, available_formats: List[Dict[str, Any]], preference: str) -> Dict[str, Any]:
        """Select the best quality format based on preference."""
        if not available_formats:
            return {}
        
        # Handle special preferences
        if preference == 'best':
            return self._select_best_overall(available_formats)
        elif preference == 'worst':
            return self._select_worst_overall(available_formats)
        elif preference.endswith('p'):
            return self._select_by_resolution(available_formats, preference)
        elif preference in ['audio', 'audio-only']:
            return self._select_audio_only(available_formats)
        else:
            # Default to best quality
            return self._select_best_overall(available_formats)
    
    def apply_format_preferences(self, formats: List[Dict[str, Any]], preferences: FormatPreferences) -> Dict[str, Any]:
        """Apply format preferences to select the best format."""
        if not formats:
            return {}
        
        scored_formats = []
        
        for fmt in formats:
            score = self._calculate_format_score(fmt, preferences)
            scored_formats.append((score, fmt))
        
        # Sort by score (highest first) and return the best format
        scored_formats.sort(key=lambda x: x[0], reverse=True)
        return scored_formats[0][1] if scored_formats else {}
    
    def create_format_selector(self, quality: str, preferences: FormatPreferences, audio_only: bool = False) -> str:
        """Create yt-dlp format selector string."""
        if audio_only:
            return self._create_audio_format_selector(preferences)
        
        # Build video format selector
        selectors = []
        
        if quality == 'best':
            selectors.append(f"best[vcodec^={preferences.video_codec}][ext={preferences.container}]")
            selectors.append(f"best[ext={preferences.container}]")
            selectors.append("best")
        elif quality == 'worst':
            selectors.append(f"worst[vcodec^={preferences.video_codec}][ext={preferences.container}]")
            selectors.append(f"worst[ext={preferences.container}]")
            selectors.append("worst")
        elif quality.endswith('p'):
            height = quality[:-1]
            selectors.append(f"best[height<={height}][vcodec^={preferences.video_codec}][ext={preferences.container}]")
            selectors.append(f"best[height<={height}][ext={preferences.container}]")
            selectors.append(f"best[height<={height}]")
            selectors.append("best")
        else:
            # Fallback to best
            selectors.append("best")
        
        return "/".join(selectors)
    
    def extract_audio_formats(self, formats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract audio-only formats from available formats."""
        audio_formats = []
        
        for fmt in formats:
            # Check if it's audio-only (no video codec or height)
            if (fmt.get('vcodec') == 'none' or 
                fmt.get('vcodec') is None and fmt.get('height') is None):
                if fmt.get('acodec') and fmt.get('acodec') != 'none':
                    audio_formats.append(fmt)
        
        return audio_formats
    
    def _select_best_overall(self, formats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best overall quality format."""
        video_formats = [f for f in formats if f.get('height') and f.get('vcodec') != 'none']
        
        if not video_formats:
            return formats[0] if formats else {}
        
        # Sort by resolution (height) and then by format preference
        def sort_key(fmt):
            height = fmt.get('height', 0)
            ext = fmt.get('ext', '').lower()
            vcodec = fmt.get('vcodec', '').lower()
            
            format_score = self._format_priority.get(ext, 0)
            codec_score = self._codec_priority.get(vcodec, 0)
            
            return (height, format_score, codec_score)
        
        video_formats.sort(key=sort_key, reverse=True)
        return video_formats[0]
    
    def _select_worst_overall(self, formats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the worst overall quality format."""
        video_formats = [f for f in formats if f.get('height') and f.get('vcodec') != 'none']
        
        if not video_formats:
            return formats[-1] if formats else {}
        
        # Sort by resolution (height) ascending
        video_formats.sort(key=lambda f: f.get('height', 0))
        return video_formats[0]
    
    def _select_by_resolution(self, formats: List[Dict[str, Any]], resolution: str) -> Dict[str, Any]:
        """Select format by specific resolution (e.g., '720p')."""
        target_height = int(resolution[:-1])
        
        # Find formats at or below target resolution
        suitable_formats = []
        for fmt in formats:
            height = fmt.get('height')
            if height and height <= target_height and fmt.get('vcodec') != 'none':
                suitable_formats.append(fmt)
        
        if not suitable_formats:
            # Fallback to any video format
            suitable_formats = [f for f in formats if f.get('height') and f.get('vcodec') != 'none']
        
        if not suitable_formats:
            return formats[0] if formats else {}
        
        # Select the best format among suitable ones
        def sort_key(fmt):
            height = fmt.get('height', 0)
            ext = fmt.get('ext', '').lower()
            vcodec = fmt.get('vcodec', '').lower()
            
            format_score = self._format_priority.get(ext, 0)
            codec_score = self._codec_priority.get(vcodec, 0)
            
            return (height, format_score, codec_score)
        
        suitable_formats.sort(key=sort_key, reverse=True)
        return suitable_formats[0]
    
    def _select_audio_only(self, formats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best audio-only format."""
        audio_formats = self.extract_audio_formats(formats)
        
        if not audio_formats:
            return {}
        
        # Sort by audio quality and codec preference
        def sort_key(fmt):
            abr = fmt.get('abr', 0) or 0  # Audio bitrate
            acodec = fmt.get('acodec', '').lower()
            ext = fmt.get('ext', '').lower()
            
            codec_score = self._audio_codec_priority.get(acodec, 0)
            format_score = self._format_priority.get(ext, 0)
            
            return (abr, codec_score, format_score)
        
        audio_formats.sort(key=sort_key, reverse=True)
        return audio_formats[0]
    
    def _calculate_format_score(self, fmt: Dict[str, Any], preferences: FormatPreferences) -> float:
        """Calculate a score for a format based on preferences."""
        score = 0.0
        
        # Video codec preference
        vcodec = fmt.get('vcodec', '').lower()
        if preferences.video_codec.lower() in vcodec:
            score += 50
        elif vcodec in self._codec_priority:
            score += self._codec_priority[vcodec]
        
        # Audio codec preference
        acodec = fmt.get('acodec', '').lower()
        if preferences.audio_codec.lower() in acodec:
            score += 30
        elif acodec in self._audio_codec_priority:
            score += self._audio_codec_priority[acodec]
        
        # Container format preference
        ext = fmt.get('ext', '').lower()
        if ext == preferences.container.lower():
            score += 40
        elif ext in self._format_priority:
            score += self._format_priority[ext]
        
        # Resolution bonus (higher is better)
        height = fmt.get('height', 0)
        if height:
            score += min(height / 100, 50)  # Cap at 50 points for resolution
        
        # Audio bitrate bonus
        abr = fmt.get('abr', 0) or 0
        if abr:
            score += min(abr / 10, 20)  # Cap at 20 points for audio bitrate
        
        # Video bitrate bonus
        vbr = fmt.get('vbr', 0) or 0
        if vbr:
            score += min(vbr / 1000, 30)  # Cap at 30 points for video bitrate
        
        # Penalty for free formats if not preferred
        if not preferences.prefer_free_formats:
            if ext in ['webm', 'ogg']:
                score -= 10
        else:
            if ext in ['webm', 'ogg']:
                score += 15
        
        return score
    
    def _create_audio_format_selector(self, preferences: FormatPreferences) -> str:
        """Create format selector for audio-only downloads."""
        selectors = []
        
        # Prefer specific audio codec and format
        selectors.append(f"bestaudio[acodec^={preferences.audio_codec}]")
        selectors.append("bestaudio")
        
        # Fallback to any audio
        selectors.append("best[vcodec=none]")
        selectors.append("best")
        
        return "/".join(selectors)
    
    def get_format_info(self, url: str) -> Dict[str, Any]:
        """Get detailed format information for a video."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and 'formats' in info:
                    return {
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'formats': info['formats'],
                        'format_count': len(info['formats']),
                        'has_audio_only': bool(self.extract_audio_formats(info['formats'])),
                        'max_height': max((f.get('height', 0) or 0 for f in info['formats']), default=0),
                        'available_codecs': list(set(
                            f.get('vcodec', '') for f in info['formats'] 
                            if f.get('vcodec') and f.get('vcodec') != 'none'
                        ))
                    }
                    
        except Exception as e:
            print(f"Warning: Could not extract format information: {e}")
        
        return {}
    
    def validate_quality_preference(self, preference: str, available_qualities: List[str]) -> bool:
        """Validate if a quality preference is available."""
        if preference in ['best', 'worst', 'audio', 'audio-only']:
            return True
        
        if preference.endswith('p'):
            try:
                int(preference[:-1])
                return True
            except ValueError:
                return False
        
        return preference in available_qualities