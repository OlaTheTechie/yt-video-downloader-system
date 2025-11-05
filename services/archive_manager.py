"""
Archive manager implementation for duplicate detection and download tracking.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timedelta
import logging

from models.core import VideoMetadata, DownloadResult, DownloadConfig


class ArchiveManager:
    """Manages download archive and duplicate detection."""
    
    ARCHIVE_FILENAME = "download_archive.json"
    METADATA_VERSION = "1.0"
    
    def __init__(self, archive_dir: str = "./downloads", logger: Optional[logging.Logger] = None):
        """
        Initialize ArchiveManager.
        
        Args:
            archive_dir: Directory to store archive file
            logger: Optional logger instance
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.archive_file = self.archive_dir / self.ARCHIVE_FILENAME
        self.logger = logger or logging.getLogger(__name__)
        
        # In-memory cache of archive data
        self._archive_cache: Optional[Dict[str, Any]] = None
        self._cache_dirty = False
    
    def is_downloaded(self, video_id: str) -> bool:
        """
        Check if a video has already been downloaded.
        
        Args:
            video_id: Video ID to check
            
        Returns:
            True if video has been downloaded
        """
        archive_data = self._load_archive()
        return video_id in archive_data.get('downloaded_videos', {})
    
    def add_download_record(self, video_metadata: VideoMetadata, download_result: DownloadResult) -> None:
        """
        Add a download record to the archive.
        
        Args:
            video_metadata: Video metadata
            download_result: Download result information
        """
        if not download_result.success:
            return
        
        archive_data = self._load_archive()
        
        # Create download record
        download_record = {
            'video_id': video_metadata.video_id,
            'title': video_metadata.title,
            'uploader': video_metadata.uploader,
            'upload_date': video_metadata.upload_date,
            'duration': video_metadata.duration,
            'webpage_url': video_metadata.webpage_url,
            'download_date': datetime.now().isoformat(),
            'file_path': download_result.video_path,
            'file_size': self._get_file_size(download_result.video_path),
            'metadata_path': download_result.metadata_path,
            'thumbnail_path': download_result.thumbnail_path,
            'subtitle_files': download_result.subtitle_files,
            'split_files': download_result.split_files,
            'download_time': download_result.download_time,
            'content_hash': self._calculate_content_hash(video_metadata)
        }
        
        # Add to archive
        archive_data['downloaded_videos'][video_metadata.video_id] = download_record
        archive_data['stats']['total_downloads'] += 1
        archive_data['stats']['total_size'] += download_record['file_size']
        archive_data['last_updated'] = datetime.now().isoformat()
        
        # Save archive
        self._save_archive(archive_data)
        self.logger.info(f"Added download record for video: {video_metadata.title}")
    
    def get_download_record(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get download record for a video.
        
        Args:
            video_id: Video ID to look up
            
        Returns:
            Download record dictionary or None if not found
        """
        archive_data = self._load_archive()
        return archive_data.get('downloaded_videos', {}).get(video_id)
    
    def remove_download_record(self, video_id: str) -> bool:
        """
        Remove a download record from the archive.
        
        Args:
            video_id: Video ID to remove
            
        Returns:
            True if record was removed, False if not found
        """
        archive_data = self._load_archive()
        downloaded_videos = archive_data.get('downloaded_videos', {})
        
        if video_id in downloaded_videos:
            record = downloaded_videos.pop(video_id)
            archive_data['stats']['total_downloads'] -= 1
            archive_data['stats']['total_size'] -= record.get('file_size', 0)
            archive_data['last_updated'] = datetime.now().isoformat()
            
            self._save_archive(archive_data)
            self.logger.info(f"Removed download record for video ID: {video_id}")
            return True
        
        return False
    
    def find_duplicates_by_content(self) -> List[List[Dict[str, Any]]]:
        """
        Find potential duplicate downloads based on content hash.
        
        Returns:
            List of lists, where each inner list contains duplicate records
        """
        archive_data = self._load_archive()
        downloaded_videos = archive_data.get('downloaded_videos', {})
        
        # Group by content hash
        hash_groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for video_id, record in downloaded_videos.items():
            content_hash = record.get('content_hash')
            if content_hash:
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append(record)
        
        # Return only groups with more than one item (duplicates)
        duplicates = [group for group in hash_groups.values() if len(group) > 1]
        
        self.logger.info(f"Found {len(duplicates)} groups of duplicate content")
        return duplicates
    
    def find_duplicates_by_title(self, similarity_threshold: float = 0.8) -> List[List[Dict[str, Any]]]:
        """
        Find potential duplicate downloads based on title similarity.
        
        Args:
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of lists, where each inner list contains similar records
        """
        archive_data = self._load_archive()
        downloaded_videos = archive_data.get('downloaded_videos', {})
        
        records = list(downloaded_videos.values())
        duplicates = []
        processed = set()
        
        for i, record1 in enumerate(records):
            if i in processed:
                continue
            
            similar_group = [record1]
            processed.add(i)
            
            for j, record2 in enumerate(records[i+1:], i+1):
                if j in processed:
                    continue
                
                similarity = self._calculate_title_similarity(
                    record1.get('title', ''), 
                    record2.get('title', '')
                )
                
                if similarity >= similarity_threshold:
                    similar_group.append(record2)
                    processed.add(j)
            
            if len(similar_group) > 1:
                duplicates.append(similar_group)
        
        self.logger.info(f"Found {len(duplicates)} groups of similar titles")
        return duplicates
    
    def cleanup_missing_files(self) -> List[str]:
        """
        Remove archive records for files that no longer exist.
        
        Returns:
            List of video IDs that were removed
        """
        archive_data = self._load_archive()
        downloaded_videos = archive_data.get('downloaded_videos', {})
        
        removed_ids = []
        
        for video_id, record in list(downloaded_videos.items()):
            file_path = record.get('file_path')
            if file_path and not os.path.exists(file_path):
                downloaded_videos.pop(video_id)
                removed_ids.append(video_id)
                archive_data['stats']['total_downloads'] -= 1
                archive_data['stats']['total_size'] -= record.get('file_size', 0)
        
        if removed_ids:
            archive_data['last_updated'] = datetime.now().isoformat()
            self._save_archive(archive_data)
            self.logger.info(f"Cleaned up {len(removed_ids)} missing file records")
        
        return removed_ids
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """
        Get archive statistics.
        
        Returns:
            Dictionary with archive statistics
        """
        archive_data = self._load_archive()
        stats = archive_data.get('stats', {})
        
        # Calculate additional stats
        downloaded_videos = archive_data.get('downloaded_videos', {})
        
        if downloaded_videos:
            # Calculate date range
            download_dates = [
                datetime.fromisoformat(record.get('download_date', ''))
                for record in downloaded_videos.values()
                if record.get('download_date')
            ]
            
            if download_dates:
                stats['first_download'] = min(download_dates).isoformat()
                stats['last_download'] = max(download_dates).isoformat()
            
            # Calculate uploader stats
            uploaders = {}
            for record in downloaded_videos.values():
                uploader = record.get('uploader', 'Unknown')
                uploaders[uploader] = uploaders.get(uploader, 0) + 1
            
            stats['top_uploaders'] = sorted(
                uploaders.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            # Calculate format stats
            total_duration = sum(
                record.get('duration', 0) 
                for record in downloaded_videos.values()
            )
            stats['total_duration_hours'] = total_duration / 3600
        
        return stats
    
    def export_archive(self, export_path: str, include_metadata: bool = True) -> None:
        """
        Export archive data to a file.
        
        Args:
            export_path: Path to export file
            include_metadata: Whether to include full metadata
        """
        archive_data = self._load_archive()
        
        if not include_metadata:
            # Create simplified export
            simplified_data = {
                'version': archive_data.get('version'),
                'created_date': archive_data.get('created_date'),
                'last_updated': archive_data.get('last_updated'),
                'stats': archive_data.get('stats'),
                'video_ids': list(archive_data.get('downloaded_videos', {}).keys())
            }
            export_data = simplified_data
        else:
            export_data = archive_data
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Archive exported to: {export_path}")
    
    def import_archive(self, import_path: str, merge: bool = True) -> None:
        """
        Import archive data from a file.
        
        Args:
            import_path: Path to import file
            merge: Whether to merge with existing archive or replace
        """
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        if merge:
            current_data = self._load_archive()
            
            # Merge downloaded videos
            current_videos = current_data.get('downloaded_videos', {})
            import_videos = import_data.get('downloaded_videos', {})
            
            for video_id, record in import_videos.items():
                if video_id not in current_videos:
                    current_videos[video_id] = record
            
            # Update stats
            current_data['downloaded_videos'] = current_videos
            current_data['stats']['total_downloads'] = len(current_videos)
            current_data['last_updated'] = datetime.now().isoformat()
            
            self._save_archive(current_data)
        else:
            # Replace entire archive
            import_data['last_updated'] = datetime.now().isoformat()
            self._save_archive(import_data)
        
        self.logger.info(f"Archive imported from: {import_path}")
    
    def _load_archive(self) -> Dict[str, Any]:
        """Load archive data from file or create new archive."""
        if self._archive_cache is not None and not self._cache_dirty:
            return self._archive_cache
        
        if not self.archive_file.exists():
            # Create new archive
            archive_data = {
                'version': self.METADATA_VERSION,
                'created_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'downloaded_videos': {},
                'stats': {
                    'total_downloads': 0,
                    'total_size': 0
                }
            }
        else:
            try:
                with open(self.archive_file, 'r', encoding='utf-8') as f:
                    archive_data = json.load(f)
                
                # Validate and migrate if necessary
                archive_data = self._validate_and_migrate_archive(archive_data)
                
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error loading archive file: {e}")
                # Create backup and start fresh
                backup_path = self.archive_file.with_suffix('.backup.json')
                if self.archive_file.exists():
                    self.archive_file.rename(backup_path)
                    self.logger.info(f"Corrupted archive backed up to: {backup_path}")
                
                archive_data = {
                    'version': self.METADATA_VERSION,
                    'created_date': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'downloaded_videos': {},
                    'stats': {
                        'total_downloads': 0,
                        'total_size': 0
                    }
                }
        
        self._archive_cache = archive_data
        self._cache_dirty = False
        return archive_data
    
    def _save_archive(self, archive_data: Dict[str, Any]) -> None:
        """Save archive data to file."""
        try:
            # Create backup of existing archive
            if self.archive_file.exists():
                backup_path = self.archive_file.with_suffix('.bak')
                self.archive_file.rename(backup_path)
            
            # Save new archive
            with open(self.archive_file, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2, ensure_ascii=False)
            
            # Update cache
            self._archive_cache = archive_data
            self._cache_dirty = False
            
            # Remove backup if save was successful
            backup_path = self.archive_file.with_suffix('.bak')
            if backup_path.exists():
                backup_path.unlink()
                
        except Exception as e:
            self.logger.error(f"Error saving archive: {e}")
            # Restore backup if it exists
            backup_path = self.archive_file.with_suffix('.bak')
            if backup_path.exists():
                backup_path.rename(self.archive_file)
            raise
    
    def _validate_and_migrate_archive(self, archive_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and migrate archive data to current version."""
        # Ensure required fields exist
        if 'version' not in archive_data:
            archive_data['version'] = '1.0'
        
        if 'downloaded_videos' not in archive_data:
            archive_data['downloaded_videos'] = {}
        
        if 'stats' not in archive_data:
            archive_data['stats'] = {
                'total_downloads': len(archive_data.get('downloaded_videos', {})),
                'total_size': 0
            }
        
        if 'created_date' not in archive_data:
            archive_data['created_date'] = datetime.now().isoformat()
        
        if 'last_updated' not in archive_data:
            archive_data['last_updated'] = datetime.now().isoformat()
        
        return archive_data
    
    def _calculate_content_hash(self, metadata: VideoMetadata) -> str:
        """Calculate a hash based on video content characteristics."""
        # Use title, uploader, duration, and upload date for content hash
        content_string = f"{metadata.title}|{metadata.uploader}|{metadata.duration}|{metadata.upload_date}"
        return hashlib.md5(content_string.encode('utf-8')).hexdigest()
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles using simple word overlap."""
        if not title1 or not title2:
            return 0.0
        
        # Normalize titles
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        try:
            return os.path.getsize(file_path) if os.path.exists(file_path) else 0
        except OSError:
            return 0