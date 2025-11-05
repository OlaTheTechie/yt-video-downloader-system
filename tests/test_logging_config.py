"""
Unit tests for logging configuration and structured logging.
"""

import pytest
import tempfile
import json
import logging
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from config.logging_config import (
    setup_logging, get_logger, StructuredFormatter, AuditLogger,
    PerformanceLogger, LogAnalyzer, get_audit_logger, get_performance_logger
)


class TestStructuredFormatter:
    """Test cases for StructuredFormatter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = StructuredFormatter()
    
    def test_format_basic_record(self):
        """Test formatting of basic log record."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert log_entry['level'] == 'INFO'
        assert log_entry['logger'] == 'test_logger'
        assert log_entry['message'] == 'Test message'
        assert log_entry['line'] == 42
        assert 'timestamp' in log_entry
    
    def test_format_record_with_extra_fields(self):
        """Test formatting of log record with extra fields."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.operation_id = "op_123"
        record.user_id = "user_456"
        record.custom_data = {"key": "value"}
        
        formatted = self.formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert 'extra' in log_entry
        assert log_entry['extra']['operation_id'] == "op_123"
        assert log_entry['extra']['user_id'] == "user_456"
        assert log_entry['extra']['custom_data'] == {"key": "value"}
    
    def test_format_record_with_exception(self):
        """Test formatting of log record with exception information."""
        import sys
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Exception occurred",
            args=(),
            exc_info=exc_info
        )
        
        formatted = self.formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert 'exception' in log_entry
        assert 'ValueError' in log_entry['exception']
        assert 'Test exception' in log_entry['exception']


class TestAuditLogger:
    """Test cases for AuditLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_audit_logger_initialization(self):
        """Test AuditLogger initialization."""
        audit_dir = Path(self.temp_dir) / 'audit'
        assert audit_dir.exists()
        assert audit_dir.is_dir()
        
        # Check that logger is configured
        assert self.audit_logger.logger.name == 'audit'
        assert self.audit_logger.logger.level == logging.INFO
        assert not self.audit_logger.logger.propagate
    
    def test_log_download_start(self):
        """Test logging download start events."""
        config = {"quality": "720p", "format": "mp4"}
        
        self.audit_logger.log_download_start(
            url="https://example.com/video",
            config=config,
            user_id="test_user"
        )
        
        # Verify log file was created and contains expected data
        audit_file = Path(self.temp_dir) / 'audit' / 'audit.log'
        assert audit_file.exists()
        
        with open(audit_file, 'r') as f:
            log_line = f.readline().strip()
        
        log_entry = json.loads(log_line)
        assert log_entry['message'] == "Download started"
        assert log_entry['extra']['event_type'] == 'download_start'
        assert log_entry['extra']['url'] == "https://example.com/video"
        assert log_entry['extra']['config'] == config
        assert log_entry['extra']['user_id'] == "test_user"
    
    def test_log_download_complete(self):
        """Test logging download completion events."""
        self.audit_logger.log_download_complete(
            url="https://example.com/video",
            success=True,
            file_path="/downloads/video.mp4",
            duration=120.5,
            file_size=1024000
        )
        
        audit_file = Path(self.temp_dir) / 'audit' / 'audit.log'
        with open(audit_file, 'r') as f:
            log_line = f.readline().strip()
        
        log_entry = json.loads(log_line)
        assert log_entry['message'] == "Download completed"
        assert log_entry['extra']['event_type'] == 'download_complete'
        assert log_entry['extra']['success'] is True
        assert log_entry['extra']['file_path'] == "/downloads/video.mp4"
        assert log_entry['extra']['duration_seconds'] == 120.5
        assert log_entry['extra']['file_size_bytes'] == 1024000
    
    def test_log_configuration_change(self):
        """Test logging configuration changes."""
        old_config = {"quality": "720p"}
        new_config = {"quality": "1080p"}
        
        self.audit_logger.log_configuration_change(
            old_config=old_config,
            new_config=new_config,
            user_id="admin_user"
        )
        
        audit_file = Path(self.temp_dir) / 'audit' / 'audit.log'
        with open(audit_file, 'r') as f:
            log_line = f.readline().strip()
        
        log_entry = json.loads(log_line)
        assert log_entry['message'] == "Configuration changed"
        assert log_entry['extra']['event_type'] == 'config_change'
        assert log_entry['extra']['old_config'] == old_config
        assert log_entry['extra']['new_config'] == new_config
    
    def test_log_error_event(self):
        """Test logging error events."""
        context = {"operation": "download", "url": "https://example.com/video"}
        
        self.audit_logger.log_error_event(
            error_type="NetworkError",
            error_message="Connection timeout",
            context=context,
            severity="high"
        )
        
        audit_file = Path(self.temp_dir) / 'audit' / 'audit.log'
        with open(audit_file, 'r') as f:
            log_line = f.readline().strip()
        
        log_entry = json.loads(log_line)
        assert log_entry['level'] == 'ERROR'
        assert log_entry['extra']['event_type'] == 'error'
        assert log_entry['extra']['error_type'] == "NetworkError"
        assert log_entry['extra']['error_message'] == "Connection timeout"
        assert log_entry['extra']['context'] == context
        assert log_entry['extra']['severity'] == "high"
    
    def test_session_id_consistency(self):
        """Test that session ID is consistent across operations."""
        self.audit_logger.log_download_start("url1", {})
        self.audit_logger.log_download_start("url2", {})
        
        audit_file = Path(self.temp_dir) / 'audit' / 'audit.log'
        with open(audit_file, 'r') as f:
            lines = f.readlines()
        
        log1 = json.loads(lines[0].strip())
        log2 = json.loads(lines[1].strip())
        
        # Session IDs should be the same for the same logger instance
        assert log1['extra']['session_id'] == log2['extra']['session_id']


class TestPerformanceLogger:
    """Test cases for PerformanceLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.perf_logger = PerformanceLogger("test_performance")
    
    def test_start_and_end_operation(self):
        """Test starting and ending operation timing."""
        operation_id = "test_op_1"
        operation_name = "test_operation"
        context = {"param": "value"}
        
        # Start operation
        self.perf_logger.start_operation(operation_id, operation_name, context)
        assert operation_id in self.perf_logger.start_times
        
        # Simulate some work
        time.sleep(0.01)
        
        # End operation
        duration = self.perf_logger.end_operation(operation_id, operation_name, True, context)
        
        assert duration > 0
        assert operation_id not in self.perf_logger.start_times
    
    def test_end_operation_without_start(self):
        """Test ending operation that wasn't started."""
        with patch.object(self.perf_logger.logger, 'warning') as mock_warning:
            duration = self.perf_logger.end_operation("nonexistent", "test", True)
            
            assert duration == 0.0
            mock_warning.assert_called_once()
    
    def test_log_metric(self):
        """Test logging performance metrics."""
        with patch.object(self.perf_logger.logger, 'info') as mock_info:
            self.perf_logger.log_metric(
                metric_name="download_speed",
                value=1.5,
                unit="MB/s",
                context={"file": "video.mp4"}
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            # Check the extra fields
            extra = call_args[1]['extra']
            assert extra['metric_name'] == "download_speed"
            assert extra['metric_value'] == 1.5
            assert extra['metric_unit'] == "MB/s"
            assert extra['context'] == {"file": "video.mp4"}


class TestLogAnalyzer:
    """Test cases for LogAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test.log"
        
        # Create sample log entries
        sample_logs = [
            {
                "timestamp": "2023-01-01T12:00:00",
                "level": "ERROR",
                "message": "Network connection failed",
                "extra": {"error_type": "NetworkError", "context": {"url": "test1"}}
            },
            {
                "timestamp": "2023-01-01T12:01:00",
                "level": "ERROR",
                "message": "Network connection failed",
                "extra": {"error_type": "NetworkError", "context": {"url": "test2"}}
            },
            {
                "timestamp": "2023-01-01T12:02:00",
                "level": "ERROR",
                "message": "File not found",
                "extra": {"error_type": "FileSystemError", "context": {"path": "/test"}}
            },
            {
                "timestamp": "2023-01-01T12:03:00",
                "level": "INFO",
                "message": "Operation completed",
                "extra": {"operation_name": "download", "duration_seconds": 10.5}
            }
        ]
        
        with open(self.log_file, 'w') as f:
            for log_entry in sample_logs:
                f.write(json.dumps(log_entry) + '\n')
        
        self.analyzer = LogAnalyzer(str(self.log_file))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_analyze_error_patterns(self):
        """Test error pattern analysis."""
        with patch('time.time', return_value=time.mktime(time.strptime("2023-01-01T13:00:00", "%Y-%m-%dT%H:%M:%S"))):
            analysis = self.analyzer.analyze_error_patterns(hours=24)
        
        assert analysis['total_errors'] == 3
        assert analysis['unique_error_messages'] == 2
        assert analysis['error_counts']['Network connection failed'] == 2
        assert analysis['error_counts']['File not found'] == 1
        assert analysis['error_types']['NetworkError'] == 2
        assert analysis['error_types']['FileSystemError'] == 1
        assert len(analysis['recent_errors']) == 3
    
    def test_get_performance_summary(self):
        """Test performance summary generation."""
        with patch('time.time', return_value=time.mktime(time.strptime("2023-01-01T13:00:00", "%Y-%m-%dT%H:%M:%S"))):
            summary = self.analyzer.get_performance_summary(hours=24)
        
        assert 'operations' in summary
        assert 'download' in summary['operations']
        assert summary['operations']['download']['count'] == 1
        assert summary['operations']['download']['avg_duration'] == 10.5
    
    def test_analyze_nonexistent_file(self):
        """Test analysis of nonexistent log file."""
        nonexistent_analyzer = LogAnalyzer("/nonexistent/path.log")
        
        analysis = nonexistent_analyzer.analyze_error_patterns()
        assert analysis == {}
        
        summary = nonexistent_analyzer.get_performance_summary()
        assert summary == {}


class TestLoggingSetup:
    """Test cases for logging setup functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset logging configuration
        logging.getLogger().handlers.clear()
    
    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        setup_logging(
            log_level="DEBUG",
            log_dir=self.temp_dir,
            enable_structured_logging=False,
            enable_audit_logging=False
        )
        
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG
        
        # Check that log directory was created
        log_dir = Path(self.temp_dir)
        assert log_dir.exists()
        
        # Check that log file was created
        log_file = log_dir / "youtube_downloader.log"
        
        # Log a test message to create the file
        test_logger = get_logger("test")
        test_logger.info("Test message")
        
        assert log_file.exists()
    
    def test_setup_logging_structured(self):
        """Test structured logging setup."""
        setup_logging(
            log_level="INFO",
            log_dir=self.temp_dir,
            enable_structured_logging=True,
            enable_audit_logging=False
        )
        
        # Test that structured formatter is used
        logger = logging.getLogger()
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) > 0
        
        file_handler = file_handlers[0]
        assert isinstance(file_handler.formatter, StructuredFormatter)
    
    def test_setup_logging_with_audit(self):
        """Test logging setup with audit logging enabled."""
        setup_logging(
            log_level="INFO",
            log_dir=self.temp_dir,
            enable_audit_logging=True
        )
        
        # Check that audit directory was created
        audit_dir = Path(self.temp_dir) / 'audit'
        assert audit_dir.exists()
    
    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test_module")
        assert logger.name == "test_module"
        assert isinstance(logger, logging.Logger)
    
    def test_get_audit_logger(self):
        """Test get_audit_logger function."""
        audit_logger = get_audit_logger()
        assert isinstance(audit_logger, AuditLogger)
    
    def test_get_performance_logger(self):
        """Test get_performance_logger function."""
        perf_logger = get_performance_logger("test_perf")
        assert isinstance(perf_logger, PerformanceLogger)
        assert perf_logger.logger.name == "test_perf"


class TestLoggingIntegration:
    """Integration tests for logging functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Set up complete logging system
        setup_logging(
            log_level="DEBUG",
            log_dir=self.temp_dir,
            enable_structured_logging=True,
            enable_audit_logging=True
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset logging
        logging.getLogger().handlers.clear()
    
    def test_complete_logging_workflow(self):
        """Test complete logging workflow with all components."""
        # Get loggers
        app_logger = get_logger("app")
        audit_logger = get_audit_logger()
        perf_logger = get_performance_logger()
        
        # Log various events
        app_logger.info("Application started")
        app_logger.error("An error occurred", extra={"error_code": "E001"})
        
        audit_logger.log_download_start("https://example.com", {"quality": "720p"})
        audit_logger.log_download_complete("https://example.com", True, "/path/video.mp4")
        
        perf_logger.start_operation("op1", "test_operation")
        time.sleep(0.01)
        perf_logger.end_operation("op1", "test_operation", True)
        
        # Verify log files were created
        main_log = Path(self.temp_dir) / "youtube_downloader.log"
        audit_log = Path(self.temp_dir) / "audit" / "audit.log"
        
        assert main_log.exists()
        assert audit_log.exists()
        
        # Verify log content
        with open(main_log, 'r') as f:
            main_content = f.read()
            assert "Application started" in main_content
            assert "An error occurred" in main_content
        
        with open(audit_log, 'r') as f:
            audit_lines = f.readlines()
            assert len(audit_lines) >= 2  # At least download start and complete
            
            # Parse first audit log entry
            first_entry = json.loads(audit_lines[0].strip())
            assert first_entry['extra']['event_type'] == 'download_start'
    
    def test_log_analysis_integration(self):
        """Test log analysis on real log files."""
        # Generate some log entries
        app_logger = get_logger("app")
        
        app_logger.error("Network error 1", extra={"error_type": "NetworkError"})
        app_logger.error("Network error 2", extra={"error_type": "NetworkError"})
        app_logger.error("File error", extra={"error_type": "FileSystemError"})
        
        # Analyze the logs
        main_log = Path(self.temp_dir) / "youtube_downloader.log"
        analyzer = LogAnalyzer(str(main_log))
        
        analysis = analyzer.analyze_error_patterns(hours=1)
        
        assert analysis['total_errors'] == 3
        assert analysis['error_types']['NetworkError'] == 2
        assert analysis['error_types']['FileSystemError'] == 1


if __name__ == "__main__":
    pytest.main([__file__])