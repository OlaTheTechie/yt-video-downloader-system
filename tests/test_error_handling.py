"""
Unit tests for error handling framework.
"""

import pytest
import time
import logging
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from config.error_handling import (
    ErrorHandler, YouTubeDownloaderError, NetworkError, ContentError,
    FileSystemError, ProcessingError, GeoRestrictedError, AgeRestrictedError,
    PrivateVideoError, RateLimitError, with_error_handling
)


class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(logger=self.mock_logger)
    
    def test_initialization(self):
        """Test ErrorHandler initialization."""
        assert self.error_handler.max_retries == 3
        assert self.error_handler.base_delay == 1.0
        assert self.error_handler.max_delay == 60.0
        assert self.error_handler.jitter_factor == 0.1
        assert isinstance(self.error_handler.error_counts, dict)
    
    def test_get_retry_delay_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        # Test basic exponential backoff
        delay_0 = self.error_handler.get_retry_delay(0)
        delay_1 = self.error_handler.get_retry_delay(1)
        delay_2 = self.error_handler.get_retry_delay(2)
        
        # Should increase exponentially (with jitter)
        assert 1.0 <= delay_0 <= 1.2  # 1.0 + 10% jitter
        assert 2.0 <= delay_1 <= 2.4  # 2.0 + 10% jitter
        assert 4.0 <= delay_2 <= 4.8  # 4.0 + 10% jitter
    
    def test_get_retry_delay_max_cap(self):
        """Test that retry delay is capped at maximum."""
        # Test with high retry count
        delay = self.error_handler.get_retry_delay(10)
        assert delay <= self.error_handler.max_delay * 1.1  # Max + jitter
    
    def test_get_retry_delay_rate_limit_error(self):
        """Test retry delay for rate limit errors."""
        rate_limit_error = RateLimitError("Rate limited", retry_after=30)
        delay = self.error_handler.get_retry_delay(1, rate_limit_error)
        assert delay == 30.0
    
    def test_handle_network_error_retry(self):
        """Test network error retry logic."""
        network_error = NetworkError("Connection timeout")
        
        # Should retry network errors
        should_retry = self.error_handler.handle_error(network_error, "test_context", 0)
        assert should_retry is True
        
        # Should not retry after max attempts
        should_retry = self.error_handler.handle_error(network_error, "test_context", 3)
        assert should_retry is False
    
    def test_handle_content_error_no_retry(self):
        """Test content error no-retry logic."""
        geo_error = GeoRestrictedError("Geo-blocked content")
        age_error = AgeRestrictedError("Age-restricted content")
        private_error = PrivateVideoError("Private video")
        
        # Should not retry specific content errors
        assert self.error_handler.handle_error(geo_error, "test", 0) is False
        assert self.error_handler.handle_error(age_error, "test", 0) is False
        assert self.error_handler.handle_error(private_error, "test", 0) is False
    
    def test_handle_rate_limit_error_retry(self):
        """Test rate limit error retry logic."""
        rate_limit_error = RateLimitError("Too many requests", retry_after=60)
        
        # Should retry rate limit errors
        should_retry = self.error_handler.handle_error(rate_limit_error, "test", 0)
        assert should_retry is True
        
        # Should retry up to max attempts
        should_retry = self.error_handler.handle_error(rate_limit_error, "test", 2)
        assert should_retry is True
        
        # Should not retry after max attempts
        should_retry = self.error_handler.handle_error(rate_limit_error, "test", 3)
        assert should_retry is False
    
    def test_classify_yt_dlp_error_geo_restriction(self):
        """Test classification of geo-restriction errors."""
        mock_error = Exception("Video not available in your country")
        classified = self.error_handler.classify_yt_dlp_error(mock_error)
        
        assert isinstance(classified, GeoRestrictedError)
        assert "geo-restricted" in str(classified).lower()
    
    def test_classify_yt_dlp_error_age_restriction(self):
        """Test classification of age-restriction errors."""
        mock_error = Exception("Sign in to confirm your age")
        classified = self.error_handler.classify_yt_dlp_error(mock_error)
        
        assert isinstance(classified, AgeRestrictedError)
        assert "age-restricted" in str(classified).lower()
    
    def test_classify_yt_dlp_error_private_video(self):
        """Test classification of private video errors."""
        mock_error = Exception("Video is private")
        classified = self.error_handler.classify_yt_dlp_error(mock_error)
        
        assert isinstance(classified, PrivateVideoError)
        assert "private or deleted" in str(classified).lower()
    
    def test_classify_yt_dlp_error_rate_limit(self):
        """Test classification of rate limit errors."""
        mock_error = Exception("Too many requests, retry after 30 seconds")
        classified = self.error_handler.classify_yt_dlp_error(mock_error)
        
        assert isinstance(classified, RateLimitError)
        assert classified.retry_after == 30
    
    def test_classify_yt_dlp_error_network(self):
        """Test classification of network errors."""
        mock_error = Exception("Connection timeout")
        classified = self.error_handler.classify_yt_dlp_error(mock_error)
        
        assert isinstance(classified, NetworkError)
        assert "network error" in str(classified).lower()
    
    def test_handle_graceful_degradation(self):
        """Test graceful degradation handling."""
        mock_error = Exception("Non-critical error")
        
        # Test without fallback
        result = self.error_handler.handle_graceful_degradation(
            mock_error, "test_operation"
        )
        assert result is None
        self.mock_logger.warning.assert_called()
        
        # Test with fallback
        fallback_result = "fallback_value"
        fallback_action = Mock(return_value=fallback_result)
        
        result = self.error_handler.handle_graceful_degradation(
            mock_error, "test_operation", fallback_action
        )
        assert result == fallback_result
        fallback_action.assert_called_once()
    
    def test_handle_graceful_degradation_fallback_fails(self):
        """Test graceful degradation when fallback also fails."""
        mock_error = Exception("Non-critical error")
        fallback_error = Exception("Fallback failed")
        fallback_action = Mock(side_effect=fallback_error)
        
        result = self.error_handler.handle_graceful_degradation(
            mock_error, "test_operation", fallback_action
        )
        assert result is None
        
        # Should log both the original error and fallback failure
        assert self.mock_logger.warning.call_count == 2
    
    def test_error_counts_tracking(self):
        """Test error count tracking."""
        error = NetworkError("Test error")
        context = "test_context"
        
        # First occurrence
        self.error_handler.handle_error(error, context, 0)
        assert f"{type(error).__name__}:{context}" in self.error_handler.error_counts
        assert self.error_handler.error_counts[f"{type(error).__name__}:{context}"] == 1
        
        # Second occurrence
        self.error_handler.handle_error(error, context, 0)
        assert self.error_handler.error_counts[f"{type(error).__name__}:{context}"] == 2
    
    def test_reset_error_counts(self):
        """Test resetting error counts."""
        error = NetworkError("Test error")
        self.error_handler.handle_error(error, "test", 0)
        
        assert len(self.error_handler.error_counts) > 0
        
        self.error_handler.reset_error_counts()
        assert len(self.error_handler.error_counts) == 0


class TestCustomErrors:
    """Test cases for custom error classes."""
    
    def test_youtube_downloader_error_base(self):
        """Test base YouTubeDownloaderError class."""
        error = YouTubeDownloaderError(
            "Test error",
            details={"key": "value"},
            original_exception=ValueError("Original")
        )
        
        assert str(error) == "Test error"
        assert error.details["key"] == "value"
        assert isinstance(error.original_exception, ValueError)
        assert error.timestamp > 0
        
        # Test to_dict method
        error_dict = error.to_dict()
        assert error_dict["message"] == "Test error"
        assert error_dict["details"]["key"] == "value"
        assert "timestamp" in error_dict
    
    def test_geo_restricted_error(self):
        """Test GeoRestrictedError class."""
        error = GeoRestrictedError("Geo-blocked", country_code="US")
        
        assert isinstance(error, ContentError)
        assert error.country_code == "US"
        assert error.details["country_code"] == "US"
        assert "VPN" in error.details["suggested_solution"]
    
    def test_age_restricted_error(self):
        """Test AgeRestrictedError class."""
        error = AgeRestrictedError("Age-restricted", age_limit=18)
        
        assert isinstance(error, ContentError)
        assert error.age_limit == 18
        assert error.details["age_limit"] == 18
        assert "authentication" in error.details["suggested_solution"].lower()
    
    def test_private_video_error(self):
        """Test PrivateVideoError class."""
        error = PrivateVideoError("Private video", video_id="abc123")
        
        assert isinstance(error, ContentError)
        assert error.video_id == "abc123"
        assert error.details["video_id"] == "abc123"
        assert "private" in error.details["suggested_solution"].lower()
    
    def test_rate_limit_error(self):
        """Test RateLimitError class."""
        error = RateLimitError("Rate limited", retry_after=30)
        
        assert isinstance(error, NetworkError)
        assert error.retry_after == 30
        assert error.details["retry_after"] == 30
        assert "30 seconds" in error.details["suggested_solution"]


class TestErrorHandlingDecorator:
    """Test cases for error handling decorator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(logger=self.mock_logger)
    
    def test_decorator_success(self):
        """Test decorator with successful function execution."""
        @with_error_handling(self.error_handler, "test_function", max_retries=2)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_decorator_retry_and_succeed(self):
        """Test decorator with retry and eventual success."""
        call_count = 0
        
        @with_error_handling(self.error_handler, "test_function", max_retries=2)
        def retry_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Temporary network error")
            return "success"
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = retry_then_succeed()
        
        assert result == "success"
        assert call_count == 2
    
    def test_decorator_max_retries_exceeded(self):
        """Test decorator when max retries are exceeded."""
        @with_error_handling(self.error_handler, "test_function", max_retries=1)
        def always_fails():
            raise NetworkError("Persistent network error")
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(NetworkError):
                always_fails()
    
    def test_decorator_non_retryable_error(self):
        """Test decorator with non-retryable error."""
        @with_error_handling(self.error_handler, "test_function", max_retries=2)
        def geo_blocked_function():
            raise GeoRestrictedError("Geo-blocked content")
        
        with pytest.raises(GeoRestrictedError):
            geo_blocked_function()
    
    def test_decorator_yt_dlp_error_classification(self):
        """Test decorator classifies yt-dlp errors."""
        @with_error_handling(self.error_handler, "test_function", max_retries=1)
        def yt_dlp_error_function():
            # Simulate yt-dlp error
            error = Exception("Video not available in your country")
            error.__module__ = "yt_dlp.utils"
            raise error
        
        with pytest.raises(GeoRestrictedError):
            yt_dlp_error_function()


class TestErrorRecovery:
    """Test cases for error recovery scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_network_error_recovery(self):
        """Test recovery from network errors."""
        attempts = 0
        
        def simulate_network_recovery():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise NetworkError("Connection failed")
            return "recovered"
        
        @with_error_handling(self.error_handler, max_retries=3)
        def network_operation():
            return simulate_network_recovery()
        
        with patch('time.sleep'):
            result = network_operation()
        
        assert result == "recovered"
        assert attempts == 3
    
    def test_filesystem_error_recovery(self):
        """Test recovery from filesystem errors."""
        attempts = 0
        
        def simulate_filesystem_recovery():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise FileSystemError("File is busy")
            return "file_written"
        
        @with_error_handling(self.error_handler, max_retries=2)
        def filesystem_operation():
            return simulate_filesystem_recovery()
        
        with patch('time.sleep'):
            result = filesystem_operation()
        
        assert result == "file_written"
        assert attempts == 2
    
    def test_processing_error_limited_retry(self):
        """Test that processing errors have limited retry attempts."""
        attempts = 0
        
        def simulate_processing_error():
            nonlocal attempts
            attempts += 1
            raise ProcessingError("FFmpeg failed")
        
        @with_error_handling(self.error_handler, max_retries=3)
        def processing_operation():
            return simulate_processing_error()
        
        with patch('time.sleep'):
            with pytest.raises(ProcessingError):
                processing_operation()
        
        # Processing errors should only be retried once (2 total attempts)
        assert attempts == 2


if __name__ == "__main__":
    pytest.main([__file__])