"""
Main CLI implementation using Click framework for the YouTube Video Downloader.
"""

import click
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from models.core import DownloadConfig, ProgressInfo
from config import ConfigManager, setup_logging, get_logger
from config.error_handling import ConfigurationError, ValidationError
from cli.interfaces import CLIInterface


class YouTubeDownloaderCLI(CLIInterface):
    """Main CLI application class using Click framework."""
    
    def __init__(self):
        """Initialize CLI application."""
        self.config_manager = ConfigManager()
        self.logger = get_logger(__name__)
    
    def parse_arguments(self, args: List[str]) -> DownloadConfig:
        """Parse command-line arguments and return configuration."""
        # This method is implemented through Click decorators
        # It's here to satisfy the interface but actual parsing happens in CLI commands
        pass
    
    def display_progress(self, progress: ProgressInfo) -> None:
        """Display progress information to the user."""
        if progress.total_files > 1:
            file_progress = f"[{progress.files_completed}/{progress.total_files}] "
        else:
            file_progress = ""
        
        click.echo(
            f"{file_progress}{progress.current_file}: "
            f"{progress.progress_percent:.1f}% "
            f"({progress.download_speed}) "
            f"ETA: {progress.eta}",
            nl=False
        )
        click.echo("\r", nl=False)  # Carriage return for overwriting
    
    def handle_user_prompts(self, prompt: str) -> str:
        """Handle user prompts and return user input."""
        return click.prompt(prompt)
    
    def display_error(self, error_message: str) -> None:
        """Display error message to the user."""
        click.echo(click.style(f"Error: {error_message}", fg='red'), err=True)
    
    def display_success(self, message: str) -> None:
        """Display success message to the user."""
        click.echo(click.style(message, fg='green'))


# Global CLI instance
cli_app = YouTubeDownloaderCLI()


@click.group(invoke_without_command=True)
@click.option('--config', '-c', 
              type=click.Path(exists=True, path_type=Path),
              help='Path to configuration file')
@click.option('--log-level', 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              default='INFO',
              help='Set logging level')
@click.option('--log-file',
              type=click.Path(path_type=Path),
              help='Path to log file')
@click.pass_context
def main(ctx, config, log_level, log_file):
    """YouTube Video Downloader - Download videos with advanced features."""
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Setup logging
    setup_logging(
        log_level=log_level,
        log_file=str(log_file) if log_file else None
    )
    
    # Load configuration
    try:
        if config:
            ctx.obj['config'] = cli_app.config_manager.load_config(config)
        else:
            # Try to load default config
            default_config_path = cli_app.config_manager.get_config_path()
            ctx.obj['config'] = cli_app.config_manager.load_config(default_config_path)
    except ConfigurationError as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    
    # If no command is specified, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument('url')
@click.option('--output', '-o',
              type=click.Path(path_type=Path),
              help='Output directory for downloaded files')
@click.option('--quality', '-q',
              type=click.Choice(['worst', 'best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p']),
              help='Video quality to download')
@click.option('--format', '-f',
              type=click.Choice(['mp4', 'webm', 'mkv']),
              help='Video format preference')
@click.option('--audio-format',
              type=click.Choice(['mp3', 'm4a', 'ogg', 'wav']),
              help='Audio format for audio-only downloads')
@click.option('--split-timestamps/--no-split-timestamps',
              default=None,
              help='Split video based on timestamps in description')
@click.option('--parallel', '-p',
              type=click.IntRange(1, 10),
              help='Number of parallel downloads (1-10)')
@click.option('--thumbnails/--no-thumbnails',
              default=None,
              help='Download video thumbnails')
@click.option('--metadata/--no-metadata',
              default=None,
              help='Save video metadata')
@click.option('--resume/--no-resume',
              default=None,
              help='Resume interrupted downloads')
@click.option('--retries',
              type=click.IntRange(0, 10),
              help='Number of retry attempts (0-10)')
@click.option('--video-codec',
              type=click.Choice(['h264', 'h265', 'vp9', 'av1']),
              help='Preferred video codec')
@click.option('--audio-codec',
              type=click.Choice(['aac', 'mp3', 'opus']),
              help='Preferred audio codec')
@click.option('--container',
              type=click.Choice(['mp4', 'webm', 'mkv']),
              help='Preferred container format')
@click.pass_context
def download(ctx, url, **kwargs):
    """Download a single YouTube video."""
    try:
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Filter out None values from CLI arguments
        cli_args = {k: v for k, v in kwargs.items() if v is not None}
        
        # Merge CLI arguments with configuration
        final_config = cli_app.config_manager.merge_cli_args(base_config, cli_args)
        
        # Validate URL
        if not _is_valid_youtube_url(url):
            cli_app.display_error("Invalid YouTube URL provided")
            sys.exit(1)
        
        cli_app.display_success(f"Configuration loaded successfully")
        click.echo(f"URL: {url}")
        click.echo(f"Output directory: {final_config.output_directory}")
        click.echo(f"Quality: {final_config.quality}")
        click.echo(f"Format: {final_config.format_preference}")
        
        # TODO: Implement actual download logic in future tasks
        click.echo("Download functionality will be implemented in future tasks.")
        
    except (ConfigurationError, ValidationError) as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    except Exception as e:
        cli_app.display_error(f"Unexpected error: {str(e)}")
        sys.exit(1)


@main.command()
@click.argument('playlist_url')
@click.option('--output', '-o',
              type=click.Path(path_type=Path),
              help='Output directory for downloaded files')
@click.option('--quality', '-q',
              type=click.Choice(['worst', 'best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p']),
              help='Video quality to download')
@click.option('--format', '-f',
              type=click.Choice(['mp4', 'webm', 'mkv']),
              help='Video format preference')
@click.option('--parallel', '-p',
              type=click.IntRange(1, 10),
              help='Number of parallel downloads (1-10)')
@click.option('--split-timestamps/--no-split-timestamps',
              default=None,
              help='Split videos based on timestamps in descriptions')
@click.option('--thumbnails/--no-thumbnails',
              default=None,
              help='Download video thumbnails')
@click.option('--metadata/--no-metadata',
              default=None,
              help='Save video metadata')
@click.pass_context
def playlist(ctx, playlist_url, **kwargs):
    """Download an entire YouTube playlist."""
    try:
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Filter out None values from CLI arguments
        cli_args = {k: v for k, v in kwargs.items() if v is not None}
        
        # Merge CLI arguments with configuration
        final_config = cli_app.config_manager.merge_cli_args(base_config, cli_args)
        
        # Validate playlist URL
        if not _is_valid_youtube_playlist_url(playlist_url):
            cli_app.display_error("Invalid YouTube playlist URL provided")
            sys.exit(1)
        
        cli_app.display_success(f"Playlist download configuration loaded")
        click.echo(f"Playlist URL: {playlist_url}")
        click.echo(f"Output directory: {final_config.output_directory}")
        click.echo(f"Parallel downloads: {final_config.max_parallel_downloads}")
        
        # TODO: Implement actual playlist download logic in future tasks
        click.echo("Playlist download functionality will be implemented in future tasks.")
        
    except (ConfigurationError, ValidationError) as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    except Exception as e:
        cli_app.display_error(f"Unexpected error: {str(e)}")
        sys.exit(1)


@main.command()
@click.argument('batch_file', type=click.Path(exists=True, path_type=Path))
@click.option('--output', '-o',
              type=click.Path(path_type=Path),
              help='Output directory for downloaded files')
@click.option('--quality', '-q',
              type=click.Choice(['worst', 'best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p']),
              help='Video quality to download')
@click.option('--parallel', '-p',
              type=click.IntRange(1, 10),
              help='Number of parallel downloads (1-10)')
@click.pass_context
def batch(ctx, batch_file, **kwargs):
    """Download videos from a batch file containing URLs."""
    try:
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Filter out None values from CLI arguments
        cli_args = {k: v for k, v in kwargs.items() if v is not None}
        
        # Merge CLI arguments with configuration
        final_config = cli_app.config_manager.merge_cli_args(base_config, cli_args)
        
        # Read and validate batch file
        urls = _read_batch_file(batch_file)
        if not urls:
            cli_app.display_error("No valid URLs found in batch file")
            sys.exit(1)
        
        cli_app.display_success(f"Batch download configuration loaded")
        click.echo(f"Batch file: {batch_file}")
        click.echo(f"URLs found: {len(urls)}")
        click.echo(f"Output directory: {final_config.output_directory}")
        
        # Import workflow manager
        from services.workflow_manager import WorkflowManager
        
        # Initialize workflow manager
        workflow_manager = WorkflowManager()
        
        # Set up progress callback
        def progress_callback(progress: ProgressInfo):
            if progress.total_files > 1:
                click.echo(f"Progress: {progress.files_completed}/{progress.total_files} files completed")
        
        workflow_manager.download_manager.set_progress_callback(progress_callback)
        
        # Start batch download
        click.echo(f"\nStarting batch download...")
        results = workflow_manager.download_batch_from_file(str(batch_file), final_config, interactive=False)
        
        # Display results summary
        summary = workflow_manager.get_workflow_summary(results)
        
        click.echo(f"\nBatch download completed!")
        click.echo(f"Total downloads: {summary['total_downloads']}")
        click.echo(f"Successful: {summary['successful_downloads']}")
        click.echo(f"Failed: {summary['failed_downloads']}")
        
        if summary['videos_with_splits'] > 0:
            click.echo(f"Videos split into chapters: {summary['videos_with_splits']}")
            click.echo(f"Total split files created: {summary['total_split_files']}")
        
        if summary['successful_downloads'] > 0:
            click.echo(f"Total download time: {summary['total_download_time']:.1f} seconds")
            click.echo(f"Average time per download: {summary['average_download_time']:.1f} seconds")
        
    except (ConfigurationError, ValidationError) as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    except Exception as e:
        cli_app.display_error(f"Unexpected error: {str(e)}")
        sys.exit(1)


@main.command()
@click.option('--output', '-o',
              type=click.Path(path_type=Path),
              default='./youtube_downloader_config.json',
              help='Output path for configuration file')
def init_config(output):
    """Generate a default configuration file."""
    try:
        cli_app.config_manager.save_default_config(output)
        cli_app.display_success(f"Default configuration saved to: {output}")
        click.echo("You can now edit this file to customize your settings.")
        
    except ConfigurationError as e:
        cli_app.display_error(f"Failed to create configuration file: {e.message}")
        sys.exit(1)


@main.command()
@click.option('--config', '-c',
              type=click.Path(exists=True, path_type=Path),
              help='Path to configuration file to validate')
def validate_config(config):
    """Validate a configuration file."""
    try:
        if not config:
            config = cli_app.config_manager.get_config_path()
        
        # Try to load the configuration
        loaded_config = cli_app.config_manager.load_config(config)
        cli_app.display_success(f"Configuration file is valid: {config}")
        
        # Display configuration summary
        click.echo("\nConfiguration Summary:")
        click.echo(f"  Output Directory: {loaded_config.output_directory}")
        click.echo(f"  Quality: {loaded_config.quality}")
        click.echo(f"  Format: {loaded_config.format_preference}")
        click.echo(f"  Parallel Downloads: {loaded_config.max_parallel_downloads}")
        click.echo(f"  Split Timestamps: {loaded_config.split_timestamps}")
        click.echo(f"  Save Thumbnails: {loaded_config.save_thumbnails}")
        click.echo(f"  Save Metadata: {loaded_config.save_metadata}")
        
    except ConfigurationError as e:
        cli_app.display_error(f"Configuration validation failed: {e.message}")
        sys.exit(1)


def _is_valid_youtube_url(url: str) -> bool:
    """
    Validate if URL is a valid YouTube video URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid YouTube URL, False otherwise
    """
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
    return any(domain in url.lower() for domain in youtube_domains)


def _is_valid_youtube_playlist_url(url: str) -> bool:
    """
    Validate if URL is a valid YouTube playlist URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid YouTube playlist URL, False otherwise
    """
    return _is_valid_youtube_url(url) and ('playlist' in url.lower() or 'list=' in url.lower())


def _read_batch_file(file_path: Path) -> List[str]:
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
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    if _is_valid_youtube_url(line):
                        urls.append(line)
                    else:
                        click.echo(f"Warning: Invalid URL on line {line_num}: {line}", err=True)
    except Exception as e:
        raise ConfigurationError(f"Failed to read batch file {file_path}: {str(e)}")
    
    return urls


if __name__ == '__main__':
    main()