# YouTube Video Downloader

A production-ready command-line application for downloading YouTube videos with advanced features including timestamp-based video splitting, playlist support, and parallel downloads.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/example/youtube-video-downloader)

## Features

- **Single Video Downloads**: Download individual YouTube videos with metadata preservation
- **Playlist Support**: Download entire playlists with proper organization
- **Timestamp Splitting**: Automatically split videos based on timestamps in descriptions
- **Parallel Processing**: Download multiple videos concurrently for faster processing
- **Quality Selection**: Choose from various video qualities (144p to 4K+)
- **Format Options**: Support for multiple video and audio formats
- **Resume Capability**: Resume interrupted downloads automatically
- **Subtitle Support**: Download subtitles in multiple languages and formats
- **Archive Management**: Track downloads and prevent duplicates
- **Batch Processing**: Process multiple URLs from text files
- **Interactive Mode**: Make splitting decisions on a per-video basis
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Requirements

- **Python**: 3.8 or higher
- **FFmpeg**: Required for video splitting functionality
- **Operating System**: Windows, macOS, or Linux
- **Network**: Internet connection for YouTube access
- **Storage**: Minimum 1GB free space (more for video storage)

## Installation

### Method 1: Install from PyPI (Recommended)

```bash
pip install youtube-video-downloader
```

### Method 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/example/youtube-video-downloader.git
cd youtube-video-downloader

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Method 3: Using pipx (Isolated Installation)

```bash
# Install pipx if not already installed
pip install pipx

# Install the application
pipx install youtube-video-downloader
```

### FFmpeg Installation

FFmpeg is required for video splitting functionality:

**Windows:**
```bash
# Using chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
# Using homebrew
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install ffmpeg
# or
sudo dnf install ffmpeg
```

## Quick Start

### Basic Usage

```bash
# Download a single video
youtube-downloader download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download with specific quality
youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" -q 720p

# Download entire playlist
youtube-downloader playlist "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz59Oq8HmPME"

# Download with timestamp splitting
youtube-downloader download "https://youtu.be/dQw4w9WgXcQ" --split-timestamps
```

### Configuration

Generate a default configuration file:

```bash
youtube-downloader init-config
```

This creates `youtube_downloader_config.json` with default settings that you can customize.

## Detailed Usage

### Single Video Downloads

```bash
# Basic download
youtube-downloader download "https://www.youtube.com/watch?v=VIDEO_ID"

# Download to specific directory
youtube-downloader download "https://youtu.be/VIDEO_ID" -o ~/Downloads/Videos

# Download specific quality and format
youtube-downloader download "https://youtu.be/VIDEO_ID" -q 1080p -f mp4

# Download audio only
youtube-downloader download "https://youtu.be/VIDEO_ID" --audio-format mp3

# Download with metadata and thumbnails
youtube-downloader download "https://youtu.be/VIDEO_ID" --metadata --thumbnails

# Download with subtitles
youtube-downloader download "https://youtu.be/VIDEO_ID" --subtitles --subtitle-languages en,es,fr
```

### Timestamp Splitting

The application can automatically detect timestamps in video descriptions and split videos into chapters:

```bash
# Automatic splitting based on timestamps
youtube-downloader download "https://youtu.be/VIDEO_ID" --split-timestamps

# Interactive mode - prompts for each video
youtube-downloader download "https://youtu.be/VIDEO_ID" --interactive
```

**Supported timestamp formats:**
- `0:00 Introduction`
- `[5:30] Chapter 1`
- `1:23:45 - Final thoughts`
- `10:15 Chapter title here`

### Playlist Downloads

```bash
# Download entire playlist
youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Playlist with parallel downloads (faster)
youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" -p 3

# Playlist with timestamp splitting
youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --split-timestamps

# Interactive playlist (decide splitting per video)
youtube-downloader playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID" --interactive
```

### Batch Downloads

Create a text file with URLs (one per line):

```text
# urls.txt
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/another_video_id
https://www.youtube.com/playlist?list=PLAYLIST_ID
# https://youtu.be/commented_out_video
```

Then download:

```bash
# Basic batch download
youtube-downloader batch urls.txt

# Batch with parallel processing
youtube-downloader batch urls.txt -p 5

# Batch with specific quality
youtube-downloader batch urls.txt -q 720p
```

### Archive Management

```bash
# View download statistics
youtube-downloader archive --action stats

# Find duplicate downloads
youtube-downloader archive --action duplicates

# Clean up missing files from archive
youtube-downloader archive --action cleanup

# Export archive data
youtube-downloader archive --action export --export-path backup.json
```

## Configuration Options

### Quality Settings
- `worst`, `best`: Automatic quality selection
- `144p`, `240p`, `360p`, `480p`, `720p`, `1080p`, `1440p`, `2160p`: Specific resolutions

### Format Options
- **Video formats**: `mp4`, `webm`, `mkv`
- **Audio formats**: `mp3`, `m4a`, `ogg`, `wav`
- **Video codecs**: `h264`, `h265`, `vp9`, `av1`
- **Audio codecs**: `aac`, `mp3`, `opus`

### Example Configuration File

```json
{
  "output_directory": "./downloads",
  "quality": "720p",
  "format_preference": "mp4",
  "audio_format": "m4a",
  "split_timestamps": false,
  "max_parallel_downloads": 3,
  "save_thumbnails": true,
  "save_metadata": true,
  "resume_downloads": true,
  "retry_attempts": 3,
  "video_codec": "h264",
  "audio_codec": "aac",
  "subtitles": false,
  "subtitle_languages": ["en"],
  "subtitle_format": "srt",
  "archive_downloads": true
}
```

## Advanced Features

### Custom Configuration

```bash
# Use custom configuration file
youtube-downloader --config my-config.json download "https://youtu.be/VIDEO_ID"

# Validate configuration
youtube-downloader validate-config --config my-config.json
```

### Logging and Debugging

```bash
# Enable debug logging
youtube-downloader --log-level DEBUG download "https://youtu.be/VIDEO_ID"

# Save logs to file
youtube-downloader --log-file download.log download "https://youtu.be/VIDEO_ID"
```

### Performance Tuning

```bash
# Increase parallel downloads for playlists
youtube-downloader playlist "PLAYLIST_URL" -p 5

# Enable resume for large downloads
youtube-downloader download "VIDEO_URL" --resume

# Set retry attempts for unstable connections
youtube-downloader download "VIDEO_URL" --retries 5
```

## Troubleshooting

### Common Issues

#### 1. "FFmpeg not found" Error
**Problem**: Video splitting fails with FFmpeg not found error.

**Solution**:
- Install FFmpeg using your system's package manager
- Ensure FFmpeg is in your system PATH
- Test with: `ffmpeg -version`

#### 2. "Permission denied" Error
**Problem**: Cannot write to output directory.

**Solution**:
```bash
# Check directory permissions
ls -la /path/to/output/directory

# Create directory with proper permissions
mkdir -p ~/Downloads/YouTube && chmod 755 ~/Downloads/YouTube

# Use a different output directory
youtube-downloader download "VIDEO_URL" -o ~/Downloads/YouTube
```

#### 3. "Video unavailable" Error
**Problem**: Video cannot be downloaded due to restrictions.

**Solutions**:
- Check if video is private or deleted
- For geo-restricted content, consider using a VPN
- For age-restricted content, the application will attempt authentication

#### 4. Slow Download Speeds
**Problem**: Downloads are slower than expected.

**Solutions**:
```bash
# Reduce parallel downloads
youtube-downloader download "VIDEO_URL" -p 1

# Use lower quality
youtube-downloader download "VIDEO_URL" -q 480p

# Check network connection and try again later
```

#### 5. Timestamp Detection Issues
**Problem**: Timestamps not detected or splitting fails.

**Solutions**:
- Manually verify timestamp format in video description
- Use interactive mode to manually decide: `--interactive`
- Check FFmpeg installation for splitting functionality

#### 6. Configuration File Issues
**Problem**: Configuration file not loading or invalid.

**Solutions**:
```bash
# Validate configuration
youtube-downloader validate-config

# Generate new default configuration
youtube-downloader init-config -o new-config.json

# Check JSON syntax with online validator
```

### Getting Help

```bash
# General help
youtube-downloader --help

# Command-specific help
youtube-downloader download --help
youtube-downloader playlist --help

# Show comprehensive examples
youtube-downloader help-examples
```

### Debug Information

When reporting issues, please include:

1. **System Information**:
   ```bash
   python --version
   youtube-downloader --version  # If available
   ffmpeg -version
   ```

2. **Error Output**: Run with debug logging:
   ```bash
   youtube-downloader --log-level DEBUG download "VIDEO_URL"
   ```

3. **Configuration**: Your configuration file (remove sensitive information)

4. **URL**: The specific URL that's causing issues (if not private)

## Development

### Setting up Development Environment

```bash
# Clone repository
git clone https://github.com/example/youtube-video-downloader.git
cd youtube-video-downloader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install in development mode
pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8 .

# Type checking
mypy .
```

### Building Distribution

```bash
# Build package
python -m build

# Upload to PyPI (maintainers only)
twine upload dist/*
```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Areas for Contribution

- **Bug fixes**: Help us identify and fix issues
- **Feature requests**: Suggest new functionality
- **Documentation**: Improve documentation and examples
- **Testing**: Add test cases and improve coverage
- **Performance**: Optimize download speeds and resource usage

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **yt-dlp**: Core video downloading functionality
- **Click**: Command-line interface framework
- **FFmpeg**: Video processing and splitting
- **Contributors**: Thanks to all contributors who help improve this project

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Support

- **Documentation**: This README and `youtube-downloader help-examples`
- **Issues**: [GitHub Issues](https://github.com/example/youtube-video-downloader/issues)
- **Discussions**: [GitHub Discussions](https://github.com/example/youtube-video-downloader/discussions)

---

**Note**: This application is for personal use only. Please respect YouTube's Terms of Service and copyright laws. Do not use this tool to download copyrighted content without permission.