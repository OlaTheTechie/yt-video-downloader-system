"""
Main application controller for the YouTube Video Downloader.
"""

import logging
from typing import Optional, List
from models.core import DownloadConfig, DownloadResult
from services.interfaces import (
    DownloadManagerInterface,
    ConfigManagerInterface
)
from config.logging_config import setup_logging, get_logger
from config.error_handling import ErrorHandler, YouTubeDownloaderError


class YouTubeDownloaderApp:
    """
    Main application controller that orchestrates all components.
    """
    
    def __init__(
        self,
        download_manager: Optional[DownloadManagerInterface] = None,
        config_manager: Optional[ConfigManagerInterface] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize the YouTube Downloader application.
        
        Args:
            download_manager: Download manager implementation
            config_manager: Configuration manager implementation
            log_level: Logging level for the application
        """
        # Set up logging
        setup_logging(log_level=log_level)
        self.logger = get_logger(__name__)
        
        # Initialize error handler
        self.error_handler = ErrorHandler(self.logger)
        
        # Store component interfaces (will be injected by concrete implementations)
        self.download_manager = download_manager
        self.config_manager = config_manager
        
        self.logger.info("YouTube Downloader application initialized")
    
    def set_download_manager(self, download_manager: DownloadManagerInterface) -> None:
        """Set the download manager implementation."""
        self.download_manager = download_manager
        self.logger.debug("Download manager set")
    
    def set_config_manager(self, config_manager: ConfigManagerInterface) -> None:
        """Set the configuration manager implementation."""
        self.config_manager = config_manager
        self.logger.debug("Configuration manager set")
    
    def download_single_video(self, url: str, config: DownloadConfig) -> DownloadResult:
        """
        Download a single video.
        
        Args:
            url: YouTube video URL
            config: Download configuration
            
        Returns:
            Download result
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self.logger.info(f"Starting single video download: {url}")
        
        try:
            result = self.download_manager.download_single(url, config)
            if result.success:
                self.logger.info(f"Successfully downloaded video: {result.video_path}")
            else:
                self.logger.error(f"Failed to download video: {result.error_message}")
            return result
        except Exception as e:
            self.logger.error(f"Error downloading single video: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download video: {str(e)}", original_exception=e)
    
    def download_playlist(self, url: str, config: DownloadConfig) -> List[DownloadResult]:
        """
        Download all videos in a playlist.
        
        Args:
            url: YouTube playlist URL
            config: Download configuration
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self.logger.info(f"Starting playlist download: {url}")
        
        try:
            results = self.download_manager.download_playlist(url, config)
            successful_downloads = sum(1 for result in results if result.success)
            self.logger.info(f"Playlist download completed: {successful_downloads}/{len(results)} videos successful")
            return results
        except Exception as e:
            self.logger.error(f"Error downloading playlist: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download playlist: {str(e)}", original_exception=e)
    
    def download_batch(self, urls: List[str], config: DownloadConfig) -> List[DownloadResult]:
        """
        Download multiple videos from a list of URLs.
        
        Args:
            urls: List of YouTube video URLs
            config: Download configuration
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self.logger.info(f"Starting batch download: {len(urls)} URLs")
        
        try:
            results = self.download_manager.download_batch(urls, config)
            successful_downloads = sum(1 for result in results if result.success)
            self.logger.info(f"Batch download completed: {successful_downloads}/{len(results)} videos successful")
            return results
        except Exception as e:
            self.logger.error(f"Error downloading batch: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download batch: {str(e)}", original_exception=e)
    
    def load_configuration(self, config_path: Optional[str] = None) -> DownloadConfig:
        """
        Load configuration from file or return default configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Download configuration
            
        Raises:
            YouTubeDownloaderError: If config manager is not set or loading fails
        """
        if not self.config_manager:
            self.logger.warning("Config manager not set, using default configuration")
            return DownloadConfig()
        
        try:
            if config_path:
                config = self.config_manager.load_config(config_path)
                self.logger.info(f"Configuration loaded from: {config_path}")
            else:
                config = DownloadConfig()
                self.logger.info("Using default configuration")
            
            return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to load configuration: {str(e)}", original_exception=e)
    
    def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        self.logger.info("Shutting down YouTube Downloader application")
        
        # Reset error counts
        self.error_handler.reset_error_counts()
        
        # Log final statistics if needed
        self.logger.info("Application shutdown complete")