"""
Interface definitions for CLI components.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from models.core import DownloadConfig, ProgressInfo


class CLIInterface(ABC):
    """Interface for command-line interface operations."""
    
    @abstractmethod
    def parse_arguments(self, args: List[str]) -> DownloadConfig:
        """Parse command-line arguments and return configuration."""
        pass
    
    @abstractmethod
    def display_progress(self, progress: ProgressInfo) -> None:
        """Display progress information to the user."""
        pass
    
    @abstractmethod
    def handle_user_prompts(self, prompt: str) -> str:
        """Handle user prompts and return user input."""
        pass
    
    @abstractmethod
    def display_error(self, error_message: str) -> None:
        """Display error message to the user."""
        pass
    
    @abstractmethod
    def display_success(self, message: str) -> None:
        """Display success message to the user."""
        pass


class ArgumentValidator:
    """Validates and sanitizes CLI arguments."""
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate YouTube URL format."""
        if not url or not isinstance(url, str):
            return False
        
        youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
        return any(domain in url.lower() for domain in youtube_domains)
    
    @staticmethod
    def validate_output_path(path: str) -> bool:
        """Validate output path format."""
        if not path or not isinstance(path, str):
            return False
        
        # Basic path validation - check for invalid characters
        # Note: backslash is valid for Windows paths, colon is valid for drive letters
        invalid_chars = ['<', '>', '"', '|', '?', '*']
        
        # Allow colon only if it's part of a Windows drive letter (e.g., C:)
        if ':' in path:
            # Check if colon is in a valid position for Windows drive letter
            colon_positions = [i for i, char in enumerate(path) if char == ':']
            for pos in colon_positions:
                # Valid if it's at position 1 (like C:) or preceded by a drive letter
                if pos != 1 or not path[pos-1].isalpha():
                    return False
        
        return not any(char in path for char in invalid_chars)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename by removing invalid characters."""
        if not filename:
            return "untitled"
        
        # Replace invalid characters with underscores
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        sanitized = filename
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(' .')
        
        # Ensure filename is not empty after sanitization
        return sanitized if sanitized else "untitled"
    
    @staticmethod
    def validate_quality(quality: str) -> bool:
        """Validate video quality setting."""
        valid_qualities = ['worst', 'best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p']
        return quality in valid_qualities
    
    @staticmethod
    def validate_format(format_name: str) -> bool:
        """Validate video format setting."""
        valid_formats = ['mp4', 'webm', 'mkv']
        return format_name in valid_formats
    
    @staticmethod
    def validate_parallel_count(count: int) -> bool:
        """Validate parallel download count."""
        return isinstance(count, int) and 1 <= count <= 10