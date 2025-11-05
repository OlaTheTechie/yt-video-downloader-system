"""
Error handling framework for the YouTube Video Downloader application.
"""

import logging
import time
from enum import Enum
from typing import Optional, Callable, Any, Dict
from functools import wraps


class ErrorType(Enum):
    """Types of errors that can occur in the application."""
    NETWORK_ERROR = "network_error"
    CONTENT_ERROR = "content_error"
    FILESYSTEM_ERROR = "filesystem_error"
    PROCESSING_ERROR = "processing_error"
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class YouTubeDownloaderError(Exception):
    """Base exception class for YouTube Downloader errors."""
    
    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.PROCESSING_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            'message': self.message,
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'details': self.details,
            'timestamp': self.timestamp,
            'original_exception': str(self.original_exception) if self.original_exception else None
        }


class NetworkError(YouTubeDownloaderError):
    """Error related to network operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.NETWORK_ERROR, **kwargs)


class ContentError(YouTubeDownloaderError):
    """Error related to video content (private, deleted, geo-blocked, etc.)."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.CONTENT_ERROR, **kwargs)


class FileSystemError(YouTubeDownloaderError):
    """Error related to file system operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.FILESYSTEM_ERROR, **kwargs)


class ProcessingError(YouTubeDownloaderError):
    """Error related to video processing operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.PROCESSING_ERROR, **kwargs)


class ConfigurationError(YouTubeDownloaderError):
    """Error related to configuration issues."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.CONFIGURATION_ERROR, **kwargs)


class ValidationError(YouTubeDownloaderError):
    """Error related to input validation."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.VALIDATION_ERROR, **kwargs)


class GeoRestrictedError(ContentError):
    """Error for geo-restricted content."""
    
    def __init__(self, message: str, country_code: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.country_code = country_code
        self.details['country_code'] = country_code
        self.details['suggested_solution'] = "Consider using a VPN or proxy service"


class AgeRestrictedError(ContentError):
    """Error for age-restricted content."""
    
    def __init__(self, message: str, age_limit: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.age_limit = age_limit
        self.details['age_limit'] = age_limit
        self.details['suggested_solution'] = "Authentication may be required for age-restricted content"


class PrivateVideoError(ContentError):
    """Error for private or deleted videos."""
    
    def __init__(self, message: str, video_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.video_id = video_id
        self.details['video_id'] = video_id
        self.details['suggested_solution'] = "Video may be private, deleted, or unavailable"


class RateLimitError(NetworkError):
    """Error for rate limiting."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        self.details['retry_after'] = retry_after
        self.details['suggested_solution'] = f"Wait {retry_after} seconds before retrying" if retry_after else "Reduce request frequency"


class ErrorHandler:
    """Centralized error handling and recovery mechanisms."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_counts: Dict[str, int] = {}
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay for exponential backoff
        self.max_delay = 60.0  # Maximum delay for exponential backoff
        self.jitter_factor = 0.1  # Add randomness to prevent thundering herd
    
    def handle_error(
        self,
        error: Exception,
        context: str = "",
        retry_count: int = 0
    ) -> bool:
        """
        Handle an error and determine if operation should be retried.
        
        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            retry_count: Current retry attempt number
            
        Returns:
            True if operation should be retried, False otherwise
        """
        error_key = f"{type(error).__name__}:{context}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log the error
        self.logger.error(
            f"Error in {context}: {str(error)}",
            extra={
                'error_type': type(error).__name__,
                'retry_count': retry_count,
                'context': context
            }
        )
        
        # Determine if we should retry based on error type
        if isinstance(error, RateLimitError):
            return self._should_retry_rate_limit_error(error, retry_count)
        elif isinstance(error, NetworkError):
            return self._should_retry_network_error(error, retry_count)
        elif isinstance(error, (GeoRestrictedError, AgeRestrictedError, PrivateVideoError)):
            return False  # Don't retry specific content errors
        elif isinstance(error, ContentError):
            return self._should_retry_content_error(error, retry_count)
        elif isinstance(error, FileSystemError):
            return self._should_retry_filesystem_error(error, retry_count)
        elif isinstance(error, ProcessingError):
            return self._should_retry_processing_error(error, retry_count)
        else:
            return retry_count < self.max_retries
    
    def _should_retry_network_error(self, error: NetworkError, retry_count: int) -> bool:
        """Determine if network error should be retried."""
        if retry_count >= self.max_retries:
            return False
        
        # Retry on timeout, connection errors, but not on 404, 403, etc.
        retryable_keywords = ['timeout', 'connection', 'network', 'dns']
        error_message = str(error).lower()
        return any(keyword in error_message for keyword in retryable_keywords)
    
    def _should_retry_filesystem_error(self, error: FileSystemError, retry_count: int) -> bool:
        """Determine if filesystem error should be retried."""
        if retry_count >= self.max_retries:
            return False
        
        # Retry on temporary filesystem issues
        retryable_keywords = ['busy', 'locked', 'temporary']
        error_message = str(error).lower()
        return any(keyword in error_message for keyword in retryable_keywords)
    
    def _should_retry_processing_error(self, error: ProcessingError, retry_count: int) -> bool:
        """Determine if processing error should be retried."""
        return retry_count < 1  # Only retry processing errors once
    
    def _should_retry_rate_limit_error(self, error: RateLimitError, retry_count: int) -> bool:
        """Determine if rate limit error should be retried."""
        if retry_count >= self.max_retries:
            return False
        
        # Always retry rate limit errors with appropriate delay
        return True
    
    def _should_retry_content_error(self, error: ContentError, retry_count: int) -> bool:
        """Determine if general content error should be retried."""
        if retry_count >= 1:  # Only retry content errors once
            return False
        
        # Retry on temporary content issues
        retryable_keywords = ['temporary', 'unavailable', 'server error', '5xx']
        error_message = str(error).lower()
        return any(keyword in error_message for keyword in retryable_keywords)
    
    def get_retry_delay(self, retry_count: int, error: Optional[Exception] = None) -> float:
        """Calculate delay before retry using exponential backoff with jitter."""
        import random
        
        # Handle rate limit errors with specific delay
        if isinstance(error, RateLimitError) and error.retry_after:
            return float(error.retry_after)
        
        # Calculate exponential backoff delay
        delay = self.base_delay * (2 ** retry_count)
        
        # Cap at maximum delay
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = delay * self.jitter_factor * random.random()
        
        return delay + jitter
    
    def reset_error_counts(self) -> None:
        """Reset error counters."""
        self.error_counts.clear()
    
    def classify_yt_dlp_error(self, error: Exception) -> YouTubeDownloaderError:
        """
        Classify yt-dlp errors into our custom error types.
        
        Args:
            error: The original yt-dlp error
            
        Returns:
            Classified custom error
        """
        error_message = str(error).lower()
        
        # Geo-restriction errors
        if any(keyword in error_message for keyword in [
            'geo', 'country', 'region', 'location', 'not available in your country',
            'blocked in your country', 'geographic'
        ]):
            return GeoRestrictedError(
                f"Content is geo-restricted: {str(error)}",
                original_exception=error
            )
        
        # Age-restriction errors
        if any(keyword in error_message for keyword in [
            'age', 'sign in', 'login', 'account', 'restricted', 'mature'
        ]):
            return AgeRestrictedError(
                f"Content is age-restricted: {str(error)}",
                original_exception=error
            )
        
        # Private/deleted video errors
        if any(keyword in error_message for keyword in [
            'private', 'deleted', 'removed', 'unavailable', 'not found',
            '404', 'does not exist'
        ]):
            return PrivateVideoError(
                f"Video is private or deleted: {str(error)}",
                original_exception=error
            )
        
        # Rate limiting errors
        if any(keyword in error_message for keyword in [
            'rate limit', 'too many requests', '429', 'quota', 'throttle'
        ]):
            # Try to extract retry-after value
            import re
            retry_match = re.search(r'retry.*?(\d+)', error_message)
            retry_after = int(retry_match.group(1)) if retry_match else None
            
            return RateLimitError(
                f"Rate limited: {str(error)}",
                retry_after=retry_after,
                original_exception=error
            )
        
        # Network errors
        if any(keyword in error_message for keyword in [
            'network', 'connection', 'timeout', 'dns', 'resolve',
            'unreachable', 'refused', 'reset'
        ]):
            return NetworkError(
                f"Network error: {str(error)}",
                original_exception=error
            )
        
        # Processing errors (FFmpeg, format issues, etc.)
        if any(keyword in error_message for keyword in [
            'ffmpeg', 'format', 'codec', 'conversion', 'processing'
        ]):
            return ProcessingError(
                f"Processing error: {str(error)}",
                original_exception=error
            )
        
        # Default to generic content error
        return ContentError(
            f"Content error: {str(error)}",
            original_exception=error
        )
    
    def handle_graceful_degradation(self, error: Exception, operation: str, fallback_action: Optional[Callable] = None) -> Any:
        """
        Handle graceful degradation for non-critical operations.
        
        Args:
            error: The error that occurred
            operation: Description of the operation that failed
            fallback_action: Optional fallback function to execute
            
        Returns:
            Result of fallback action or None
        """
        self.logger.warning(
            f"Non-critical operation failed: {operation} - {str(error)}",
            extra={'operation': operation, 'error_type': type(error).__name__}
        )
        
        if fallback_action:
            try:
                return fallback_action()
            except Exception as fallback_error:
                self.logger.warning(
                    f"Fallback action also failed for {operation}: {str(fallback_error)}"
                )
        
        return None


def with_error_handling(
    error_handler: Optional[ErrorHandler] = None,
    context: str = "",
    max_retries: int = 3
):
    """
    Decorator for automatic error handling and retry logic.
    
    Args:
        error_handler: ErrorHandler instance to use
        context: Context string for error logging
        max_retries: Maximum number of retry attempts
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler()
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Classify the error if it's from yt-dlp
                    classified_error = e
                    if ('yt_dlp' in str(type(e)) or 'youtube_dl' in str(type(e)) or 
                        (hasattr(e, '__module__') and e.__module__ and 'yt_dlp' in e.__module__)):
                        classified_error = handler.classify_yt_dlp_error(e)
                    
                    if not handler.handle_error(classified_error, context or func.__name__, retry_count):
                        raise classified_error
                    
                    if retry_count < max_retries:
                        delay = handler.get_retry_delay(retry_count, classified_error)
                        handler.logger.info(f"Retrying in {delay:.1f} seconds (attempt {retry_count + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        retry_count += 1
                    else:
                        raise classified_error
            
            return None  # Should never reach here
        return wrapper
    return decorator