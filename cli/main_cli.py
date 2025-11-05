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
from config.error_handling import ConfigurationError, ValidationError, YouTubeDownloaderError
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
    """
    YouTube Video Downloader - Download videos with advanced features.
    
    A production-ready command-line application for downloading YouTube videos
    with advanced features including timestamp-based video splitting, playlist
    support, and parallel downloads.
    
    \b
    EXAMPLES:
    
    Download a single video:
        youtube-downloader download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    Download with specific quality and format:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" -q 720p -f mp4
    
    Download with timestamp splitting:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --split-timestamps
    
    Download entire playlist:
        youtube-downloader playlist "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq8HmPME"
    
    Download from batch file:
        youtube-downloader batch urls.txt
    
    Interactive mode with splitting decisions:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --interactive
    
    \b
    CONFIGURATION:
    
    Generate default configuration file:
        youtube-downloader init-config
    
    Use custom configuration:
        youtube-downloader --config my-config.json download "https://youtu.be/dQw4w9WgXcQ"
    
    Validate configuration:
        youtube-downloader validate-config
    
    \b
    ARCHIVE MANAGEMENT:
    
    View archive statistics:
        youtube-downloader archive --action stats
    
    Find duplicate downloads:
        youtube-downloader archive --action duplicates
    
    Clean up missing files:
        youtube-downloader archive --action cleanup
    
    For more information on each command, use:
        youtube-downloader COMMAND --help
    """
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
        click.echo("\n" + "="*60)
        click.echo("QUICK START:")
        click.echo("  1. Download a single video:")
        click.echo('     youtube-downloader download "https://www.youtube.com/watch?v=VIDEO_ID"')
        click.echo("  2. Download a playlist:")
        click.echo('     youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"')
        click.echo("  3. Create configuration file:")
        click.echo("     youtube-downloader init-config")
        click.echo("="*60)


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
@click.option('--subtitles/--no-subtitles',
              default=None,
              help='Download video subtitles')
@click.option('--subtitle-languages',
              default=None,
              help='Comma-separated list of subtitle languages (e.g., en,es,fr)')
@click.option('--subtitle-format',
              type=click.Choice(['srt', 'vtt', 'ass', 'ttml']),
              help='Subtitle format preference')
@click.option('--auto-subs/--no-auto-subs',
              default=None,
              help='Include auto-generated subtitles')
@click.option('--archive/--no-archive',
              default=None,
              help='Use download archive to track downloads')
@click.option('--skip-duplicates/--no-skip-duplicates',
              default=None,
              help='Skip videos that are already in the archive')
@click.option('--interactive/--no-interactive',
              default=False,
              help='Enable interactive mode for timestamp splitting decisions')
@click.pass_context
def download(ctx, url, interactive, **kwargs):
    """
    Download a single YouTube video.
    
    \b
    EXAMPLES:
    
    Basic download:
        youtube-downloader download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    Download with specific quality and format:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" -q 720p -f mp4
    
    Download with timestamp splitting:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --split-timestamps
    
    Interactive mode (prompts for splitting):
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --interactive
    
    Download with subtitles:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --subtitles --subtitle-languages en,es
    
    Audio-only download:
        youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --audio-format mp3
    """
    try:
        # Import application controller
        from core.application import YouTubeDownloaderApp
        
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Process CLI arguments
        cli_args = _process_cli_args(kwargs)
        
        # Initialize application
        app = YouTubeDownloaderApp()
        
        # Load and merge configuration
        final_config = app.load_configuration(cli_args=cli_args)
        if base_config:
            # Merge with base config from context
            final_config = app.config_manager.merge_cli_args(base_config, cli_args)
        
        # Validate URL
        if not _is_valid_youtube_url(url):
            cli_app.display_error("Invalid YouTube URL provided")
            sys.exit(1)
        
        # Set up progress callback
        def progress_callback(progress: ProgressInfo):
            cli_app.display_progress(progress)
        
        app.set_progress_callback(progress_callback)
        
        cli_app.display_success("Starting single video download...")
        click.echo(f"URL: {url}")
        click.echo(f"Output directory: {final_config.output_directory}")
        click.echo(f"Quality: {final_config.quality}")
        click.echo(f"Format: {final_config.format_preference}")
        
        # Perform download
        result = app.download_single_video(url, final_config, interactive=interactive)
        
        # Display results
        if result.success:
            cli_app.display_success(f"Download completed successfully!")
            click.echo(f"Video saved to: {result.video_path}")
            
            if result.split_files:
                click.echo(f"Video split into {len(result.split_files)} chapters")
            
            if result.metadata_path:
                click.echo(f"Metadata saved to: {result.metadata_path}")
            
            if result.thumbnail_path:
                click.echo(f"Thumbnail saved to: {result.thumbnail_path}")
        else:
            cli_app.display_error(f"Download failed: {result.error_message}")
            sys.exit(1)
        
    except (ConfigurationError, ValidationError) as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    except YouTubeDownloaderError as e:
        cli_app.display_error(f"Download error: {e.message}")
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
@click.option('--subtitles/--no-subtitles',
              default=None,
              help='Download video subtitles')
@click.option('--subtitle-languages',
              default=None,
              help='Comma-separated list of subtitle languages (e.g., en,es,fr)')
@click.option('--subtitle-format',
              type=click.Choice(['srt', 'vtt', 'ass', 'ttml']),
              help='Subtitle format preference')
@click.option('--archive/--no-archive',
              default=None,
              help='Use download archive to track downloads')
@click.option('--skip-duplicates/--no-skip-duplicates',
              default=None,
              help='Skip videos that are already in the archive')
@click.option('--interactive/--no-interactive',
              default=False,
              help='Enable interactive mode for timestamp splitting decisions')
@click.pass_context
def playlist(ctx, playlist_url, interactive, **kwargs):
    """
    Download an entire YouTube playlist.
    
    \b
    EXAMPLES:
    
    Basic playlist download:
        youtube-downloader playlist "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq8HmPME"
    
    Playlist with parallel downloads:
        youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" -p 3
    
    Playlist with timestamp splitting:
        youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --split-timestamps
    
    Interactive playlist (per-video splitting decisions):
        youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --interactive
    """
    try:
        # Import application controller
        from core.application import YouTubeDownloaderApp
        
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Process CLI arguments
        cli_args = _process_cli_args(kwargs)
        
        # Initialize application
        app = YouTubeDownloaderApp()
        
        # Load and merge configuration
        final_config = app.load_configuration(cli_args=cli_args)
        if base_config:
            # Merge with base config from context
            final_config = app.config_manager.merge_cli_args(base_config, cli_args)
        
        # Validate playlist URL
        if not _is_valid_youtube_playlist_url(playlist_url):
            cli_app.display_error("Invalid YouTube playlist URL provided")
            sys.exit(1)
        
        # Set up progress callback
        def progress_callback(progress: ProgressInfo):
            cli_app.display_progress(progress)
        
        app.set_progress_callback(progress_callback)
        
        cli_app.display_success("Starting playlist download...")
        click.echo(f"Playlist URL: {playlist_url}")
        click.echo(f"Output directory: {final_config.output_directory}")
        click.echo(f"Parallel downloads: {final_config.max_parallel_downloads}")
        
        # Perform playlist download
        results = app.download_playlist(playlist_url, final_config, interactive=interactive)
        
        # Display results summary
        summary = app.get_workflow_summary(results)
        
        click.echo(f"\nPlaylist download completed!")
        click.echo(f"Total downloads: {summary['total_downloads']}")
        click.echo(f"Successful: {summary['successful_downloads']}")
        click.echo(f"Failed: {summary['failed_downloads']}")
        
        if summary['videos_with_splits'] > 0:
            click.echo(f"Videos split into chapters: {summary['videos_with_splits']}")
            click.echo(f"Total split files created: {summary['total_split_files']}")
        
        if summary['successful_downloads'] > 0:
            click.echo(f"Total download time: {summary['total_download_time']:.1f} seconds")
            click.echo(f"Average time per download: {summary['average_download_time']:.1f} seconds")
        
        # Exit with error code if any downloads failed
        if summary['failed_downloads'] > 0:
            sys.exit(1)
        
    except (ConfigurationError, ValidationError) as e:
        cli_app.display_error(f"Configuration error: {e.message}")
        sys.exit(1)
    except YouTubeDownloaderError as e:
        cli_app.display_error(f"Download error: {e.message}")
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
    """
    Download videos from a batch file containing URLs.
    
    The batch file should contain one URL per line. Lines starting with # are
    treated as comments and ignored. Empty lines are also ignored.
    
    \b
    BATCH FILE FORMAT:
    
    # YouTube Video Downloader Batch File
    # One URL per line, comments start with #
    
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://youtu.be/another_video_id
    https://www.youtube.com/playlist?list=PLAYLIST_ID
    # https://youtu.be/commented_out_video
    
    \b
    EXAMPLES:
    
    Basic batch download:
        youtube-downloader batch urls.txt
    
    Batch with parallel processing:
        youtube-downloader batch urls.txt -p 5
    
    Batch with specific quality:
        youtube-downloader batch urls.txt -q 720p
    """
    try:
        # Get base configuration
        base_config = ctx.obj['config']
        
        # Process CLI arguments
        cli_args = _process_cli_args(kwargs)
        
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
        
        # Import application controller
        from core.application import YouTubeDownloaderApp
        
        # Initialize application
        app = YouTubeDownloaderApp()
        
        # Set up progress callback
        def progress_callback(progress: ProgressInfo):
            if progress.total_files > 1:
                click.echo(f"Progress: {progress.files_completed}/{progress.total_files} files completed")
        
        app.set_progress_callback(progress_callback)
        
        # Start batch download
        click.echo(f"\nStarting batch download...")
        results = app.download_batch_from_file(str(batch_file), final_config, interactive=False)
        
        # Display results summary
        summary = app.get_workflow_summary(results)
        
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
@click.option('--archive-dir', '-d',
              type=click.Path(path_type=Path),
              default='./downloads',
              help='Directory containing the download archive')
@click.option('--action',
              type=click.Choice(['stats', 'duplicates', 'cleanup', 'export']),
              required=True,
              help='Archive management action to perform')
@click.option('--export-path',
              type=click.Path(path_type=Path),
              help='Path for archive export (required for export action)')
@click.pass_context
def archive(ctx, archive_dir, action, export_path):
    """Manage download archive and detect duplicates."""
    try:
        from services.archive_manager import ArchiveManager
        
        archive_manager = ArchiveManager(str(archive_dir))
        
        if action == 'stats':
            stats = archive_manager.get_archive_stats()
            click.echo("Archive Statistics:")
            click.echo(f"Total downloads: {stats.get('total_downloads', 0)}")
            click.echo(f"Total size: {stats.get('total_size', 0) / (1024**3):.2f} GB")
            
            if 'first_download' in stats:
                click.echo(f"First download: {stats['first_download']}")
            if 'last_download' in stats:
                click.echo(f"Last download: {stats['last_download']}")
            
            if 'total_duration_hours' in stats:
                click.echo(f"Total duration: {stats['total_duration_hours']:.1f} hours")
            
            if 'top_uploaders' in stats:
                click.echo("\nTop uploaders:")
                for uploader, count in stats['top_uploaders'][:5]:
                    click.echo(f"  {uploader}: {count} videos")
        
        elif action == 'duplicates':
            content_duplicates = archive_manager.find_duplicates_by_content()
            title_duplicates = archive_manager.find_duplicates_by_title()
            
            click.echo(f"Found {len(content_duplicates)} groups of content duplicates")
            click.echo(f"Found {len(title_duplicates)} groups of title duplicates")
            
            if content_duplicates:
                click.echo("\nContent duplicates:")
                for i, group in enumerate(content_duplicates[:5], 1):
                    click.echo(f"  Group {i}:")
                    for record in group:
                        click.echo(f"    - {record.get('title', 'Unknown')} ({record.get('video_id', 'Unknown')})")
        
        elif action == 'cleanup':
            removed_ids = archive_manager.cleanup_missing_files()
            click.echo(f"Cleaned up {len(removed_ids)} missing file records")
            
            if removed_ids:
                click.echo("Removed records:")
                for video_id in removed_ids[:10]:  # Show first 10
                    click.echo(f"  - {video_id}")
                if len(removed_ids) > 10:
                    click.echo(f"  ... and {len(removed_ids) - 10} more")
        
        elif action == 'export':
            if not export_path:
                click.echo("Error: --export-path is required for export action")
                sys.exit(1)
            
            archive_manager.export_archive(str(export_path))
            click.echo(f"Archive exported to: {export_path}")
        
    except Exception as e:
        click.echo(f"Error managing archive: {e}")
        sys.exit(1)


@main.command()
def help_examples():
    """Show comprehensive usage examples and tips."""
    examples = """
YouTube Video Downloader - Comprehensive Usage Examples

═══════════════════════════════════════════════════════════════════════════════

BASIC DOWNLOADS:

  Single video download:
    youtube-downloader download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

  Download to specific directory:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" -o ~/Downloads/Videos

  Download specific quality:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" -q 720p

  Download audio only:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --audio-format mp3

═══════════════════════════════════════════════════════════════════════════════

ADVANCED FEATURES:

  Download with timestamp splitting:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --split-timestamps

  Interactive mode (prompts for splitting decisions):
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --interactive

  Download with subtitles:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --subtitles --subtitle-languages en,es

  Download with metadata and thumbnails:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --metadata --thumbnails

═══════════════════════════════════════════════════════════════════════════════

PLAYLIST DOWNLOADS:

  Download entire playlist:
    youtube-downloader playlist "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq8HmPME"

  Playlist with parallel downloads:
    youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" -p 3

  Playlist with splitting options:
    youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --split-timestamps

═══════════════════════════════════════════════════════════════════════════════

BATCH DOWNLOADS:

  Create batch file (urls.txt):
    # One URL per line, comments start with #
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://youtu.be/another_video_id
    # https://youtu.be/commented_out_video

  Download from batch file:
    youtube-downloader batch urls.txt

  Batch download with parallel processing:
    youtube-downloader batch urls.txt -p 5

═══════════════════════════════════════════════════════════════════════════════

CONFIGURATION:

  Generate default configuration:
    youtube-downloader init-config

  Generate config in specific location:
    youtube-downloader init-config -o ~/my-config.json

  Use custom configuration:
    youtube-downloader --config ~/my-config.json download "https://youtu.be/dQw4w9WgXcQ"

  Validate configuration:
    youtube-downloader validate-config

═══════════════════════════════════════════════════════════════════════════════

ARCHIVE MANAGEMENT:

  View download statistics:
    youtube-downloader archive --action stats

  Find duplicate downloads:
    youtube-downloader archive --action duplicates

  Clean up missing files from archive:
    youtube-downloader archive --action cleanup

  Export archive data:
    youtube-downloader archive --action export --export-path archive-backup.json

═══════════════════════════════════════════════════════════════════════════════

QUALITY AND FORMAT OPTIONS:

  Quality options: worst, best, 144p, 240p, 360p, 480p, 720p, 1080p, 1440p, 2160p
  Video formats: mp4, webm, mkv
  Audio formats: mp3, m4a, ogg, wav
  Video codecs: h264, h265, vp9, av1
  Audio codecs: aac, mp3, opus

  Example with specific codec preferences:
    youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --video-codec h264 --audio-codec aac

═══════════════════════════════════════════════════════════════════════════════

LOGGING AND DEBUGGING:

  Enable debug logging:
    youtube-downloader --log-level DEBUG download "https://youtu.be/dQw4w9WgXcQ"

  Save logs to file:
    youtube-downloader --log-file download.log download "https://youtu.be/dQw4w9WgXcQ"

═══════════════════════════════════════════════════════════════════════════════

TIPS:

  • Use quotes around URLs to avoid shell interpretation issues
  • The --interactive flag is useful for deciding splitting on a per-video basis
  • Parallel downloads (-p) can speed up playlist/batch downloads significantly
  • Use --archive to avoid re-downloading the same videos
  • Configuration files allow you to set default preferences
  • Check logs if downloads fail - they contain detailed error information

For detailed help on any command, use:
  youtube-downloader COMMAND --help

═══════════════════════════════════════════════════════════════════════════════
"""
    click.echo(examples)


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


def _process_cli_args(cli_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process CLI arguments to handle Path objects and other conversions.
    
    Args:
        cli_args: Raw CLI arguments
        
    Returns:
        Processed CLI arguments
    """
    processed_args = {}
    
    for key, value in cli_args.items():
        if value is None:
            continue
            
        # Convert Path objects to strings
        if key == 'output' and value is not None:
            processed_args['output_directory'] = str(value)
        elif isinstance(value, Path):
            processed_args[key] = str(value)
        else:
            processed_args[key] = value
    
    # Process subtitle languages if provided
    if 'subtitle_languages' in processed_args and processed_args['subtitle_languages']:
        processed_args['subtitle_languages'] = [
            lang.strip() for lang in processed_args['subtitle_languages'].split(',')
        ]
    
    return processed_args


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