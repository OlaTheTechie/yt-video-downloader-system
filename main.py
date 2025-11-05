"""
Main entry point for the YouTube Video Downloader application.

This module provides the main entry point for the CLI application,
handling graceful shutdown and cleanup on interruption.
"""

import sys
import signal
from cli.main_cli import main as cli_main
from core.application import YouTubeDownloaderApp


# Global application instance for signal handling
app_instance = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global app_instance
    
    signal_names = {signal.SIGINT: 'SIGINT', signal.SIGTERM: 'SIGTERM'}
    signal_name = signal_names.get(signum, f'Signal {signum}')
    
    print(f"\nReceived {signal_name}, shutting down gracefully...", file=sys.stderr)
    
    if app_instance:
        app_instance.shutdown()
    
    sys.exit(0)


def main():
    """Main entry point for the CLI application."""
    global app_instance
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize application instance for signal handling
        app_instance = YouTubeDownloaderApp()
        
        # Run the CLI application
        cli_main()
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        if app_instance:
            app_instance.shutdown()
        return 1
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        if app_instance:
            app_instance.shutdown()
        return 1
    
    finally:
        # Ensure cleanup
        if app_instance:
            app_instance.shutdown()


if __name__ == "__main__":
    sys.exit(main())