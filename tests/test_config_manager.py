"""
Unit tests for ConfigManager class.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from config.config_manager import ConfigManager
from config.error_handling import ConfigurationError, ValidationError
from models.core import DownloadConfig, FormatPreferences


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_default_config(self):
        """Test default configuration creation."""
        default_config = self.config_manager._create_default_config()
        
        assert isinstance(default_config, dict)
        assert 'output_directory' in default_config
        assert 'quality' in default_config
        assert 'format_preference' in default_config
        assert 'max_parallel_downloads' in default_config
        assert 'format_preferences' in default_config
        
        # Check default values
        assert default_config['output_directory'] == './downloads'
        assert default_config['quality'] == 'best'
        assert default_config['format_preference'] == 'mp4'
        assert default_config['max_parallel_downloads'] == 3
    
    def test_load_config_nonexistent_file(self):
        """Test loading configuration from non-existent file."""
        non_existent_path = self.temp_path / "nonexistent.json"
        
        config = self.config_manager.load_config(non_existent_path)
        
        assert isinstance(config, DownloadConfig)
        assert config.output_directory == './downloads'
        assert config.quality == 'best'
    
    def test_load_config_valid_file(self):
        """Test loading configuration from valid JSON file."""
        config_data = {
            "output_directory": "/custom/path",
            "quality": "720p",
            "format_preference": "webm",
            "max_parallel_downloads": 5
        }
        
        config_file = self.temp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = self.config_manager.load_config(config_file)
        
        assert config.output_directory == "/custom/path"
        assert config.quality == "720p"
        assert config.format_preference == "webm"
        assert config.max_parallel_downloads == 5
    
    def test_load_config_invalid_json(self):
        """Test loading configuration from invalid JSON file."""
        config_file = self.temp_path / "invalid.json"
        with open(config_file, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager.load_config(config_file)
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_save_config(self):
        """Test saving configuration to file."""
        config = DownloadConfig(
            output_directory="/test/path",
            quality="1080p",
            format_preference="mp4",
            max_parallel_downloads=4
        )
        
        config_file = self.temp_path / "saved_config.json"
        self.config_manager.save_config(config, config_file)
        
        assert config_file.exists()
        
        # Verify saved content
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['output_directory'] == "/test/path"
        assert saved_data['quality'] == "1080p"
        assert saved_data['max_parallel_downloads'] == 4
    
    def test_save_default_config(self):
        """Test saving default configuration."""
        config_file = self.temp_path / "default_config.json"
        self.config_manager.save_default_config(config_file)
        
        assert config_file.exists()
        
        # Verify content matches default
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        default_config = self.config_manager._create_default_config()
        assert saved_data == default_config
    
    def test_merge_cli_args(self):
        """Test merging CLI arguments with configuration."""
        base_config = DownloadConfig(
            output_directory="./downloads",
            quality="best",
            max_parallel_downloads=3
        )
        
        cli_args = {
            'output': '/new/path',
            'quality': '720p',
            'parallel': 5,
            'video_codec': 'h265'
        }
        
        merged_config = self.config_manager.merge_cli_args(base_config, cli_args)
        
        assert merged_config.output_directory == '/new/path'
        assert merged_config.quality == '720p'
        assert merged_config.max_parallel_downloads == 5
        assert merged_config.format_preferences.video_codec == 'h265'
    
    def test_merge_cli_args_none_values(self):
        """Test merging CLI arguments with None values."""
        base_config = DownloadConfig(
            output_directory="./downloads",
            quality="best"
        )
        
        cli_args = {
            'output': '/new/path',
            'quality': None,  # Should not override
            'parallel': None  # Should not override
        }
        
        merged_config = self.config_manager.merge_cli_args(base_config, cli_args)
        
        assert merged_config.output_directory == '/new/path'
        assert merged_config.quality == 'best'  # Not overridden
        assert merged_config.max_parallel_downloads == 3  # Not overridden
    
    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        valid_config = {
            'output_directory': './downloads',
            'quality': 'best',
            'format_preference': 'mp4',
            'audio_format': 'mp3',
            'split_timestamps': False,
            'max_parallel_downloads': 3,
            'save_thumbnails': True,
            'save_metadata': True,
            'resume_downloads': True,
            'retry_attempts': 3,
            'download_subtitles': False,
            'subtitle_languages': ['en'],
            'subtitle_format': 'srt',
            'auto_generated_subtitles': True,
            'use_archive': True,
            'skip_duplicates': True
        }
        
        # Should not raise any exception
        self.config_manager._validate_config(valid_config)
    
    def test_validate_config_missing_field(self):
        """Test configuration validation with missing required field."""
        invalid_config = {
            'output_directory': './downloads',
            # Missing 'quality' field
            'format_preference': 'mp4'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.config_manager._validate_config(invalid_config)
        
        assert "Missing required configuration field: quality" in str(exc_info.value)
    
    def test_validate_config_invalid_parallel_downloads(self):
        """Test configuration validation with invalid parallel downloads."""
        invalid_config = {
            'output_directory': './downloads',
            'quality': 'best',
            'format_preference': 'mp4',
            'audio_format': 'mp3',
            'split_timestamps': False,
            'max_parallel_downloads': 0,  # Invalid: must be positive
            'save_thumbnails': True,
            'save_metadata': True,
            'resume_downloads': True,
            'retry_attempts': 3,
            'download_subtitles': False,
            'subtitle_languages': ['en'],
            'subtitle_format': 'srt',
            'auto_generated_subtitles': True,
            'use_archive': True,
            'skip_duplicates': True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.config_manager._validate_config(invalid_config)
        
        assert "max_parallel_downloads must be a positive integer" in str(exc_info.value)
    
    def test_validate_config_invalid_retry_attempts(self):
        """Test configuration validation with invalid retry attempts."""
        invalid_config = {
            'output_directory': './downloads',
            'quality': 'best',
            'format_preference': 'mp4',
            'audio_format': 'mp3',
            'split_timestamps': False,
            'max_parallel_downloads': 3,
            'save_thumbnails': True,
            'save_metadata': True,
            'resume_downloads': True,
            'retry_attempts': -1,  # Invalid: must be non-negative
            'download_subtitles': False,
            'subtitle_languages': ['en'],
            'subtitle_format': 'srt',
            'auto_generated_subtitles': True,
            'use_archive': True,
            'skip_duplicates': True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.config_manager._validate_config(invalid_config)
        
        assert "retry_attempts must be a non-negative integer" in str(exc_info.value)
    
    def test_merge_configs(self):
        """Test merging two configuration dictionaries."""
        base_config = {
            'output_directory': './downloads',
            'quality': 'best',
            'format_preferences': {
                'video_codec': 'h264',
                'audio_codec': 'aac'
            }
        }
        
        override_config = {
            'quality': '720p',
            'format_preferences': {
                'video_codec': 'h265'
                # audio_codec should remain 'aac'
            },
            'new_field': 'new_value'
        }
        
        merged = self.config_manager._merge_configs(base_config, override_config)
        
        assert merged['output_directory'] == './downloads'
        assert merged['quality'] == '720p'
        assert merged['format_preferences']['video_codec'] == 'h265'
        assert merged['format_preferences']['audio_codec'] == 'aac'
        assert merged['new_field'] == 'new_value'
    
    def test_create_download_config(self):
        """Test creating DownloadConfig from dictionary."""
        config_dict = {
            'output_directory': '/test/path',
            'quality': '1080p',
            'format_preference': 'webm',
            'audio_format': 'm4a',
            'split_timestamps': True,
            'max_parallel_downloads': 5,
            'save_thumbnails': False,
            'save_metadata': True,
            'resume_downloads': False,
            'retry_attempts': 2,
            'download_subtitles': True,
            'subtitle_languages': ['en', 'es'],
            'subtitle_format': 'vtt',
            'auto_generated_subtitles': False,
            'use_archive': False,
            'skip_duplicates': False,
            'format_preferences': {
                'video_codec': 'vp9',
                'audio_codec': 'opus',
                'container': 'webm',
                'prefer_free_formats': True
            }
        }
        
        config = self.config_manager._create_download_config(config_dict)
        
        assert isinstance(config, DownloadConfig)
        assert config.output_directory == '/test/path'
        assert config.quality == '1080p'
        assert config.format_preference == 'webm'
        assert config.split_timestamps is True
        assert config.max_parallel_downloads == 5
        assert config.download_subtitles is True
        assert config.subtitle_languages == ['en', 'es']
        assert config.subtitle_format == 'vtt'
        assert config.auto_generated_subtitles is False
        assert config.use_archive is False
        assert config.skip_duplicates is False
        assert config.format_preferences.video_codec == 'vp9'
        assert config.format_preferences.prefer_free_formats is True
    
    def test_download_config_to_dict(self):
        """Test converting DownloadConfig to dictionary."""
        format_prefs = FormatPreferences(
            video_codec='h265',
            audio_codec='opus',
            container='mkv',
            prefer_free_formats=True
        )
        
        config = DownloadConfig(
            output_directory='/test/path',
            quality='1440p',
            format_preference='mkv',
            audio_format='ogg',
            split_timestamps=True,
            max_parallel_downloads=7,
            save_thumbnails=False,
            save_metadata=True,
            resume_downloads=False,
            retry_attempts=5,
            format_preferences=format_prefs
        )
        
        config_dict = self.config_manager._download_config_to_dict(config)
        
        assert config_dict['output_directory'] == '/test/path'
        assert config_dict['quality'] == '1440p'
        assert config_dict['format_preference'] == 'mkv'
        assert config_dict['split_timestamps'] is True
        assert config_dict['max_parallel_downloads'] == 7
        assert config_dict['format_preferences']['video_codec'] == 'h265'
        assert config_dict['format_preferences']['prefer_free_formats'] is True
    
    def test_get_config_path_default(self):
        """Test getting default configuration path."""
        config_path = self.config_manager.get_config_path()
        
        assert isinstance(config_path, Path)
        assert config_path.name == ConfigManager.DEFAULT_CONFIG_FILENAME
    
    def test_get_config_path_custom_dir(self):
        """Test getting configuration path with custom directory."""
        custom_dir = "/custom/config/dir"
        config_path = self.config_manager.get_config_path(custom_dir)
        
        assert isinstance(config_path, Path)
        assert str(config_path.parent) == custom_dir
        assert config_path.name == ConfigManager.DEFAULT_CONFIG_FILENAME