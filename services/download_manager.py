"""
Download manager implementation using yt-dlp for video downloads.
"""

import os
import time
import json
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import threading
import queue
from dataclasses import dataclass
from enum import Enum
import hashlib
import pickle
import sys
from datetime import datetime, timedelta

from models.core import (
    DownloadConfig, DownloadResult, ProgressInfo, VideoMetadata, 
    DownloadStatus
)
from services.interfaces import DownloadManagerInterface
from services.timestamp_parser import TimestampParser
from services.video_splitter import VideoSplitter
from services.subtitle_handler import SubtitleHandler


class TaskStatus(Enum):
    """Status enumeration for download tasks."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """Represents a download task in the queue."""
    task_id: str
    url: str
    config: DownloadConfig
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[DownloadResult] = None
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class DownloadQueue:
    """Thread-safe queue for managing download tasks."""
    
    def __init__(self, maxsize: int = 0):
        self._queue = queue.Queue(maxsize=maxsize)
        self._tasks: Dict[str, DownloadTask] = {}
        self._lock = threading.Lock()
        self._task_counter = 0
    
    def add_task(self, url: str, config: DownloadConfig) -> str:
        """Add a download task to the queue."""
        with self._lock:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}_{int(time.time())}"
            
            task = DownloadTask(
                task_id=task_id,
                url=url,
                config=config,
                status=TaskStatus.QUEUED
            )
            
            self._tasks[task_id] = task
            self._queue.put(task)
            
            return task_id
    
    def get_task(self, timeout: Optional[float] = None) -> Optional[DownloadTask]:
        """Get the next task from the queue."""
        try:
            task = self._queue.get(timeout=timeout)
            with self._lock:
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = time.time()
            return task
        except queue.Empty:
            return None
    
    def complete_task(self, task_id: str, result: DownloadResult) -> None:
        """Mark a task as completed."""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                task.result = result
                task.completed_at = time.time()
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a specific task."""
        with self._lock:
            task = self._tasks.get(task_id)
            return task.status if task else None
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """Get all tasks."""
        with self._lock:
            return list(self._tasks.values())
    
    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()
    
    def clear_completed_tasks(self) -> None:
        """Clear completed tasks from memory."""
        with self._lock:
            completed_tasks = [
                task_id for task_id, task in self._tasks.items()
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            ]
            for task_id in completed_tasks:
                del self._tasks[task_id]


@dataclass
class ResumeState:
    """Represents the state of a partially downloaded file."""
    url: str
    video_id: str
    title: str
    output_path: str
    partial_file_path: str
    downloaded_bytes: int
    total_bytes: int
    last_modified: float
    config_hash: str
    metadata: Optional[Dict[str, Any]] = None
    
    def is_valid(self) -> bool:
        """Check if the resume state is still valid."""
        if not os.path.exists(self.partial_file_path):
            return False
        
        # Check if file size matches recorded downloaded bytes
        try:
            actual_size = os.path.getsize(self.partial_file_path)
            return actual_size == self.downloaded_bytes
        except OSError:
            return False
    
    def get_resume_percentage(self) -> float:
        """Get the resume percentage."""
        if self.total_bytes > 0:
            return (self.downloaded_bytes / self.total_bytes) * 100
        return 0.0


class ResumeHandler:
    """Handles download resume functionality."""
    
    def __init__(self, resume_dir: str = "./.resume"):
        self.resume_dir = Path(resume_dir)
        self.resume_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()
    
    def _get_resume_file_path(self, url: str) -> Path:
        """Get the path to the resume state file for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.resume_dir / f"resume_{url_hash}.pkl"
    
    def _get_config_hash(self, config: DownloadConfig) -> str:
        """Generate a hash of the configuration to detect changes."""
        config_str = f"{config.quality}_{config.format_preference}_{config.output_directory}"
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def save_resume_state(self, url: str, video_id: str, title: str, 
                         output_path: str, partial_file_path: str,
                         downloaded_bytes: int, total_bytes: int,
                         config: DownloadConfig, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Save the current download state for resuming."""
        with self._lock:
            resume_state = ResumeState(
                url=url,
                video_id=video_id,
                title=title,
                output_path=output_path,
                partial_file_path=partial_file_path,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                last_modified=time.time(),
                config_hash=self._get_config_hash(config),
                metadata=metadata
            )
            
            resume_file = self._get_resume_file_path(url)
            try:
                with open(resume_file, 'wb') as f:
                    pickle.dump(resume_state, f)
            except Exception as e:
                print(f"Warning: Could not save resume state: {e}")
    
    def load_resume_state(self, url: str) -> Optional[ResumeState]:
        """Load the resume state for a URL."""
        with self._lock:
            resume_file = self._get_resume_file_path(url)
            
            if not resume_file.exists():
                return None
            
            try:
                with open(resume_file, 'rb') as f:
                    resume_state = pickle.load(f)
                
                # Validate the resume state
                if resume_state.is_valid():
                    return resume_state
                else:
                    # Clean up invalid resume state
                    self.clear_resume_state(url)
                    return None
                    
            except Exception as e:
                print(f"Warning: Could not load resume state: {e}")
                # Clean up corrupted resume state
                self.clear_resume_state(url)
                return None
    
    def clear_resume_state(self, url: str) -> None:
        """Clear the resume state for a URL."""
        with self._lock:
            resume_file = self._get_resume_file_path(url)
            try:
                if resume_file.exists():
                    resume_file.unlink()
            except Exception as e:
                print(f"Warning: Could not clear resume state: {e}")
    
    def can_resume(self, url: str, config: DownloadConfig) -> bool:
        """Check if a download can be resumed."""
        resume_state = self.load_resume_state(url)
        if not resume_state:
            return False
        
        # Check if configuration has changed
        current_config_hash = self._get_config_hash(config)
        if resume_state.config_hash != current_config_hash:
            print(f"Configuration changed, cannot resume download for: {resume_state.title}")
            self.clear_resume_state(url)
            return False
        
        return True
    
    def get_all_resume_states(self) -> List[ResumeState]:
        """Get all available resume states."""
        resume_states = []
        
        try:
            for resume_file in self.resume_dir.glob("resume_*.pkl"):
                try:
                    with open(resume_file, 'rb') as f:
                        resume_state = pickle.load(f)
                    
                    if resume_state.is_valid():
                        resume_states.append(resume_state)
                    else:
                        # Clean up invalid state
                        resume_file.unlink()
                        
                except Exception:
                    # Clean up corrupted state
                    try:
                        resume_file.unlink()
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Warning: Error scanning resume states: {e}")
        
        return resume_states
    
    def cleanup_old_resume_states(self, max_age_days: int = 7) -> None:
        """Clean up old resume states."""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        for resume_state in self.get_all_resume_states():
            if resume_state.last_modified < cutoff_time:
                self.clear_resume_state(resume_state.url)
                print(f"Cleaned up old resume state for: {resume_state.title}")


@dataclass
class DownloadProgress:
    """Enhanced progress information for a single download."""
    url: str
    title: str
    status: str
    progress_percent: float
    download_speed: str
    eta: str
    downloaded_bytes: int
    total_bytes: int
    start_time: float
    worker_id: Optional[str] = None
    
    def get_elapsed_time(self) -> str:
        """Get formatted elapsed time."""
        elapsed = time.time() - self.start_time
        return str(timedelta(seconds=int(elapsed)))
    
    def get_formatted_size(self) -> str:
        """Get formatted size information."""
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} TB"
        
        if self.total_bytes > 0:
            return f"{format_bytes(self.downloaded_bytes)} / {format_bytes(self.total_bytes)}"
        else:
            return f"{format_bytes(self.downloaded_bytes)} / Unknown"


class ProgressReporter:
    """Enhanced progress reporter with real-time updates and multi-file tracking."""
    
    def __init__(self, enable_progress_bars: bool = True):
        self.enable_progress_bars = enable_progress_bars
        self._active_downloads: Dict[str, DownloadProgress] = {}
        self._completed_downloads: List[DownloadProgress] = []
        self._lock = threading.Lock()
        self._last_update = 0.0
        self._update_interval = 0.5  # Update every 500ms
        
        # Overall statistics
        self._overall_stats = {
            'total_files': 0,
            'completed_files': 0,
            'failed_files': 0,
            'total_bytes': 0,
            'downloaded_bytes': 0,
            'start_time': time.time(),
            'active_downloads': 0
        }
    
    def start_download(self, url: str, title: str, total_bytes: int = 0) -> None:
        """Start tracking a new download."""
        with self._lock:
            progress = DownloadProgress(
                url=url,
                title=title,
                status="starting",
                progress_percent=0.0,
                download_speed="0 MB/s",
                eta="Unknown",
                downloaded_bytes=0,
                total_bytes=total_bytes,
                start_time=time.time()
            )
            
            self._active_downloads[url] = progress
            self._overall_stats['total_files'] += 1
            self._overall_stats['total_bytes'] += total_bytes
            self._overall_stats['active_downloads'] += 1
    
    def update_download(self, url: str, downloaded_bytes: int, total_bytes: int,
                       speed: str, eta: str, status: str = "downloading") -> None:
        """Update progress for a download."""
        with self._lock:
            if url not in self._active_downloads:
                return
            
            progress = self._active_downloads[url]
            old_downloaded = progress.downloaded_bytes
            
            progress.downloaded_bytes = downloaded_bytes
            progress.total_bytes = max(progress.total_bytes, total_bytes)
            progress.download_speed = speed
            progress.eta = eta
            progress.status = status
            
            if total_bytes > 0:
                progress.progress_percent = (downloaded_bytes / total_bytes) * 100
            
            # Update overall stats
            self._overall_stats['downloaded_bytes'] += (downloaded_bytes - old_downloaded)
            
            # Update display if enough time has passed
            current_time = time.time()
            if current_time - self._last_update >= self._update_interval:
                self._update_display()
                self._last_update = current_time
    
    def complete_download(self, url: str, success: bool, final_size: int = 0) -> None:
        """Mark a download as completed."""
        with self._lock:
            if url not in self._active_downloads:
                return
            
            progress = self._active_downloads[url]
            progress.status = "completed" if success else "failed"
            progress.progress_percent = 100.0 if success else progress.progress_percent
            
            if final_size > 0:
                progress.downloaded_bytes = final_size
                progress.total_bytes = final_size
            
            # Move to completed list
            self._completed_downloads.append(progress)
            del self._active_downloads[url]
            
            # Update overall stats
            if success:
                self._overall_stats['completed_files'] += 1
            else:
                self._overall_stats['failed_files'] += 1
            
            self._overall_stats['active_downloads'] -= 1
            
            # Final update
            self._update_display()
    
    def _update_display(self) -> None:
        """Update the progress display."""
        if not self.enable_progress_bars:
            return
        
        # Clear previous lines
        if hasattr(self, '_last_line_count'):
            for _ in range(self._last_line_count):
                sys.stdout.write('\033[F\033[K')  # Move up and clear line
        
        lines = []
        
        # Overall progress header
        elapsed = time.time() - self._overall_stats['start_time']
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        
        lines.append(f"\n{'='*60}")
        lines.append(f"DOWNLOAD PROGRESS - Elapsed: {elapsed_str}")
        lines.append(f"Total: {self._overall_stats['total_files']} | "
                    f"Completed: {self._overall_stats['completed_files']} | "
                    f"Failed: {self._overall_stats['failed_files']} | "
                    f"Active: {self._overall_stats['active_downloads']}")
        
        if self._overall_stats['total_bytes'] > 0:
            overall_percent = (self._overall_stats['downloaded_bytes'] / self._overall_stats['total_bytes']) * 100
            lines.append(f"Overall Progress: {overall_percent:.1f}%")
        
        lines.append(f"{'='*60}")
        
        # Active downloads
        if self._active_downloads:
            lines.append("ACTIVE DOWNLOADS:")
            for i, (url, progress) in enumerate(self._active_downloads.items(), 1):
                # Progress bar
                bar_width = 30
                filled = int(bar_width * progress.progress_percent / 100)
                bar = '█' * filled + '░' * (bar_width - filled)
                
                # Truncate title if too long
                title = progress.title[:40] + "..." if len(progress.title) > 40 else progress.title
                
                lines.append(f"{i:2d}. {title}")
                lines.append(f"    [{bar}] {progress.progress_percent:.1f}%")
                lines.append(f"    {progress.get_formatted_size()} | {progress.download_speed} | ETA: {progress.eta}")
                lines.append("")
        
        # Recent completions (last 3)
        if self._completed_downloads:
            recent_completed = self._completed_downloads[-3:]
            lines.append("RECENT COMPLETIONS:")
            for progress in recent_completed:
                status_icon = "✓" if progress.status == "completed" else "✗"
                title = progress.title[:50] + "..." if len(progress.title) > 50 else progress.title
                lines.append(f"  {status_icon} {title} ({progress.get_elapsed_time()})")
            lines.append("")
        
        # Print all lines
        output = '\n'.join(lines)
        print(output, end='', flush=True)
        
        # Store line count for next clear
        self._last_line_count = len(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all download progress."""
        with self._lock:
            total_elapsed = time.time() - self._overall_stats['start_time']
            
            return {
                'total_files': self._overall_stats['total_files'],
                'completed_files': self._overall_stats['completed_files'],
                'failed_files': self._overall_stats['failed_files'],
                'active_downloads': len(self._active_downloads),
                'total_elapsed': total_elapsed,
                'overall_progress': (
                    (self._overall_stats['downloaded_bytes'] / self._overall_stats['total_bytes']) * 100
                    if self._overall_stats['total_bytes'] > 0 else 0
                ),
                'active_downloads_detail': [
                    {
                        'title': p.title,
                        'progress': p.progress_percent,
                        'speed': p.download_speed,
                        'eta': p.eta,
                        'elapsed': p.get_elapsed_time()
                    }
                    for p in self._active_downloads.values()
                ]
            }
    
    def print_final_summary(self) -> None:
        """Print final summary of all downloads."""
        summary = self.get_summary()
        
        print(f"\n{'='*60}")
        print("DOWNLOAD SUMMARY")
        print(f"{'='*60}")
        print(f"Total files: {summary['total_files']}")
        print(f"Successful: {summary['completed_files']}")
        print(f"Failed: {summary['failed_files']}")
        print(f"Total time: {str(timedelta(seconds=int(summary['total_elapsed'])))}")
        
        if summary['completed_files'] > 0:
            avg_time = summary['total_elapsed'] / summary['completed_files']
            print(f"Average time per file: {avg_time:.1f}s")
        
        print(f"{'='*60}")
    
    def clear_display(self) -> None:
        """Clear the progress display."""
        if hasattr(self, '_last_line_count'):
            for _ in range(self._last_line_count):
                sys.stdout.write('\033[F\033[K')  # Move up and clear line
            self._last_line_count = 0


class DownloadManager(DownloadManagerInterface):
    """Enhanced download manager with thread pool support and download queue."""
    
    def __init__(self, max_workers: int = 3):
        self._max_workers = max(1, min(max_workers, 10))
        self._progress_callback: Optional[Callable[[ProgressInfo], None]] = None
        self._current_downloads: Dict[str, ProgressInfo] = {}
        self._lock = threading.Lock()
        self._timestamp_parser = TimestampParser()
        self._video_splitter = VideoSplitter()
        self._subtitle_handler = SubtitleHandler()
        
        # Thread pool and queue management
        self._executor: Optional[ThreadPoolExecutor] = None
        self._download_queue = DownloadQueue()
        self._active_futures: Dict[str, Future] = {}
        self._shutdown_event = threading.Event()
        
        # Resume functionality
        self._resume_handler = ResumeHandler()
        
        # Progress reporting
        self._progress_reporter = ProgressReporter(enable_progress_bars=True)
        
        # Statistics
        self._stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_download_time': 0.0,
            'average_download_time': 0.0,
            'resumed_downloads': 0
        }
    
    def set_parallel_workers(self, count: int) -> None:
        """Set the number of parallel download workers."""
        old_count = self._max_workers
        self._max_workers = max(1, min(count, 10))
        
        # If executor is running and worker count changed, restart it
        if self._executor and old_count != self._max_workers:
            self._restart_executor()
    
    def _restart_executor(self) -> None:
        """Restart the thread pool executor with new worker count."""
        if self._executor:
            # Wait for current tasks to complete
            self._executor.shutdown(wait=True)
        
        # Create new executor
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="download_worker"
        )
    
    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Ensure thread pool executor is available."""
        if self._executor is None or self._executor._shutdown:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="download_worker"
            )
        return self._executor
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        return {
            'queue_size': self._download_queue.get_queue_size(),
            'active_downloads': len(self._active_futures),
            'max_workers': self._max_workers,
            'statistics': self._stats.copy(),
            'all_tasks': [
                {
                    'task_id': task.task_id,
                    'url': task.url,
                    'status': task.status.value,
                    'created_at': task.created_at,
                    'started_at': task.started_at,
                    'completed_at': task.completed_at
                }
                for task in self._download_queue.get_all_tasks()
            ]
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific download task."""
        with self._lock:
            if task_id in self._active_futures:
                future = self._active_futures[task_id]
                cancelled = future.cancel()
                if cancelled:
                    del self._active_futures[task_id]
                return cancelled
        return False
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the download manager and cleanup resources."""
        self._shutdown_event.set()
        
        # Cancel all pending futures
        with self._lock:
            for future in self._active_futures.values():
                future.cancel()
            self._active_futures.clear()
        
        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
        
        # Clear queue
        self._download_queue.clear_completed_tasks()
    
    def get_resumable_downloads(self) -> List[ResumeState]:
        """Get all resumable downloads."""
        return self._resume_handler.get_all_resume_states()
    
    def can_resume_download(self, url: str, config: DownloadConfig) -> bool:
        """Check if a download can be resumed."""
        return self._resume_handler.can_resume(url, config)
    
    def clear_resume_data(self, url: str) -> None:
        """Clear resume data for a specific URL."""
        self._resume_handler.clear_resume_state(url)
    
    def cleanup_old_resume_data(self, max_age_days: int = 7) -> None:
        """Clean up old resume data."""
        self._resume_handler.cleanup_old_resume_states(max_age_days)
    
    def enable_progress_bars(self, enabled: bool = True) -> None:
        """Enable or disable progress bars."""
        self._progress_reporter.enable_progress_bars = enabled
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary."""
        return self._progress_reporter.get_summary()
    
    def print_progress_summary(self) -> None:
        """Print final progress summary."""
        self._progress_reporter.print_final_summary()
    
    def set_progress_callback(self, callback: Callable[[ProgressInfo], None]) -> None:
        """Set callback function for progress updates."""
        self._progress_callback = callback
    
    def download_single(self, url: str, config: DownloadConfig) -> DownloadResult:
        """Download a single video."""
        result = DownloadResult(success=False)
        result.status = DownloadStatus.IN_PROGRESS
        
        try:
            start_time = time.time()
            
            # Create output directory
            output_dir = Path(config.output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check for resume capability
            resume_state = None
            if config.resume_downloads:
                resume_state = self._resume_handler.load_resume_state(url)
                if resume_state and not self._resume_handler.can_resume(url, config):
                    resume_state = None
            
            # Configure yt-dlp options
            ydl_opts = self._build_ydl_options(config, str(output_dir))
            
            # Set up progress hook with resume support
            ydl_opts['progress_hooks'] = [self._create_progress_hook_with_resume(url, resume_state, config)]
            
            # Configure resume options if available
            if resume_state:
                print(f"Resuming download: {resume_state.title} ({resume_state.get_resume_percentage():.1f}% completed)")
                ydl_opts['continuedl'] = True
                self._stats['resumed_downloads'] += 1
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get metadata
                info = ydl.extract_info(url, download=False)
                if not info:
                    result.mark_failure("Failed to extract video information")
                    return result
                
                # Create video metadata
                metadata = self._extract_metadata_from_info(info)
                result.video_metadata = metadata
                
                # Sanitize filename for safe file operations
                safe_title = self._sanitize_filename(info.get('title', 'video'))
                
                # Start progress tracking
                estimated_size = info.get('filesize') or info.get('filesize_approx') or 0
                self._progress_reporter.start_download(url, safe_title, estimated_size)
                
                # Download the video
                ydl.download([url])
                
                # Find the downloaded file
                video_path = self._find_downloaded_file(str(output_dir), safe_title, config.format_preference)
                
                if video_path and os.path.exists(video_path):
                    download_time = time.time() - start_time
                    result.mark_success(video_path, download_time)
                    
                    # Complete progress tracking
                    final_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
                    self._progress_reporter.complete_download(url, True, final_size)
                    
                    # Save metadata if requested
                    if config.save_metadata:
                        metadata_path = self._save_metadata(metadata, str(output_dir), safe_title)
                        result.metadata_path = metadata_path
                    
                    # Download thumbnail if requested
                    if config.save_thumbnails and metadata.thumbnail_url:
                        thumbnail_path = self._download_thumbnail(
                            metadata.thumbnail_url, str(output_dir), safe_title
                        )
                        result.thumbnail_path = thumbnail_path
                    
                    # Handle timestamp splitting if requested
                    if config.split_timestamps:
                        split_files = self._handle_timestamp_splitting(
                            video_path, metadata, str(output_dir), safe_title
                        )
                        result.split_files = split_files
                else:
                    result.mark_failure("Downloaded file not found")
                    self._progress_reporter.complete_download(url, False)
                    
        except yt_dlp.DownloadError as e:
            result.mark_failure(f"yt-dlp download error: {str(e)}")
            self._progress_reporter.complete_download(url, False)
        except Exception as e:
            result.mark_failure(f"Unexpected error: {str(e)}")
            self._progress_reporter.complete_download(url, False)
        finally:
            # Clean up progress tracking
            with self._lock:
                self._current_downloads.pop(url, None)
        
        return result
    
    def download_playlist(self, url: str, config: DownloadConfig) -> List[DownloadResult]:
        """Download all videos in a playlist with enhanced error handling."""
        results = []
        
        try:
            # Extract playlist info with more detailed options
            ydl_opts = {
                'quiet': True, 
                'extract_flat': True,
                'ignoreerrors': True,  # Continue on individual video errors
                'no_warnings': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)
                
                if not playlist_info:
                    result = DownloadResult(success=False)
                    result.mark_failure("Failed to extract playlist information - playlist may be private or deleted")
                    return [result]
                
                # Handle both playlist and channel URLs
                if 'entries' not in playlist_info:
                    # Single video URL passed instead of playlist
                    result = self.download_single(url, config)
                    return [result]
                
                # Filter out None entries (private/deleted videos)
                all_entries = playlist_info['entries'] or []
                valid_entries = [entry for entry in all_entries if entry and entry.get('url')]
                private_count = len(all_entries) - len(valid_entries)
                
                if not valid_entries:
                    result = DownloadResult(success=False)
                    result.mark_failure("No accessible videos found in playlist - all videos may be private or deleted")
                    return [result]
                
                # Log playlist information
                playlist_title = playlist_info.get('title', 'Unknown Playlist')
                playlist_uploader = playlist_info.get('uploader', 'Unknown')
                
                print(f"Playlist: {playlist_title}")
                print(f"Uploader: {playlist_uploader}")
                print(f"Total videos: {len(all_entries)}")
                print(f"Accessible videos: {len(valid_entries)}")
                if private_count > 0:
                    print(f"Private/deleted videos: {private_count}")
                
                # Create playlist folder with better naming
                safe_playlist_title = self._sanitize_filename(playlist_title)
                safe_uploader = self._sanitize_filename(playlist_uploader)
                
                # Create folder name: "Uploader - Playlist Title"
                if safe_uploader and safe_uploader.lower() != 'unknown':
                    folder_name = f"{safe_uploader} - {safe_playlist_title}"
                else:
                    folder_name = safe_playlist_title
                
                playlist_dir = Path(config.output_directory) / folder_name
                playlist_dir.mkdir(parents=True, exist_ok=True)
                
                # Save playlist metadata
                if config.save_metadata:
                    self._save_playlist_metadata(playlist_info, str(playlist_dir))
                
                # Update config for playlist directory
                playlist_config = DownloadConfig(**config.__dict__)
                playlist_config.output_directory = str(playlist_dir)
                
                # Download videos with progress tracking
                print(f"\nStarting download of {len(valid_entries)} videos...")
                
                if self._max_workers > 1 and config.max_parallel_downloads > 1:
                    results = self._download_playlist_parallel(valid_entries, playlist_config)
                else:
                    results = self._download_playlist_sequential(valid_entries, playlist_config)
                
                # Add summary
                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                
                print(f"\nPlaylist download completed:")
                print(f"  Successful: {successful}")
                print(f"  Failed: {failed}")
                print(f"  Private/deleted: {private_count}")
                
                # Print progress summary for playlist
                self._progress_reporter.print_final_summary()
                    
        except yt_dlp.DownloadError as e:
            result = DownloadResult(success=False)
            result.mark_failure(f"Playlist download error: {str(e)}")
            results = [result]
        except Exception as e:
            result = DownloadResult(success=False)
            result.mark_failure(f"Unexpected playlist processing error: {str(e)}")
            results = [result]
        
        return results
    
    def download_batch(self, urls: List[str], config: DownloadConfig) -> List[DownloadResult]:
        """Download multiple videos from a list of URLs with enhanced error handling and progress tracking."""
        results = []
        
        if not urls:
            return results
        
        print(f"Starting batch download of {len(urls)} URLs...")
        
        # Categorize URLs (single videos vs playlists)
        single_videos = []
        playlists = []
        
        for url in urls:
            if self._is_playlist_url(url):
                playlists.append(url)
            else:
                single_videos.append(url)
        
        print(f"  Single videos: {len(single_videos)}")
        print(f"  Playlists: {len(playlists)}")
        
        # Process single videos
        if single_videos:
            print(f"\nProcessing {len(single_videos)} single videos...")
            if self._max_workers > 1 and config.max_parallel_downloads > 1:
                single_results = self._download_batch_parallel(single_videos, config)
            else:
                single_results = self._download_batch_sequential(single_videos, config)
            results.extend(single_results)
        
        # Process playlists
        if playlists:
            print(f"\nProcessing {len(playlists)} playlists...")
            for i, playlist_url in enumerate(playlists, 1):
                print(f"\nPlaylist {i}/{len(playlists)}: {playlist_url}")
                playlist_results = self.download_playlist(playlist_url, config)
                results.extend(playlist_results)
        
        # Print summary
        self._print_batch_summary(results, len(single_videos), len(playlists))
        
        # Print progress summary
        self._progress_reporter.print_final_summary()
        
        return results
    
    def _download_batch_sequential(self, urls: List[str], config: DownloadConfig) -> List[DownloadResult]:
        """Download batch URLs sequentially."""
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"Downloading {i}/{len(urls)}: {url}")
            
            try:
                result = self.download_single(url, config)
                results.append(result)
                
                if result.success:
                    print(f"  ✓ Downloaded: {os.path.basename(result.video_path)}")
                    if result.split_files:
                        print(f"    Split into {len(result.split_files)} chapters")
                else:
                    print(f"  ✗ Failed: {result.error_message}")
                
                # Update progress
                if self._progress_callback:
                    batch_progress = ProgressInfo(
                        current_file=f"Video {i}",
                        progress_percent=100.0 if result.success else 0.0,
                        download_speed="",
                        eta="",
                        files_completed=i,
                        total_files=len(urls)
                    )
                    self._progress_callback(batch_progress)
                    
            except Exception as e:
                error_result = DownloadResult(success=False)
                error_result.mark_failure(f"Batch download error for {url}: {str(e)}")
                results.append(error_result)
                print(f"  ✗ Error: {str(e)}")
        
        return results
    
    def _download_batch_parallel(self, urls: List[str], config: DownloadConfig) -> List[DownloadResult]:
        """Download batch URLs in parallel using the managed thread pool."""
        results = []
        
        print(f"Starting parallel download with {self._max_workers} workers...")
        
        executor = self._ensure_executor()
        
        # Submit all tasks to the queue and executor
        future_to_info = {}
        for i, url in enumerate(urls):
            task_id = self._download_queue.add_task(url, config)
            future = executor.submit(self._execute_download_task, task_id)
            future_to_info[future] = (i, url, task_id)
            
            with self._lock:
                self._active_futures[task_id] = future
        
        completed = 0
        for future in as_completed(future_to_info.keys()):
            i, url, task_id = future_to_info[future]
            completed += 1
            
            # Remove from active futures
            with self._lock:
                self._active_futures.pop(task_id, None)
            
            try:
                result = future.result()
                results.append((i, result))
                
                # Update statistics
                self._update_statistics(result)
                
                if result.success:
                    print(f"  ✓ [{completed}/{len(urls)}] Downloaded: {os.path.basename(result.video_path)}")
                    if result.split_files:
                        print(f"    Split into {len(result.split_files)} chapters")
                else:
                    print(f"  ✗ [{completed}/{len(urls)}] Failed: {url} - {result.error_message}")
                    
            except Exception as e:
                error_result = DownloadResult(success=False)
                error_result.mark_failure(f"Batch download error for {url}: {str(e)}")
                results.append((i, error_result))
                print(f"  ✗ [{completed}/{len(urls)}] Error: {url} - {str(e)}")
                self._update_statistics(error_result)
            
            # Update progress
            if self._progress_callback:
                batch_progress = ProgressInfo(
                    current_file=f"Video {i+1}",
                    progress_percent=100.0,
                    download_speed="",
                    eta="",
                    files_completed=completed,
                    total_files=len(urls)
                )
                self._progress_callback(batch_progress)
        
        # Sort results by original order and return just the results
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]
    
    def _execute_download_task(self, task_id: str) -> DownloadResult:
        """Execute a download task from the queue."""
        # Get task from queue (this should be immediate since we just added it)
        task = None
        with self._lock:
            all_tasks = self._download_queue.get_all_tasks()
            for t in all_tasks:
                if t.task_id == task_id:
                    task = t
                    break
        
        if not task:
            result = DownloadResult(success=False)
            result.mark_failure("Task not found in queue")
            return result
        
        try:
            # Execute the actual download
            result = self.download_single(task.url, task.config)
            
            # Mark task as completed
            self._download_queue.complete_task(task_id, result)
            
            return result
            
        except Exception as e:
            error_result = DownloadResult(success=False)
            error_result.mark_failure(f"Task execution error: {str(e)}")
            self._download_queue.complete_task(task_id, error_result)
            return error_result
    
    def _update_statistics(self, result: DownloadResult) -> None:
        """Update download statistics."""
        with self._lock:
            self._stats['total_downloads'] += 1
            
            if result.success:
                self._stats['successful_downloads'] += 1
                self._stats['total_download_time'] += result.download_time
            else:
                self._stats['failed_downloads'] += 1
            
            # Calculate average download time
            if self._stats['successful_downloads'] > 0:
                self._stats['average_download_time'] = (
                    self._stats['total_download_time'] / self._stats['successful_downloads']
                )
    
    def _is_playlist_url(self, url: str) -> bool:
        """Check if URL is a playlist URL."""
        return 'playlist' in url.lower() or 'list=' in url.lower() or '/c/' in url or '/channel/' in url or '/user/' in url
    
    def _print_batch_summary(self, results: List[DownloadResult], single_count: int, playlist_count: int) -> None:
        """Print summary of batch download results."""
        total_downloads = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total_downloads - successful
        total_split_files = sum(len(r.split_files) for r in results)
        
        print(f"\n{'='*50}")
        print("BATCH DOWNLOAD SUMMARY")
        print(f"{'='*50}")
        print(f"Single videos processed: {single_count}")
        print(f"Playlists processed: {playlist_count}")
        print(f"Total downloads attempted: {total_downloads}")
        print(f"Successful downloads: {successful}")
        print(f"Failed downloads: {failed}")
        if total_split_files > 0:
            print(f"Total split files created: {total_split_files}")
        print(f"{'='*50}")
    
    def _build_ydl_options(self, config: DownloadConfig, output_dir: str) -> Dict[str, Any]:
        """Build yt-dlp options from configuration."""
        opts = {
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'format': self._build_format_selector(config),
            'writeinfojson': False,  # We handle metadata separately
            'writethumbnail': False,  # We handle thumbnails separately
            'ignoreerrors': False,
            'no_warnings': False,
            'extractaudio': False,  # We handle audio extraction in quality selector
        }
        
        # Add retry configuration
        if config.retry_attempts > 0:
            opts['retries'] = config.retry_attempts
        
        # Add resume configuration
        if config.resume_downloads:
            opts['continuedl'] = True
            opts['part'] = True  # Use .part files for partial downloads
        
        return opts
    
    def _build_format_selector(self, config: DownloadConfig) -> str:
        """Build format selector string for yt-dlp."""
        if config.quality == 'best':
            return 'best[ext=mp4]/best'
        elif config.quality == 'worst':
            return 'worst[ext=mp4]/worst'
        elif config.quality.endswith('p'):
            # Specific resolution like 720p, 1080p
            height = config.quality[:-1]
            return f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
        else:
            return 'best[ext=mp4]/best'
    
    def _create_progress_hook(self, url: str) -> Callable[[Dict[str, Any]], None]:
        """Create progress hook for yt-dlp."""
        return self._create_progress_hook_with_resume(url, None)
    
    def _create_progress_hook_with_resume(self, url: str, resume_state: Optional[ResumeState], config: DownloadConfig) -> Callable[[Dict[str, Any]], None]:
        """Create progress hook for yt-dlp with resume support."""
        def progress_hook(d: Dict[str, Any]) -> None:
            if d['status'] == 'downloading':
                filename = d.get('filename', 'Unknown')
                
                # Calculate progress percentage
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                
                if total_bytes:
                    progress = (downloaded_bytes / total_bytes) * 100
                else:
                    progress = 0.0
                
                # Format speed and ETA
                speed = d.get('speed', 0)
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "Unknown"
                
                eta = d.get('eta', 0)
                eta_str = f"{eta}s" if eta else "Unknown"
                
                # Create progress info
                progress_info = ProgressInfo(
                    current_file=os.path.basename(filename),
                    progress_percent=progress,
                    download_speed=speed_str,
                    eta=eta_str,
                    files_completed=0,
                    total_files=1,
                    current_file_size=total_bytes,
                    total_downloaded=downloaded_bytes
                )
                
                # Update tracking and call callback
                with self._lock:
                    self._current_downloads[url] = progress_info
                
                # Update progress reporter
                self._progress_reporter.update_download(
                    url=url,
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_bytes,
                    speed=speed_str,
                    eta=eta_str,
                    status="downloading"
                )
                
                if self._progress_callback:
                    self._progress_callback(progress_info)
                
                # Save resume state periodically (every 5% progress or 10MB)
                if total_bytes > 0 and downloaded_bytes > 0:
                    should_save = False
                    
                    # Save every 5% progress
                    if progress % 5 < 1:
                        should_save = True
                    
                    # Save every 10MB
                    if downloaded_bytes % (10 * 1024 * 1024) < 1024 * 1024:
                        should_save = True
                    
                    if should_save:
                        try:
                            # Extract video info for resume state
                            video_id = d.get('info_dict', {}).get('id', 'unknown')
                            title = d.get('info_dict', {}).get('title', 'Unknown')
                            
                            self._resume_handler.save_resume_state(
                                url=url,
                                video_id=video_id,
                                title=title,
                                output_path=filename,
                                partial_file_path=filename + '.part' if not filename.endswith('.part') else filename,
                                downloaded_bytes=downloaded_bytes,
                                total_bytes=total_bytes,
                                config=config,
                                metadata=d.get('info_dict')
                            )
                        except Exception as e:
                            # Don't fail download if resume state saving fails
                            pass
            
            elif d['status'] == 'finished':
                # Clear resume state on successful completion
                self._resume_handler.clear_resume_state(url)
            
            elif d['status'] == 'error':
                # Keep resume state on error for potential retry
                pass
        
        return progress_hook
    
    def _download_playlist_sequential(self, entries: List[Dict[str, Any]], config: DownloadConfig) -> List[DownloadResult]:
        """Download playlist videos sequentially with enhanced error handling."""
        results = []
        
        for i, entry in enumerate(entries):
            if not entry or not entry.get('url'):
                # Create a skipped result for missing entries
                error_result = DownloadResult(success=False)
                error_result.mark_failure("Video entry is missing or private")
                error_result.status = DownloadStatus.SKIPPED
                results.append(error_result)
                continue
            
            video_title = entry.get('title', f'Video {i+1}')
            print(f"Downloading {i+1}/{len(entries)}: {video_title}")
                
            try:
                result = self.download_single(entry['url'], config)
                results.append(result)
                
                # Show result
                if result.success:
                    print(f"  ✓ Downloaded: {os.path.basename(result.video_path)}")
                    if result.split_files:
                        print(f"    Split into {len(result.split_files)} chapters")
                else:
                    print(f"  ✗ Failed: {result.error_message}")
                
                # Update progress for playlist
                if self._progress_callback:
                    playlist_progress = ProgressInfo(
                        current_file=video_title,
                        progress_percent=100.0 if result.success else 0.0,
                        download_speed="",
                        eta="",
                        files_completed=i + 1,
                        total_files=len(entries)
                    )
                    self._progress_callback(playlist_progress)
                    
            except Exception as e:
                error_result = DownloadResult(success=False)
                error_result.mark_failure(f"Error downloading {video_title}: {str(e)}")
                results.append(error_result)
                print(f"  ✗ Error: {str(e)}")
        
        return results
    
    def _download_playlist_parallel(self, entries: List[Dict[str, Any]], config: DownloadConfig) -> List[DownloadResult]:
        """Download playlist videos in parallel using the managed thread pool."""
        results = []
        
        # Filter valid entries and create mapping
        valid_entries = [(i, entry) for i, entry in enumerate(entries) if entry and entry.get('url')]
        
        if not valid_entries:
            return results
        
        print(f"Starting parallel download with {self._max_workers} workers...")
        
        executor = self._ensure_executor()
        
        # Submit all tasks to the queue and executor
        future_to_entry = {}
        for i, entry in valid_entries:
            task_id = self._download_queue.add_task(entry['url'], config)
            future = executor.submit(self._execute_download_task, task_id)
            future_to_entry[future] = (i, entry, task_id)
            
            with self._lock:
                self._active_futures[task_id] = future
        
        completed = 0
        for future in as_completed(future_to_entry.keys()):
            i, entry, task_id = future_to_entry[future]
            completed += 1
            video_title = entry.get('title', f'Video {i+1}')
            
            # Remove from active futures
            with self._lock:
                self._active_futures.pop(task_id, None)
            
            try:
                result = future.result()
                results.append((i, result))
                
                # Update statistics
                self._update_statistics(result)
                
                # Show result
                if result.success:
                    print(f"  ✓ [{completed}/{len(valid_entries)}] Downloaded: {video_title}")
                    if result.split_files:
                        print(f"    Split into {len(result.split_files)} chapters")
                else:
                    print(f"  ✗ [{completed}/{len(valid_entries)}] Failed: {video_title} - {result.error_message}")
                    
            except Exception as e:
                error_result = DownloadResult(success=False)
                error_result.mark_failure(f"Error downloading {video_title}: {str(e)}")
                results.append((i, error_result))
                print(f"  ✗ [{completed}/{len(valid_entries)}] Error: {video_title} - {str(e)}")
                self._update_statistics(error_result)
            
            # Update progress for playlist
            if self._progress_callback:
                playlist_progress = ProgressInfo(
                    current_file=video_title,
                    progress_percent=100.0,
                    download_speed="",
                    eta="",
                    files_completed=completed,
                    total_files=len(valid_entries)
                )
                self._progress_callback(playlist_progress)
        
        # Sort results by original order and return just the results
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]
    
    def _extract_metadata_from_info(self, info: Dict[str, Any]) -> VideoMetadata:
        """Extract VideoMetadata from yt-dlp info dict."""
        return VideoMetadata(
            title=info.get('title', 'Unknown'),
            uploader=info.get('uploader', 'Unknown'),
            description=info.get('description', ''),
            upload_date=info.get('upload_date', ''),
            duration=float(info.get('duration', 0)),
            view_count=int(info.get('view_count', 0)),
            thumbnail_url=info.get('thumbnail', ''),
            video_id=info.get('id', ''),
            webpage_url=info.get('webpage_url', ''),
            tags=info.get('tags', []) or [],
            categories=info.get('categories', []) or [],
            like_count=info.get('like_count'),
            dislike_count=info.get('dislike_count')
        )
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file operations."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length and strip whitespace
        filename = filename.strip()[:200]
        
        return filename or 'video'
    
    def _find_downloaded_file(self, output_dir: str, title: str, format_preference: str) -> Optional[str]:
        """Find the downloaded video file."""
        # Common video extensions
        extensions = ['mp4', 'webm', 'mkv', 'avi', 'mov']
        
        # Try exact title match first
        for ext in extensions:
            file_path = os.path.join(output_dir, f"{title}.{ext}")
            if os.path.exists(file_path):
                return file_path
        
        # Try finding any video file with similar name
        try:
            for file in os.listdir(output_dir):
                if any(file.endswith(f".{ext}") for ext in extensions):
                    if title.lower() in file.lower():
                        return os.path.join(output_dir, file)
        except OSError:
            pass
        
        return None
    
    def _save_metadata(self, metadata: VideoMetadata, output_dir: str, title: str) -> str:
        """Save metadata to JSON file."""
        metadata_path = os.path.join(output_dir, f"{title}.info.json")
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
            return metadata_path
        except Exception as e:
            # If we can't save metadata, don't fail the entire download
            print(f"Warning: Could not save metadata: {e}")
            return ""
    
    def _save_playlist_metadata(self, playlist_info: Dict[str, Any], output_dir: str) -> str:
        """Save playlist metadata to JSON file."""
        metadata_path = os.path.join(output_dir, "playlist.info.json")
        
        try:
            # Extract relevant playlist information
            playlist_metadata = {
                'title': playlist_info.get('title', 'Unknown Playlist'),
                'uploader': playlist_info.get('uploader', 'Unknown'),
                'uploader_id': playlist_info.get('uploader_id', ''),
                'description': playlist_info.get('description', ''),
                'playlist_count': playlist_info.get('playlist_count', 0),
                'webpage_url': playlist_info.get('webpage_url', ''),
                'id': playlist_info.get('id', ''),
                'entries_count': len(playlist_info.get('entries', [])),
                'accessible_entries': len([e for e in playlist_info.get('entries', []) if e and e.get('url')]),
                'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(playlist_metadata, f, indent=2, ensure_ascii=False)
            return metadata_path
        except Exception as e:
            print(f"Warning: Could not save playlist metadata: {e}")
            return ""
    
    def _download_thumbnail(self, thumbnail_url: str, output_dir: str, title: str) -> str:
        """Download and save video thumbnail."""
        if not thumbnail_url:
            return ""
        
        try:
            import requests
            
            response = requests.get(thumbnail_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension from URL or content type
            ext = 'jpg'
            if 'content-type' in response.headers:
                content_type = response.headers['content-type']
                if 'png' in content_type:
                    ext = 'png'
                elif 'webp' in content_type:
                    ext = 'webp'
            
            thumbnail_path = os.path.join(output_dir, f"{title}.{ext}")
            
            with open(thumbnail_path, 'wb') as f:
                f.write(response.content)
            
            return thumbnail_path
            
        except Exception as e:
            # If we can't download thumbnail, don't fail the entire download
            print(f"Warning: Could not download thumbnail: {e}")
            return ""
    
    def _handle_timestamp_splitting(self, video_path: str, metadata: VideoMetadata, 
                                  output_dir: str, safe_title: str) -> List[str]:
        """
        Handle timestamp-based video splitting.
        
        Args:
            video_path: Path to the downloaded video file
            metadata: Video metadata containing description
            output_dir: Output directory for split files
            safe_title: Sanitized video title
            
        Returns:
            List of paths to split video files
        """
        try:
            # Parse timestamps from video description
            timestamps = self._timestamp_parser.parse_description(metadata.description)
            
            if not timestamps:
                print(f"No timestamps found in video description for: {safe_title}")
                return []
            
            # Validate timestamps
            if not self._timestamp_parser.validate_timestamps(timestamps):
                print(f"Invalid timestamps found in video description for: {safe_title}")
                return []
            
            print(f"Found {len(timestamps)} timestamps, splitting video: {safe_title}")
            
            # Create chapters subdirectory
            chapters_dir = os.path.join(output_dir, f"{safe_title}_chapters")
            
            # Check if FFmpeg is available
            if not self._video_splitter.validate_ffmpeg_availability():
                print("Warning: FFmpeg not available, skipping video splitting")
                return []
            
            # Split the video
            split_files = self._video_splitter.split_video(
                video_path=video_path,
                timestamps=timestamps,
                output_dir=chapters_dir
            )
            
            print(f"Successfully split video into {len(split_files)} chapters")
            return split_files
            
        except Exception as e:
            print(f"Error during timestamp splitting: {e}")
            return []
    
    def get_splitting_preview(self, url: str) -> dict:
        """
        Get a preview of timestamp splitting without downloading.
        
        Args:
            url: Video URL
            
        Returns:
            Dictionary with splitting preview information
        """
        try:
            # Extract info without downloading
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return {'error': 'Failed to extract video information'}
                
                # Extract metadata
                metadata = self._extract_metadata_from_info(info)
                
                # Parse timestamps
                timestamps = self._timestamp_parser.parse_description(metadata.description)
                
                # Get statistics
                stats = self._timestamp_parser.get_timestamp_statistics(timestamps)
                
                return {
                    'title': metadata.title,
                    'duration': metadata.duration,
                    'timestamps_found': len(timestamps),
                    'timestamps': [
                        {
                            'time': ts.format_time(),
                            'label': ts.label,
                            'seconds': ts.time_seconds
                        }
                        for ts in timestamps
                    ],
                    'statistics': stats,
                    'ffmpeg_available': self._video_splitter.validate_ffmpeg_availability()
                }
                
        except Exception as e:
            return {'error': f'Error getting splitting preview: {str(e)}'}
    
    def prompt_user_for_splitting(self, url: str) -> bool:
        """
        Prompt user whether to split video based on timestamps.
        
        Args:
            url: Video URL
            
        Returns:
            True if user wants to split, False otherwise
        """
        preview = self.get_splitting_preview(url)
        
        if 'error' in preview:
            print(f"Error: {preview['error']}")
            return False
        
        if preview['timestamps_found'] == 0:
            print("No timestamps found in video description.")
            return False
        
        if not preview['ffmpeg_available']:
            print("FFmpeg is not available. Video splitting is not possible.")
            return False
        
        # Display preview information
        print(f"\nVideo: {preview['title']}")
        print(f"Duration: {preview['duration']:.0f} seconds")
        print(f"Found {preview['timestamps_found']} timestamps:")
        
        for i, ts in enumerate(preview['timestamps'][:5], 1):  # Show first 5
            print(f"  {i}. {ts['time']} - {ts['label']}")
        
        if len(preview['timestamps']) > 5:
            print(f"  ... and {len(preview['timestamps']) - 5} more")
        
        # Prompt user
        while True:
            response = input("\nSplit video into chapters? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")