"""
Workflow manager for orchestrating download operations with optional timestamp splitting.
"""

import os
from typing import List, Optional, Callable
from pathlib import Path
import logging

from models.core import DownloadConfig, DownloadResult, VideoMetadata
from services.download_manager import DownloadManager
from services.timestamp_parser import TimestampParser
from services.video_splitter import VideoSplitter

logger = logging.getLogger(__name__)


class WorkflowManager:
    """
    Manages the complete download workflow including optional timestamp splitting.
    
    Provides user choice mechanisms and proper folder organization for split videos.
    """
    
    def __init__(self):
        """Initialize the workflow manager."""
        self.download_manager = DownloadManager()
        self.timestamp_parser = TimestampParser()
        self.video_splitter = VideoSplitter()
    
    def download_with_optional_splitting(self, url: str, config: DownloadConfig, 
                                       interactive: bool = True) -> DownloadResult:
        """
        Download a video with optional timestamp splitting.
        
        Args:
            url: Video URL to download
            config: Download configuration
            interactive: Whether to prompt user for splitting choice
            
        Returns:
            DownloadResult with splitting information
        """
        # First, get preview information if splitting is potentially requested
        should_split = False
        
        if config.split_timestamps or interactive:
            preview = self.download_manager.get_splitting_preview(url)
            
            if 'error' not in preview and preview['timestamps_found'] > 0:
                if interactive and not config.split_timestamps:
                    # Ask user if they want to split
                    should_split = self._prompt_user_for_splitting(preview)
                elif config.split_timestamps:
                    # Splitting is explicitly requested
                    should_split = True
                    if preview['ffmpeg_available']:
                        logger.info(f"Will split video into {preview['timestamps_found']} chapters")
                    else:
                        logger.warning("FFmpeg not available, will skip splitting")
                        should_split = False
        
        # Update config based on decision
        download_config = DownloadConfig(**config.__dict__)
        download_config.split_timestamps = should_split
        
        # Perform the download
        result = self.download_manager.download_single(url, download_config)
        
        return result
    
    def download_playlist_with_splitting_options(self, url: str, config: DownloadConfig,
                                               interactive: bool = True) -> List[DownloadResult]:
        """
        Download a playlist with optional timestamp splitting for each video.
        
        Args:
            url: Playlist URL to download
            config: Download configuration
            interactive: Whether to prompt user for splitting choices
            
        Returns:
            List of DownloadResults
        """
        # For playlists, we'll apply the same splitting decision to all videos
        # unless interactive mode is enabled for per-video decisions
        
        if interactive and not config.split_timestamps:
            # Ask user for global splitting preference
            print("\nPlaylist download detected.")
            print("You can choose to:")
            print("1. Apply timestamp splitting to all videos (if timestamps found)")
            print("2. Download all videos without splitting")
            print("3. Ask for each video individually (slower)")
            
            while True:
                choice = input("Enter your choice (1/2/3): ").strip()
                if choice == '1':
                    config.split_timestamps = True
                    interactive = False  # Apply to all
                    break
                elif choice == '2':
                    config.split_timestamps = False
                    interactive = False  # Apply to all
                    break
                elif choice == '3':
                    interactive = True  # Ask for each video
                    break
                else:
                    print("Please enter 1, 2, or 3.")
        
        # Download the playlist
        if interactive:
            # Custom playlist download with per-video splitting decisions
            return self._download_playlist_interactive(url, config)
        else:
            # Standard playlist download
            return self.download_manager.download_playlist(url, config)
    
    def organize_split_videos(self, result: DownloadResult, base_output_dir: str) -> None:
        """
        Organize split video files into proper folder structure.
        
        Args:
            result: Download result containing split files
            base_output_dir: Base output directory
        """
        if not result.split_files or not result.video_metadata:
            return
        
        try:
            # Create organized folder structure
            video_title = self._sanitize_filename(result.video_metadata.title)
            organized_dir = os.path.join(base_output_dir, f"{video_title}_chapters")
            
            # Ensure the directory exists
            os.makedirs(organized_dir, exist_ok=True)
            
            # Move metadata and thumbnail to chapters folder if they exist
            if result.metadata_path and os.path.exists(result.metadata_path):
                new_metadata_path = os.path.join(organized_dir, os.path.basename(result.metadata_path))
                if result.metadata_path != new_metadata_path:
                    os.rename(result.metadata_path, new_metadata_path)
                    result.metadata_path = new_metadata_path
            
            if result.thumbnail_path and os.path.exists(result.thumbnail_path):
                new_thumbnail_path = os.path.join(organized_dir, os.path.basename(result.thumbnail_path))
                if result.thumbnail_path != new_thumbnail_path:
                    os.rename(result.thumbnail_path, new_thumbnail_path)
                    result.thumbnail_path = new_thumbnail_path
            
            logger.info(f"Organized split videos in: {organized_dir}")
            
        except Exception as e:
            logger.error(f"Error organizing split videos: {e}")
    
    def _prompt_user_for_splitting(self, preview: dict) -> bool:
        """
        Prompt user whether to split video based on preview information.
        
        Args:
            preview: Preview information from download manager
            
        Returns:
            True if user wants to split, False otherwise
        """
        if not preview.get('ffmpeg_available', False):
            print("FFmpeg is not available. Video splitting is not possible.")
            return False
        
        # Display preview information
        print(f"\nVideo: {preview['title']}")
        print(f"Duration: {preview['duration']:.0f} seconds")
        print(f"Found {preview['timestamps_found']} timestamps:")
        
        # Show first few timestamps
        timestamps = preview.get('timestamps', [])
        for i, ts in enumerate(timestamps[:5], 1):
            print(f"  {i}. {ts['time']} - {ts['label']}")
        
        if len(timestamps) > 5:
            print(f"  ... and {len(timestamps) - 5} more")
        
        # Prompt user
        while True:
            response = input("\nSplit video into chapters? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def _download_playlist_interactive(self, url: str, config: DownloadConfig) -> List[DownloadResult]:
        """
        Download playlist with interactive splitting decisions for each video.
        
        Args:
            url: Playlist URL
            config: Download configuration
            
        Returns:
            List of DownloadResults
        """
        # This is a simplified version - in practice, you'd extract playlist info first
        # and then process each video individually
        results = []
        
        try:
            # Extract playlist info
            import yt_dlp
            ydl_opts = {'quiet': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)
                
                if not playlist_info or 'entries' not in playlist_info:
                    result = DownloadResult(success=False)
                    result.mark_failure("Failed to extract playlist information")
                    return [result]
                
                entries = [entry for entry in playlist_info['entries'] if entry]
                
                # Create playlist folder
                playlist_title = self._sanitize_filename(
                    playlist_info.get('title', 'playlist')
                )
                playlist_dir = Path(config.output_directory) / playlist_title
                playlist_dir.mkdir(parents=True, exist_ok=True)
                
                # Update config for playlist directory
                playlist_config = DownloadConfig(**config.__dict__)
                playlist_config.output_directory = str(playlist_dir)
                
                # Process each video with individual splitting decisions
                for i, entry in enumerate(entries, 1):
                    if not entry or not entry.get('url'):
                        continue
                    
                    print(f"\nProcessing video {i}/{len(entries)}: {entry.get('title', 'Unknown')}")
                    
                    # Download with optional splitting
                    result = self.download_with_optional_splitting(
                        entry['url'], playlist_config, interactive=True
                    )
                    results.append(result)
                    
                    # Organize split videos if any
                    if result.split_files:
                        self.organize_split_videos(result, str(playlist_dir))
                        
        except Exception as e:
            result = DownloadResult(success=False)
            result.mark_failure(f"Interactive playlist processing error: {str(e)}")
            results = [result]
        
        return results
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file operations."""
        if not filename:
            return "untitled"
        
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length and strip whitespace
        filename = filename.strip()[:200]
        
        return filename or 'untitled'
    
    def download_batch_from_file(self, file_path: str, config: DownloadConfig, 
                               interactive: bool = False) -> List[DownloadResult]:
        """
        Download videos from a batch file with optional splitting.
        
        Args:
            file_path: Path to file containing URLs
            config: Download configuration
            interactive: Whether to prompt for splitting decisions
            
        Returns:
            List of DownloadResults
        """
        try:
            # Read URLs from file
            urls = self._read_batch_file(file_path)
            
            if not urls:
                result = DownloadResult(success=False)
                result.mark_failure("No valid URLs found in batch file")
                return [result]
            
            logger.info(f"Loaded {len(urls)} URLs from batch file: {file_path}")
            
            # If interactive mode and splitting not explicitly set, ask user
            if interactive and not config.split_timestamps:
                print(f"\nBatch file loaded with {len(urls)} URLs.")
                print("Timestamp splitting options:")
                print("1. Enable splitting for all videos (if timestamps found)")
                print("2. Disable splitting for all videos")
                
                while True:
                    choice = input("Enter your choice (1/2): ").strip()
                    if choice == '1':
                        config.split_timestamps = True
                        break
                    elif choice == '2':
                        config.split_timestamps = False
                        break
                    else:
                        print("Please enter 1 or 2.")
            
            # Process batch download
            results = self.download_manager.download_batch(urls, config)
            
            # Organize split videos if any
            for result in results:
                if result.split_files and result.video_metadata:
                    self.organize_split_videos(result, config.output_directory)
            
            return results
            
        except Exception as e:
            logger.error(f"Batch file processing error: {e}")
            result = DownloadResult(success=False)
            result.mark_failure(f"Batch file processing error: {str(e)}")
            return [result]
    
    def _read_batch_file(self, file_path: str) -> List[str]:
        """
        Read URLs from a batch file.
        
        Args:
            file_path: Path to batch file
            
        Returns:
            List of valid URLs
        """
        urls = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Basic URL validation
                    if self._is_valid_youtube_url(line):
                        urls.append(line)
                    else:
                        logger.warning(f"Invalid URL on line {line_num}: {line}")
                        print(f"Warning: Invalid URL on line {line_num}: {line}")
                        
        except FileNotFoundError:
            raise FileNotFoundError(f"Batch file not found: {file_path}")
        except Exception as e:
            raise Exception(f"Failed to read batch file {file_path}: {str(e)}")
        
        return urls
    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid YouTube URL, False otherwise
        """
        youtube_domains = [
            'youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com'
        ]
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower() in youtube_domains
        except Exception:
            return False
    
    def create_batch_file_template(self, output_path: str) -> None:
        """
        Create a template batch file with examples and instructions.
        
        Args:
            output_path: Path where to create the template file
        """
        template_content = """# YouTube Video Downloader Batch File
# 
# Instructions:
# - Add one YouTube URL per line
# - Lines starting with # are comments and will be ignored
# - Empty lines are ignored
# - Supports both individual videos and playlists
#
# Examples:

# Individual videos:
# https://www.youtube.com/watch?v=dQw4w9WgXcQ
# https://youtu.be/dQw4w9WgXcQ

# Playlists:
# https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq8HmPME

# Add your URLs below:

"""
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            print(f"Batch file template created: {output_path}")
        except Exception as e:
            logger.error(f"Failed to create batch file template: {e}")
            raise Exception(f"Failed to create batch file template: {str(e)}")
    
    def get_workflow_summary(self, results: List[DownloadResult]) -> dict:
        """
        Get a summary of the workflow results.
        
        Args:
            results: List of download results
            
        Returns:
            Dictionary with workflow summary
        """
        total_downloads = len(results)
        successful_downloads = sum(1 for r in results if r.success)
        failed_downloads = total_downloads - successful_downloads
        
        total_split_files = sum(len(r.split_files) for r in results)
        videos_with_splits = sum(1 for r in results if r.split_files)
        
        total_download_time = sum(r.download_time for r in results if r.success)
        
        return {
            'total_downloads': total_downloads,
            'successful_downloads': successful_downloads,
            'failed_downloads': failed_downloads,
            'videos_with_splits': videos_with_splits,
            'total_split_files': total_split_files,
            'total_download_time': total_download_time,
            'average_download_time': total_download_time / successful_downloads if successful_downloads > 0 else 0
        }