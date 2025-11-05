"""
Unit tests for filesystem validation functionality.
"""

import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from config.filesystem_validator import (
    FileSystemValidator, validate_download_prerequisites
)
from config.error_handling import FileSystemError


class TestFileSystemValidator:
    """Test cases for FileSystemValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileSystemValidator()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_disk_space_sufficient(self):
        """Test disk space validation with sufficient space."""
        # Use a small size that should always be available
        small_size = 1024  # 1KB
        
        result = self.validator.validate_disk_space(str(self.temp_path), small_size)
        assert result is True
    
    def test_validate_disk_space_insufficient(self):
        """Test disk space validation with insufficient space."""
        # Use an impossibly large size
        huge_size = 10**18  # 1 exabyte
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_disk_space(str(self.temp_path), huge_size)
        
        assert "insufficient disk space" in str(exc_info.value).lower()
        assert "available" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()
    
    def test_validate_disk_space_nonexistent_path(self):
        """Test disk space validation creates directory if needed."""
        new_dir = self.temp_path / "new_directory"
        assert not new_dir.exists()
        
        result = self.validator.validate_disk_space(str(new_dir), 1024)
        assert result is True
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_validate_path_permissions_valid(self):
        """Test path permissions validation for valid directory."""
        permissions = self.validator.validate_path_permissions(str(self.temp_path))
        
        assert isinstance(permissions, dict)
        assert permissions['readable'] is True
        assert permissions['writable'] is True
        assert permissions['executable'] is True
        assert permissions['can_create_files'] is True
    
    def test_validate_path_permissions_creates_directory(self):
        """Test path permissions validation creates directory if needed."""
        new_dir = self.temp_path / "permissions_test"
        assert not new_dir.exists()
        
        permissions = self.validator.validate_path_permissions(str(new_dir))
        
        assert new_dir.exists()
        assert permissions['can_create_files'] is True
    
    @patch('os.access')
    def test_validate_path_permissions_insufficient(self, mock_access):
        """Test path permissions validation with insufficient permissions."""
        # Mock insufficient permissions
        mock_access.return_value = False
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_path_permissions(str(self.temp_path))
        
        assert "insufficient permissions" in str(exc_info.value).lower()
    
    def test_validate_path_permissions_file_not_directory(self):
        """Test path permissions validation when path is a file."""
        test_file = self.temp_path / "test_file.txt"
        test_file.touch()
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_path_permissions(str(test_file))
        
        assert "not a directory" in str(exc_info.value).lower()
    
    def test_validate_path_safety_valid_path(self):
        """Test path safety validation for valid path."""
        safe_path = self.temp_path / "safe_directory"
        
        result = self.validator.validate_path_safety(str(safe_path))
        assert result is True
    
    def test_validate_path_safety_directory_traversal(self):
        """Test path safety validation detects directory traversal."""
        unsafe_path = str(self.temp_path / ".." / ".." / "etc" / "passwd")
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_path_safety(unsafe_path)
        
        assert "directory traversal" in str(exc_info.value).lower()
    
    def test_validate_path_safety_with_base_path(self):
        """Test path safety validation with base path restriction."""
        base_path = str(self.temp_path)
        safe_path = str(self.temp_path / "subdirectory")
        unsafe_path = str(self.temp_path.parent / "outside")
        
        # Safe path within base
        result = self.validator.validate_path_safety(safe_path, base_path)
        assert result is True
        
        # Unsafe path outside base
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_path_safety(unsafe_path, base_path)
        
        assert "outside allowed base path" in str(exc_info.value).lower()
    
    def test_validate_path_safety_suspicious_components(self):
        """Test path safety validation detects suspicious components."""
        if os.name == 'nt':  # Windows
            suspicious_path = "C:\\Windows\\System32\\test"
        else:  # Unix-like
            suspicious_path = "/etc/test"
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_path_safety(suspicious_path)
        
        assert "suspicious component" in str(exc_info.value).lower()
    
    def test_get_disk_usage_info(self):
        """Test disk usage information retrieval."""
        usage_info = self.validator.get_disk_usage_info(str(self.temp_path))
        
        assert isinstance(usage_info, dict)
        assert 'total_bytes' in usage_info
        assert 'used_bytes' in usage_info
        assert 'free_bytes' in usage_info
        assert 'total_formatted' in usage_info
        assert 'usage_percent' in usage_info
        
        # Check that values are reasonable
        assert usage_info['total_bytes'] > 0
        assert usage_info['free_bytes'] >= 0
        assert 0 <= usage_info['usage_percent'] <= 100
    
    def test_estimate_video_size_video_formats(self):
        """Test video size estimation for different video qualities."""
        duration = 3600  # 1 hour
        
        # Test different video qualities
        size_720p = self.validator.estimate_video_size(duration, '720p', 'video')
        size_1080p = self.validator.estimate_video_size(duration, '1080p', 'video')
        size_best = self.validator.estimate_video_size(duration, 'best', 'video')
        
        assert size_720p > 0
        assert size_1080p > size_720p  # Higher quality should be larger
        assert size_best > 0
        
        # Test that estimates are reasonable (not too small or too large)
        assert 1_000_000 < size_720p < 2_000_000_000  # Between 1MB and 2GB for 1 hour
    
    def test_estimate_video_size_audio_formats(self):
        """Test video size estimation for audio formats."""
        duration = 3600  # 1 hour
        
        # Test different audio qualities
        size_low = self.validator.estimate_video_size(duration, 'low', 'audio')
        size_high = self.validator.estimate_video_size(duration, 'high', 'audio')
        size_best = self.validator.estimate_video_size(duration, 'best', 'audio')
        
        assert size_low > 0
        assert size_high > size_low  # Higher quality should be larger
        assert size_best > size_high
        
        # Audio should be smaller than video
        size_video = self.validator.estimate_video_size(duration, '720p', 'video')
        assert size_high < size_video
    
    def test_validate_filename_valid(self):
        """Test filename validation for valid filenames."""
        valid_names = [
            "normal_filename.mp4",
            "file with spaces.mp4",
            "file-with-dashes.mp4",
            "file_with_underscores.mp4",
            "file123.mp4"
        ]
        
        for filename in valid_names:
            result = self.validator.validate_filename(filename)
            assert result == filename  # Should remain unchanged
    
    def test_validate_filename_invalid_characters(self):
        """Test filename validation removes invalid characters."""
        invalid_filename = 'file<>:"/\\|?*name.mp4'
        result = self.validator.validate_filename(invalid_filename)
        
        # Should replace invalid characters with underscores
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '/' not in result
        assert '\\' not in result
        assert '|' not in result
        assert '?' not in result
        assert '*' not in result
        assert '_' in result  # Should contain replacement character
    
    def test_validate_filename_reserved_names(self):
        """Test filename validation handles Windows reserved names."""
        reserved_names = ['CON.mp4', 'PRN.txt', 'AUX.mp4', 'NUL.txt']
        
        for reserved_name in reserved_names:
            result = self.validator.validate_filename(reserved_name)
            assert result.startswith('_')  # Should be prefixed with underscore
    
    def test_validate_filename_too_long(self):
        """Test filename validation truncates long filenames."""
        long_filename = 'a' * 250 + '.mp4'  # Very long filename
        result = self.validator.validate_filename(long_filename)
        
        assert len(result) <= 200
        assert result.endswith('.mp4')  # Should preserve extension
    
    def test_validate_filename_empty(self):
        """Test filename validation handles empty filenames."""
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_filename("")
        
        assert "empty" in str(exc_info.value).lower()
        
        with pytest.raises(FileSystemError) as exc_info:
            self.validator.validate_filename("   ")  # Only whitespace
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_check_file_locks_unlocked_file(self):
        """Test file lock checking for unlocked file."""
        test_file = self.temp_path / "test_file.txt"
        test_file.write_text("test content")
        
        result = self.validator.check_file_locks(str(test_file))
        assert result is True
    
    def test_check_file_locks_nonexistent_file(self):
        """Test file lock checking for nonexistent file."""
        nonexistent_file = self.temp_path / "nonexistent.txt"
        
        result = self.validator.check_file_locks(str(nonexistent_file))
        assert result is False
    
    def test_format_bytes(self):
        """Test byte formatting utility."""
        # Test various byte sizes
        assert self.validator._format_bytes(0) == "0.0 B"
        assert self.validator._format_bytes(1024) == "1.0 KB"
        assert self.validator._format_bytes(1024 * 1024) == "1.0 MB"
        assert self.validator._format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        
        # Test fractional values
        result = self.validator._format_bytes(1536)  # 1.5 KB
        assert "1.5 KB" == result


class TestValidateDownloadPrerequisites:
    """Test cases for validate_download_prerequisites function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_download_prerequisites_success(self):
        """Test successful validation of download prerequisites."""
        result = validate_download_prerequisites(
            output_path=str(self.temp_path),
            estimated_size=1024,
            filename="test_video.mp4"
        )
        
        assert isinstance(result, dict)
        assert result['path_safe'] is True
        assert result['permissions_ok'] is True
        assert result['disk_space_ok'] is True
        assert result['filename_ok'] is True
        assert result['sanitized_filename'] == "test_video.mp4"
        assert 'disk_usage' in result
        assert 'permissions' in result
    
    def test_validate_download_prerequisites_no_size(self):
        """Test validation without estimated size."""
        result = validate_download_prerequisites(
            output_path=str(self.temp_path),
            estimated_size=0
        )
        
        assert result['path_safe'] is True
        assert result['permissions_ok'] is True
        assert result['disk_space_ok'] is False  # Not checked when size is 0
    
    def test_validate_download_prerequisites_invalid_filename(self):
        """Test validation with invalid filename."""
        result = validate_download_prerequisites(
            output_path=str(self.temp_path),
            filename="invalid<>filename.mp4"
        )
        
        assert result['filename_ok'] is True
        assert '<' not in result['sanitized_filename']
        assert '>' not in result['sanitized_filename']
    
    def test_validate_download_prerequisites_failure(self):
        """Test validation failure scenarios."""
        # Test with insufficient disk space
        with pytest.raises(FileSystemError):
            validate_download_prerequisites(
                output_path=str(self.temp_path),
                estimated_size=10**18  # Impossibly large
            )


class TestFileSystemValidatorIntegration:
    """Integration tests for FileSystemValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileSystemValidator()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_validation_workflow(self):
        """Test complete validation workflow for a download scenario."""
        # Simulate a typical download validation scenario
        output_path = str(self.temp_path / "downloads")
        filename = "My Video Title - Episode 1.mp4"
        estimated_size = 100 * 1024 * 1024  # 100MB
        
        # Step 1: Validate path safety
        self.validator.validate_path_safety(output_path)
        
        # Step 2: Validate permissions (creates directory)
        permissions = self.validator.validate_path_permissions(output_path)
        assert permissions['can_create_files'] is True
        
        # Step 3: Validate disk space
        self.validator.validate_disk_space(output_path, estimated_size)
        
        # Step 4: Sanitize filename
        safe_filename = self.validator.validate_filename(filename)
        assert safe_filename == filename  # Should be valid as-is
        
        # Step 5: Get disk usage info
        usage_info = self.validator.get_disk_usage_info(output_path)
        assert usage_info['free_bytes'] > estimated_size
        
        # Verify directory was created and is usable
        test_file = Path(output_path) / "test.txt"
        test_file.write_text("test")
        assert test_file.exists()
    
    def test_error_recovery_scenarios(self):
        """Test error recovery in various scenarios."""
        # Test recovery from permission errors
        restricted_path = self.temp_path / "restricted"
        
        try:
            # This should work in most test environments
            self.validator.validate_path_permissions(str(restricted_path))
        except FileSystemError:
            # If it fails, that's also a valid test outcome
            pass
        
        # Test recovery from disk space issues with smaller size
        try:
            self.validator.validate_disk_space(str(self.temp_path), 10**15)
            assert False, "Should have raised FileSystemError"
        except FileSystemError:
            # Now try with reasonable size
            self.validator.validate_disk_space(str(self.temp_path), 1024)


if __name__ == "__main__":
    pytest.main([__file__])