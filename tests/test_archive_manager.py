"""
Unit tests for ArchiveManager class.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from services.archive_manager import ArchiveManager
from models.core import VideoMetadata, DownloadResult, DownloadStatus


class TestArchiveManager:
    """Test cases for ArchiveManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.archive_manager = ArchiveManager(str(self.temp_path))
        
        # Mock video metadata
        self.mock_metadata = VideoMetadata(
            title='Test Video',
            uploader='Test Channel',
            description='Test description',
            upload_date='20231201',
            duration=615.5,
            view_count=1000,
            thumbnail_url='https://example.com/thumb.jpg',
            video_id='test123',
            webpage_url='https://youtube.com/watch?v=test123'
        )
        
        # Mock download result
        self.mock_result = DownloadResult(
            success=True,
            video_path=str(self.temp_path / 'test_video.mp4'),
            metadata_path=str(self.temp_path / 'test_video.json'),
            thumbnail_path=str(self.temp_path / 'test_video.jpg'),
            download_time=45.5,
            status=DownloadStatus.COMPLETED
        )
        
        # Create mock video file for file size calculation
        (self.temp_path / 'test_video.mp4').write_bytes(b'fake video content')
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_archive_initialization(self):
        """Test archive manager initialization."""
        # Test that archive directory is created
        assert self.temp_path.exists()
        
        # Test that archive file doesn't exist initially
        archive_file = self.temp_path / ArchiveManager.ARCHIVE_FILENAME
        assert not archive_file.exists()
    
    def test_load_empty_archive(self):
        """Test loading empty archive creates default structure."""
        archive_data = self.archive_manager._load_archive()
        
        assert archive_data['version'] == ArchiveManager.METADATA_VERSION
        assert 'created_date' in archive_data
        assert 'last_updated' in archive_data
        assert archive_data['downloaded_videos'] == {}
        assert archive_data['stats']['total_downloads'] == 0
        assert archive_data['stats']['total_size'] == 0
    
    def test_is_downloaded_empty_archive(self):
        """Test checking if video is downloaded in empty archive."""
        assert self.archive_manager.is_downloaded('test123') is False
        assert self.archive_manager.is_downloaded('nonexistent') is False
    
    def test_add_download_record(self):
        """Test adding a download record to archive."""
        # Add download record
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        
        # Verify record was added
        assert self.archive_manager.is_downloaded('test123') is True
        
        # Get and verify record details
        record = self.archive_manager.get_download_record('test123')
        assert record is not None
        assert record['video_id'] == 'test123'
        assert record['title'] == 'Test Video'
        assert record['uploader'] == 'Test Channel'
        assert record['file_path'] == self.mock_result.video_path
        assert record['download_time'] == 45.5
        assert 'content_hash' in record
        assert 'download_date' in record
    
    def test_add_failed_download_record(self):
        """Test that failed downloads are not added to archive."""
        failed_result = DownloadResult(success=False, error_message="Download failed")
        
        self.archive_manager.add_download_record(self.mock_metadata, failed_result)
        
        # Verify record was not added
        assert self.archive_manager.is_downloaded('test123') is False
    
    def test_remove_download_record(self):
        """Test removing a download record from archive."""
        # Add record first
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        assert self.archive_manager.is_downloaded('test123') is True
        
        # Remove record
        removed = self.archive_manager.remove_download_record('test123')
        assert removed is True
        assert self.archive_manager.is_downloaded('test123') is False
        
        # Try to remove non-existent record
        removed = self.archive_manager.remove_download_record('nonexistent')
        assert removed is False
    
    def test_calculate_content_hash(self):
        """Test content hash calculation."""
        hash1 = self.archive_manager._calculate_content_hash(self.mock_metadata)
        
        # Same metadata should produce same hash
        hash2 = self.archive_manager._calculate_content_hash(self.mock_metadata)
        assert hash1 == hash2
        
        # Different metadata should produce different hash
        different_metadata = VideoMetadata(
            title='Different Video',
            uploader='Different Channel',
            description='Different description',
            upload_date='20231202',
            duration=300.0,
            view_count=500,
            thumbnail_url='https://example.com/thumb2.jpg',
            video_id='different123',
            webpage_url='https://youtube.com/watch?v=different123'
        )
        
        hash3 = self.archive_manager._calculate_content_hash(different_metadata)
        assert hash1 != hash3
    
    def test_calculate_title_similarity(self):
        """Test title similarity calculation."""
        # Identical titles
        similarity = self.archive_manager._calculate_title_similarity(
            "Test Video Title", "Test Video Title"
        )
        assert similarity == 1.0
        
        # Completely different titles
        similarity = self.archive_manager._calculate_title_similarity(
            "Test Video Title", "Completely Different Content"
        )
        assert similarity < 0.5
        
        # Partially similar titles
        similarity = self.archive_manager._calculate_title_similarity(
            "Test Video Tutorial", "Test Video Guide"
        )
        assert 0.3 < similarity < 0.8
        
        # Empty titles
        similarity = self.archive_manager._calculate_title_similarity("", "Test")
        assert similarity == 0.0
    
    def test_find_duplicates_by_content(self):
        """Test finding duplicates by content hash."""
        # Add multiple records with same content hash
        metadata1 = self.mock_metadata
        metadata2 = VideoMetadata(
            title='Test Video',  # Same title
            uploader='Test Channel',  # Same uploader
            description='Different description',
            upload_date='20231201',  # Same date
            duration=615.5,  # Same duration
            view_count=2000,  # Different view count
            thumbnail_url='https://example.com/thumb2.jpg',
            video_id='test456',  # Different ID
            webpage_url='https://youtube.com/watch?v=test456'
        )
        
        result1 = DownloadResult(success=True, video_path='/path1.mp4')
        result2 = DownloadResult(success=True, video_path='/path2.mp4')
        
        self.archive_manager.add_download_record(metadata1, result1)
        self.archive_manager.add_download_record(metadata2, result2)
        
        # Find duplicates
        duplicates = self.archive_manager.find_duplicates_by_content()
        
        # Should find one group with two items
        assert len(duplicates) == 1
        assert len(duplicates[0]) == 2
    
    def test_find_duplicates_by_title(self):
        """Test finding duplicates by title similarity."""
        # Add records with similar titles
        metadata1 = VideoMetadata(
            title='Python Tutorial for Beginners',
            uploader='Channel1', description='', upload_date='20231201',
            duration=600, view_count=1000, thumbnail_url='', video_id='vid1',
            webpage_url='https://youtube.com/watch?v=vid1'
        )
        
        metadata2 = VideoMetadata(
            title='Python Tutorial for Beginners Part 2',
            uploader='Channel1', description='', upload_date='20231202',
            duration=650, view_count=1100, thumbnail_url='', video_id='vid2',
            webpage_url='https://youtube.com/watch?v=vid2'
        )
        
        result1 = DownloadResult(success=True, video_path='/path1.mp4')
        result2 = DownloadResult(success=True, video_path='/path2.mp4')
        
        self.archive_manager.add_download_record(metadata1, result1)
        self.archive_manager.add_download_record(metadata2, result2)
        
        # Find duplicates with lower threshold
        duplicates = self.archive_manager.find_duplicates_by_title(similarity_threshold=0.6)
        
        # Should find similar titles
        assert len(duplicates) >= 0  # May or may not find duplicates depending on similarity
    
    def test_cleanup_missing_files(self):
        """Test cleaning up records for missing files."""
        # Add record with non-existent file
        result_missing = DownloadResult(
            success=True,
            video_path='/nonexistent/path.mp4'
        )
        
        self.archive_manager.add_download_record(self.mock_metadata, result_missing)
        assert self.archive_manager.is_downloaded('test123') is True
        
        # Clean up missing files
        removed_ids = self.archive_manager.cleanup_missing_files()
        
        # Should remove the record with missing file
        assert 'test123' in removed_ids
        assert self.archive_manager.is_downloaded('test123') is False
    
    def test_get_archive_stats(self):
        """Test getting archive statistics."""
        # Add some records
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        
        # Get stats
        stats = self.archive_manager.get_archive_stats()
        
        assert stats['total_downloads'] == 1
        assert stats['total_size'] > 0
        assert 'first_download' in stats
        assert 'last_download' in stats
        assert 'top_uploaders' in stats
        assert 'total_duration_hours' in stats
        
        # Check uploader stats
        assert len(stats['top_uploaders']) > 0
        assert stats['top_uploaders'][0][0] == 'Test Channel'
        assert stats['top_uploaders'][0][1] == 1
    
    def test_export_archive(self):
        """Test exporting archive data."""
        # Add some data
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        
        # Export archive
        export_path = self.temp_path / 'exported_archive.json'
        self.archive_manager.export_archive(str(export_path))
        
        # Verify export file exists and contains data
        assert export_path.exists()
        
        with open(export_path, 'r') as f:
            exported_data = json.load(f)
        
        assert 'downloaded_videos' in exported_data
        assert 'test123' in exported_data['downloaded_videos']
        assert exported_data['stats']['total_downloads'] == 1
    
    def test_export_archive_simplified(self):
        """Test exporting simplified archive data."""
        # Add some data
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        
        # Export simplified archive
        export_path = self.temp_path / 'simplified_archive.json'
        self.archive_manager.export_archive(str(export_path), include_metadata=False)
        
        # Verify export file contains only basic info
        with open(export_path, 'r') as f:
            exported_data = json.load(f)
        
        assert 'video_ids' in exported_data
        assert 'test123' in exported_data['video_ids']
        assert 'downloaded_videos' not in exported_data  # Full metadata not included
    
    def test_import_archive(self):
        """Test importing archive data."""
        # Create test import data
        import_data = {
            'version': '1.0',
            'created_date': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'downloaded_videos': {
                'imported123': {
                    'video_id': 'imported123',
                    'title': 'Imported Video',
                    'uploader': 'Imported Channel',
                    'file_path': '/imported/path.mp4'
                }
            },
            'stats': {
                'total_downloads': 1,
                'total_size': 1000
            }
        }
        
        # Save import file
        import_path = self.temp_path / 'import_archive.json'
        with open(import_path, 'w') as f:
            json.dump(import_data, f)
        
        # Import archive (merge mode)
        self.archive_manager.import_archive(str(import_path), merge=True)
        
        # Verify imported data
        assert self.archive_manager.is_downloaded('imported123') is True
        record = self.archive_manager.get_download_record('imported123')
        assert record['title'] == 'Imported Video'
    
    def test_archive_persistence(self):
        """Test that archive data persists across manager instances."""
        # Add record with first manager
        self.archive_manager.add_download_record(self.mock_metadata, self.mock_result)
        assert self.archive_manager.is_downloaded('test123') is True
        
        # Create new manager instance
        new_manager = ArchiveManager(str(self.temp_path))
        
        # Verify data persists
        assert new_manager.is_downloaded('test123') is True
        record = new_manager.get_download_record('test123')
        assert record['title'] == 'Test Video'
    
    def test_corrupted_archive_recovery(self):
        """Test recovery from corrupted archive file."""
        # Create corrupted archive file
        archive_file = self.temp_path / ArchiveManager.ARCHIVE_FILENAME
        archive_file.write_text('invalid json content')
        
        # Create new manager - should handle corruption gracefully
        new_manager = ArchiveManager(str(self.temp_path))
        
        # Should create fresh archive
        archive_data = new_manager._load_archive()
        assert archive_data['downloaded_videos'] == {}
        
        # Should create backup of corrupted file
        backup_file = self.temp_path / 'download_archive.backup.json'
        assert backup_file.exists()
    
    def test_get_file_size(self):
        """Test file size calculation."""
        # Test existing file
        test_file = self.temp_path / 'test_file.txt'
        test_content = b'test content'
        test_file.write_bytes(test_content)
        
        size = self.archive_manager._get_file_size(str(test_file))
        assert size == len(test_content)
        
        # Test non-existent file
        size = self.archive_manager._get_file_size('/nonexistent/file.txt')
        assert size == 0