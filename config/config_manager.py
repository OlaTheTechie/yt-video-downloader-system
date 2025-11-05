"""
Configuration management for the YouTube Video Downloader application.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging

from models.core import DownloadConfig, FormatPreferences
from config.error_handling import ConfigurationError, ValidationError


class ConfigManager:
    """Manages configuration loading, validation, and merging."""
    
    DEFAULT_CONFIG_FILENAME = "youtube_downloader_config.json"
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize ConfigManager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self._default_config = self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration dictionary."""
        return {
            "output_directory": "./downloads",
            "quality": "best",
            "format_preference": "mp4",
            "audio_format": "mp3",
            "split_timestamps": False,
            "max_parallel_downloads": 3,
            "save_thumbnails": True,
            "save_metadata": True,
            "resume_downloads": True,
            "retry_attempts": 3,
            "download_subtitles": False,
            "subtitle_languages": ["en"],
            "subtitle_format": "srt",
            "auto_generated_subtitles": True,
            "use_archive": True,
            "skip_duplicates": True,
            "format_preferences": {
                "video_codec": "h264",
                "audio_codec": "aac",
                "container": "mp4",
                "prefer_free_formats": False
            }
        }
    
    def load_config(self, config_path: Union[str, Path]) -> DownloadConfig:
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            DownloadConfig instance
            
        Raises:
            ConfigurationError: If configuration file cannot be loaded or is invalid
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            self.logger.warning(f"Configuration file not found: {config_path}")
            return self._create_download_config(self._default_config)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.logger.info(f"Loaded configuration from: {config_path}")
            
            # Merge with defaults to ensure all required fields are present
            merged_config = self._merge_configs(self._default_config, config_data)
            
            # Validate the configuration
            self._validate_config(merged_config)
            
            return self._create_download_config(merged_config)
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file {config_path}: {str(e)}",
                details={"file_path": str(config_path), "json_error": str(e)}
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration from {config_path}: {str(e)}",
                details={"file_path": str(config_path)},
                original_exception=e
            )
    
    def save_config(self, config: DownloadConfig, config_path: Union[str, Path]) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            config: DownloadConfig instance to save
            config_path: Path where to save the configuration
            
        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        config_path = Path(config_path)
        
        try:
            # Create directory if it doesn't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert DownloadConfig to dictionary
            config_dict = self._download_config_to_dict(config)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Configuration saved to: {config_path}")
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to save configuration to {config_path}: {str(e)}",
                details={"file_path": str(config_path)},
                original_exception=e
            )
    
    def save_default_config(self, output_path: Union[str, Path]) -> None:
        """
        Generate and save default configuration file.
        
        Args:
            output_path: Path where to save the default configuration
            
        Raises:
            ConfigurationError: If default configuration cannot be saved
        """
        output_path = Path(output_path)
        
        try:
            # Create directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self._default_config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Default configuration saved to: {output_path}")
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to save default configuration to {output_path}: {str(e)}",
                details={"file_path": str(output_path)},
                original_exception=e
            )
    
    def merge_cli_args(self, config: DownloadConfig, cli_args: Dict[str, Any]) -> DownloadConfig:
        """
        Merge CLI arguments with existing configuration.
        CLI arguments take precedence over configuration file values.
        
        Args:
            config: Base DownloadConfig instance
            cli_args: Dictionary of CLI arguments
            
        Returns:
            New DownloadConfig instance with merged values
        """
        # Convert config to dictionary for easier manipulation
        config_dict = self._download_config_to_dict(config)
        
        # Map CLI argument names to config keys
        cli_mapping = {
            'output': 'output_directory',
            'quality': 'quality',
            'format': 'format_preference',
            'audio_format': 'audio_format',
            'split_timestamps': 'split_timestamps',
            'parallel': 'max_parallel_downloads',
            'thumbnails': 'save_thumbnails',
            'metadata': 'save_metadata',
            'resume': 'resume_downloads',
            'retries': 'retry_attempts',
            'subtitles': 'download_subtitles',
            'subtitle_languages': 'subtitle_languages',
            'subtitle_format': 'subtitle_format',
            'auto_subs': 'auto_generated_subtitles',
            'archive': 'use_archive',
            'skip_duplicates': 'skip_duplicates'
        }
        
        # Apply CLI arguments
        for cli_key, config_key in cli_mapping.items():
            if cli_key in cli_args and cli_args[cli_key] is not None:
                config_dict[config_key] = cli_args[cli_key]
                self.logger.debug(f"CLI override: {config_key} = {cli_args[cli_key]}")
        
        # Handle format preferences separately
        if 'video_codec' in cli_args and cli_args['video_codec'] is not None:
            config_dict['format_preferences']['video_codec'] = cli_args['video_codec']
        if 'audio_codec' in cli_args and cli_args['audio_codec'] is not None:
            config_dict['format_preferences']['audio_codec'] = cli_args['audio_codec']
        if 'container' in cli_args and cli_args['container'] is not None:
            config_dict['format_preferences']['container'] = cli_args['container']
        
        # Validate merged configuration
        self._validate_config(config_dict)
        
        return self._create_download_config(config_dict)
    
    def _merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.
        
        Args:
            base_config: Base configuration dictionary
            override_config: Configuration to merge on top
            
        Returns:
            Merged configuration dictionary
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Raises:
            ValidationError: If configuration is invalid
        """
        required_fields = [
            'output_directory', 'quality', 'format_preference', 'audio_format',
            'split_timestamps', 'max_parallel_downloads', 'save_thumbnails',
            'save_metadata', 'resume_downloads', 'retry_attempts', 'download_subtitles',
            'subtitle_languages', 'subtitle_format', 'auto_generated_subtitles',
            'use_archive', 'skip_duplicates'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required configuration field: {field}")
        
        # Validate specific field types and values
        if not isinstance(config['output_directory'], str):
            raise ValidationError("output_directory must be a string")
        
        if not isinstance(config['quality'], str):
            raise ValidationError("quality must be a string")
        
        if not isinstance(config['max_parallel_downloads'], int) or config['max_parallel_downloads'] < 1:
            raise ValidationError("max_parallel_downloads must be a positive integer")
        
        if config['max_parallel_downloads'] > 10:
            self.logger.warning("max_parallel_downloads > 10 may cause rate limiting issues")
        
        if not isinstance(config['retry_attempts'], int) or config['retry_attempts'] < 0:
            raise ValidationError("retry_attempts must be a non-negative integer")
        
        # Validate format preferences if present
        if 'format_preferences' in config:
            format_prefs = config['format_preferences']
            if not isinstance(format_prefs, dict):
                raise ValidationError("format_preferences must be a dictionary")
            
            valid_codecs = ['h264', 'h265', 'vp9', 'av1', 'aac', 'mp3', 'opus']
            if 'video_codec' in format_prefs and format_prefs['video_codec'] not in valid_codecs:
                self.logger.warning(f"Unknown video codec: {format_prefs['video_codec']}")
            
            if 'audio_codec' in format_prefs and format_prefs['audio_codec'] not in valid_codecs:
                self.logger.warning(f"Unknown audio codec: {format_prefs['audio_codec']}")
    
    def _create_download_config(self, config_dict: Dict[str, Any]) -> DownloadConfig:
        """
        Create DownloadConfig instance from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            DownloadConfig instance
        """
        # Extract format preferences
        format_prefs_dict = config_dict.get('format_preferences', {})
        format_preferences = FormatPreferences(
            video_codec=format_prefs_dict.get('video_codec', 'h264'),
            audio_codec=format_prefs_dict.get('audio_codec', 'aac'),
            container=format_prefs_dict.get('container', 'mp4'),
            prefer_free_formats=format_prefs_dict.get('prefer_free_formats', False)
        )
        
        return DownloadConfig(
            output_directory=config_dict['output_directory'],
            quality=config_dict['quality'],
            format_preference=config_dict['format_preference'],
            audio_format=config_dict['audio_format'],
            split_timestamps=config_dict['split_timestamps'],
            max_parallel_downloads=config_dict['max_parallel_downloads'],
            save_thumbnails=config_dict['save_thumbnails'],
            save_metadata=config_dict['save_metadata'],
            resume_downloads=config_dict['resume_downloads'],
            retry_attempts=config_dict['retry_attempts'],
            download_subtitles=config_dict['download_subtitles'],
            subtitle_languages=config_dict['subtitle_languages'],
            subtitle_format=config_dict['subtitle_format'],
            auto_generated_subtitles=config_dict['auto_generated_subtitles'],
            use_archive=config_dict['use_archive'],
            skip_duplicates=config_dict['skip_duplicates'],
            format_preferences=format_preferences
        )
    
    def _download_config_to_dict(self, config: DownloadConfig) -> Dict[str, Any]:
        """
        Convert DownloadConfig instance to dictionary.
        
        Args:
            config: DownloadConfig instance
            
        Returns:
            Configuration dictionary
        """
        return {
            'output_directory': config.output_directory,
            'quality': config.quality,
            'format_preference': config.format_preference,
            'audio_format': config.audio_format,
            'split_timestamps': config.split_timestamps,
            'max_parallel_downloads': config.max_parallel_downloads,
            'save_thumbnails': config.save_thumbnails,
            'save_metadata': config.save_metadata,
            'resume_downloads': config.resume_downloads,
            'retry_attempts': config.retry_attempts,
            'download_subtitles': config.download_subtitles,
            'subtitle_languages': config.subtitle_languages,
            'subtitle_format': config.subtitle_format,
            'auto_generated_subtitles': config.auto_generated_subtitles,
            'use_archive': config.use_archive,
            'skip_duplicates': config.skip_duplicates,
            'format_preferences': {
                'video_codec': config.format_preferences.video_codec,
                'audio_codec': config.format_preferences.audio_codec,
                'container': config.format_preferences.container,
                'prefer_free_formats': config.format_preferences.prefer_free_formats
            }
        }
    
    def get_config_path(self, config_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Get the default configuration file path.
        
        Args:
            config_dir: Optional directory for configuration file
            
        Returns:
            Path to configuration file
        """
        if config_dir is None:
            # Use current directory or user's home directory
            config_dir = Path.cwd()
        else:
            config_dir = Path(config_dir)
        
        return config_dir / self.DEFAULT_CONFIG_FILENAME