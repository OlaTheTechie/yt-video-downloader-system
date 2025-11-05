"""
Main application controller for the YouTube Video Downloader.
"""

import logging
import signal
import sys
import atexit
from typing import Optional, List, Dict, Any
from pathlib import Path

from models.core import DownloadConfig, DownloadResult, ProgressInfo
from services.interfaces import (
    DownloadManagerInterface,
    ConfigManagerInterface
)
from services.workflow_manager import WorkflowManager
from services.download_manager import DownloadManager
from config import ConfigManager
from config.logging_config import setup_logging, get_logger
from config.error_handling import ErrorHandler, YouTubeDownloaderError


class YouTubeDownloaderApp:
    """
    Main application controller that orchestrates all components.
    
    This class serves as the central coordinator for all download operations,
    providing workflow routing based on user input and proper initialization
    and cleanup procedures.
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
        
        # Initialize components
        self.config_manager = config_manager or ConfigManager()
        self.download_manager = download_manager or DownloadManager()
        self.workflow_manager = WorkflowManager()
        
        # Application state
        self._is_running = False
        self._cleanup_registered = False
        
        # Register cleanup handlers
        self._register_cleanup_handlers()
        
        self.logger.info("YouTube Downloader application initialized")
    
    def _register_cleanup_handlers(self) -> None:
        """Register cleanup handlers for graceful shutdown."""
        if not self._cleanup_registered:
            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Register atexit handler
            atexit.register(self.shutdown)
            
            self._cleanup_registered = True
            self.logger.debug("Cleanup handlers registered")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_names = {signal.SIGINT: 'SIGINT', signal.SIGTERM: 'SIGTERM'}
        signal_name = signal_names.get(signum, f'Signal {signum}')
        
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown()
        sys.exit(0)
    
    def set_download_manager(self, download_manager: DownloadManagerInterface) -> None:
        """Set the download manager implementation."""
        self.download_manager = download_manager
        self.workflow_manager.download_manager = download_manager
        self.logger.debug("Download manager set")
    
    def set_config_manager(self, config_manager: ConfigManagerInterface) -> None:
        """Set the configuration manager implementation."""
        self.config_manager = config_manager
        self.logger.debug("Configuration manager set")
    
    def download_single_video(self, url: str, config: DownloadConfig, interactive: bool = False) -> DownloadResult:
        """
        Download a single video with optional timestamp splitting.
        
        Args:
            url: YouTube video URL
            config: Download configuration
            interactive: Whether to prompt user for splitting decisions
            
        Returns:
            Download result
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self._is_running = True
        self.logger.info(f"Starting single video download: {url}")
        
        try:
            # Use workflow manager for enhanced functionality
            result = self.workflow_manager.download_with_optional_splitting(
                url, config, interactive=interactive
            )
            
            if result.success:
                self.logger.info(f"Successfully downloaded video: {result.video_path}")
                if result.split_files:
                    self.logger.info(f"Video split into {len(result.split_files)} chapters")
            else:
                self.logger.error(f"Failed to download video: {result.error_message}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error downloading single video: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download video: {str(e)}", original_exception=e)
        finally:
            self._is_running = False
    
    def download_playlist(self, url: str, config: DownloadConfig, interactive: bool = False) -> List[DownloadResult]:
        """
        Download all videos in a playlist with optional timestamp splitting.
        
        Args:
            url: YouTube playlist URL
            config: Download configuration
            interactive: Whether to prompt user for splitting decisions
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self._is_running = True
        self.logger.info(f"Starting playlist download: {url}")
        
        try:
            # Use workflow manager for enhanced functionality
            results = self.workflow_manager.download_playlist_with_splitting_options(
                url, config, interactive=interactive
            )
            
            successful_downloads = sum(1 for result in results if result.success)
            total_split_files = sum(len(r.split_files) for r in results if r.split_files)
            
            self.logger.info(f"Playlist download completed: {successful_downloads}/{len(results)} videos successful")
            if total_split_files > 0:
                self.logger.info(f"Total split files created: {total_split_files}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error downloading playlist: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download playlist: {str(e)}", original_exception=e)
        finally:
            self._is_running = False
    
    def download_batch(self, urls: List[str], config: DownloadConfig, interactive: bool = False) -> List[DownloadResult]:
        """
        Download multiple videos from a list of URLs with optional timestamp splitting.
        
        Args:
            urls: List of YouTube video URLs
            config: Download configuration
            interactive: Whether to prompt user for splitting decisions
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If download manager is not set or download fails
        """
        if not self.download_manager:
            raise YouTubeDownloaderError("Download manager not initialized")
        
        self._is_running = True
        self.logger.info(f"Starting batch download: {len(urls)} URLs")
        
        try:
            # Use download manager directly for batch processing
            results = self.download_manager.download_batch(urls, config)
            
            successful_downloads = sum(1 for result in results if result.success)
            total_split_files = sum(len(r.split_files) for r in results if r.split_files)
            
            self.logger.info(f"Batch download completed: {successful_downloads}/{len(results)} videos successful")
            if total_split_files > 0:
                self.logger.info(f"Total split files created: {total_split_files}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error downloading batch: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to download batch: {str(e)}", original_exception=e)
        finally:
            self._is_running = False
    
    def download_batch_from_file(self, file_path: str, config: DownloadConfig, interactive: bool = False) -> List[DownloadResult]:
        """
        Download videos from a batch file with optional timestamp splitting.
        
        Args:
            file_path: Path to file containing URLs
            config: Download configuration
            interactive: Whether to prompt user for splitting decisions
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If file processing fails
        """
        self._is_running = True
        self.logger.info(f"Starting batch download from file: {file_path}")
        
        try:
            # Use workflow manager for file-based batch processing
            results = self.workflow_manager.download_batch_from_file(
                file_path, config, interactive=interactive
            )
            
            successful_downloads = sum(1 for result in results if result.success)
            total_split_files = sum(len(r.split_files) for r in results if r.split_files)
            
            self.logger.info(f"Batch file download completed: {successful_downloads}/{len(results)} videos successful")
            if total_split_files > 0:
                self.logger.info(f"Total split files created: {total_split_files}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing batch file: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to process batch file: {str(e)}", original_exception=e)
        finally:
            self._is_running = False
    
    def load_configuration(self, config_path: Optional[str] = None, cli_args: Optional[Dict[str, Any]] = None) -> DownloadConfig:
        """
        Load configuration from file and merge with CLI arguments.
        
        Args:
            config_path: Path to configuration file
            cli_args: CLI arguments to merge with configuration
            
        Returns:
            Download configuration
            
        Raises:
            YouTubeDownloaderError: If config manager is not set or loading fails
        """
        if not self.config_manager:
            self.logger.warning("Config manager not set, using default configuration")
            return DownloadConfig()
        
        try:
            if config_path and Path(config_path).exists():
                config = self.config_manager.load_config(config_path)
                self.logger.info(f"Configuration loaded from: {config_path}")
            else:
                # Try to load default config
                default_config_path = self.config_manager.get_config_path()
                if Path(default_config_path).exists():
                    config = self.config_manager.load_config(default_config_path)
                    self.logger.info(f"Default configuration loaded from: {default_config_path}")
                else:
                    config = DownloadConfig()
                    self.logger.info("Using default configuration")
            
            # Merge CLI arguments if provided
            if cli_args:
                config = self.config_manager.merge_cli_args(config, cli_args)
                self.logger.debug("CLI arguments merged with configuration")
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise YouTubeDownloaderError(f"Failed to load configuration: {str(e)}", original_exception=e)
    
    def route_workflow(self, workflow_type: str, url_or_path: str, config: DownloadConfig, 
                      interactive: bool = False) -> List[DownloadResult]:
        """
        Route workflow based on input type (single, playlist, batch).
        
        Args:
            workflow_type: Type of workflow ('single', 'playlist', 'batch')
            url_or_path: URL for single/playlist or file path for batch
            config: Download configuration
            interactive: Whether to enable interactive mode
            
        Returns:
            List of download results
            
        Raises:
            YouTubeDownloaderError: If workflow type is invalid or execution fails
        """
        self.logger.info(f"Routing workflow: {workflow_type}")
        
        if workflow_type == 'single':
            result = self.download_single_video(url_or_path, config, interactive)
            return [result]
            
        elif workflow_type == 'playlist':
            return self.download_playlist(url_or_path, config, interactive)
            
        elif workflow_type == 'batch':
            return self.download_batch_from_file(url_or_path, config, interactive)
            
        else:
            raise YouTubeDownloaderError(f"Invalid workflow type: {workflow_type}")
    
    def detect_workflow_type(self, input_value: str) -> str:
        """
        Detect workflow type based on input value.
        
        Args:
            input_value: URL or file path
            
        Returns:
            Workflow type ('single', 'playlist', 'batch')
        """
        # Check if it's a file path
        if Path(input_value).exists() and Path(input_value).is_file():
            return 'batch'
        
        # Check if it's a playlist URL
        if 'playlist' in input_value.lower() or 'list=' in input_value.lower():
            return 'playlist'
        
        # Default to single video
        return 'single'
    
    def set_progress_callback(self, callback: callable) -> None:
        """
        Set progress callback for download operations.
        
        Args:
            callback: Function to call with progress updates
        """
        if self.download_manager and hasattr(self.download_manager, 'set_progress_callback'):
            self.download_manager.set_progress_callback(callback)
            self.logger.debug("Progress callback set")
    
    def get_workflow_summary(self, results: List[DownloadResult]) -> Dict[str, Any]:
        """
        Get summary of workflow results.
        
        Args:
            results: List of download results
            
        Returns:
            Dictionary with workflow summary
        """
        return self.workflow_manager.get_workflow_summary(results)
    
    def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        if not hasattr(self, 'logger'):
            return  # Already shut down or not initialized
            
        try:
            self.logger.info("Shutting down YouTube Downloader application")
        except (ValueError, OSError):
            # Logger might be closed, use print instead
            print("Shutting down YouTube Downloader application")
        
        try:
            # Stop any running operations
            if self._is_running:
                try:
                    self.logger.info("Stopping running operations...")
                except (ValueError, OSError):
                    print("Stopping running operations...")
                self._is_running = False
            
            # Clean up download manager resources
            if hasattr(self.download_manager, 'shutdown'):
                self.download_manager.shutdown()
            
            # Reset error counts
            if hasattr(self.error_handler, 'reset_error_counts'):
                self.error_handler.reset_error_counts()
            
            # Final cleanup
            try:
                self.logger.info("Application shutdown complete")
            except (ValueError, OSError):
                print("Application shutdown complete")
            
        except Exception as e:
            # Use print as logger might not be available
            print(f"Error during shutdown: {e}")
    
    def is_running(self) -> bool:
        """Check if application is currently running operations."""
        return self._is_running