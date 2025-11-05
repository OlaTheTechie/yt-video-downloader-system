"""
Main entry point for the YouTube Video Downloader application.
"""

import sys
from cli.main_cli import main as cli_main


def main():
    """Main entry point for the CLI application."""
    try:
        # Run the CLI application
        cli_main()
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())