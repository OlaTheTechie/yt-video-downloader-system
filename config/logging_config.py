"""
Logging configuration for the YouTube Video Downloader application.
"""

import logging
import logging.handlers
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "./logs",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_structured_logging: bool = True,
    enable_audit_logging: bool = True
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file name. If None, uses 'youtube_downloader.log'
        log_dir: Directory to store log files
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Set default log file name if not provided
    if log_file is None:
        log_file = "youtube_downloader.log"
    
    log_file_path = log_path / log_file
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    if enable_structured_logging:
        formatter = StructuredFormatter()
        console_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = formatter
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Set specific logger levels for external libraries
    logging.getLogger('yt_dlp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Set up audit logging if enabled
    if enable_audit_logging:
        setup_audit_logging(log_dir, max_file_size, backup_count)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def configure_yt_dlp_logging() -> None:
    """Configure yt-dlp specific logging to reduce noise."""
    yt_dlp_logger = logging.getLogger('yt_dlp')
    yt_dlp_logger.setLevel(logging.ERROR)
    
    # Create a custom handler for yt-dlp that filters out progress messages
    class YtDlpFilter(logging.Filter):
        def filter(self, record):
            # Filter out progress and download messages
            message = record.getMessage().lower()
            filtered_keywords = ['downloading', 'progress', 'eta', 'speed']
            return not any(keyword in message for keyword in filtered_keywords)
    
    yt_dlp_filter = YtDlpFilter()
    for handler in yt_dlp_logger.handlers:
        handler.addFilter(yt_dlp_filter)


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for log records."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from the record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, default=str)


class AuditLogger:
    """Specialized logger for audit trail operations."""
    
    def __init__(self, log_dir: str, max_file_size: int = 10 * 1024 * 1024, backup_count: int = 10):
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)
        
        # Create audit log directory
        audit_dir = Path(log_dir) / 'audit'
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up rotating file handler for audit logs
        audit_file = audit_dir / 'audit.log'
        handler = logging.handlers.RotatingFileHandler(
            filename=audit_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Use structured formatter for audit logs
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Prevent audit logs from propagating to root logger
        self.logger.propagate = False
    
    def log_download_start(self, url: str, config: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """Log the start of a download operation."""
        self.logger.info(
            "Download started",
            extra={
                'event_type': 'download_start',
                'url': url,
                'config': config,
                'user_id': user_id,
                'session_id': self._get_session_id()
            }
        )
    
    def log_download_complete(self, url: str, success: bool, file_path: Optional[str] = None,
                            error: Optional[str] = None, duration: Optional[float] = None,
                            file_size: Optional[int] = None) -> None:
        """Log the completion of a download operation."""
        self.logger.info(
            "Download completed",
            extra={
                'event_type': 'download_complete',
                'url': url,
                'success': success,
                'file_path': file_path,
                'error': error,
                'duration_seconds': duration,
                'file_size_bytes': file_size,
                'session_id': self._get_session_id()
            }
        )
    
    def log_configuration_change(self, old_config: Dict[str, Any], new_config: Dict[str, Any],
                               user_id: Optional[str] = None) -> None:
        """Log configuration changes."""
        self.logger.info(
            "Configuration changed",
            extra={
                'event_type': 'config_change',
                'old_config': old_config,
                'new_config': new_config,
                'user_id': user_id,
                'session_id': self._get_session_id()
            }
        )
    
    def log_error_event(self, error_type: str, error_message: str, context: Dict[str, Any],
                       severity: str = 'medium') -> None:
        """Log error events for analysis."""
        self.logger.error(
            "Error event",
            extra={
                'event_type': 'error',
                'error_type': error_type,
                'error_message': error_message,
                'context': context,
                'severity': severity,
                'session_id': self._get_session_id()
            }
        )
    
    def log_performance_metric(self, operation: str, duration: float, 
                             additional_metrics: Optional[Dict[str, Any]] = None) -> None:
        """Log performance metrics."""
        self.logger.info(
            "Performance metric",
            extra={
                'event_type': 'performance',
                'operation': operation,
                'duration_seconds': duration,
                'metrics': additional_metrics or {},
                'session_id': self._get_session_id()
            }
        )
    
    def log_system_event(self, event_type: str, description: str, 
                        details: Optional[Dict[str, Any]] = None) -> None:
        """Log system events."""
        self.logger.info(
            description,
            extra={
                'event_type': event_type,
                'details': details or {},
                'session_id': self._get_session_id()
            }
        )
    
    def _get_session_id(self) -> str:
        """Get or create a session ID for tracking related operations."""
        if not hasattr(self, '_session_id'):
            self._session_id = f"session_{int(time.time())}_{os.getpid()}"
        return self._session_id


class PerformanceLogger:
    """Logger for performance monitoring and metrics."""
    
    def __init__(self, logger_name: str = 'performance'):
        self.logger = logging.getLogger(logger_name)
        self.start_times: Dict[str, float] = {}
    
    def start_operation(self, operation_id: str, operation_name: str, 
                       context: Optional[Dict[str, Any]] = None) -> None:
        """Start timing an operation."""
        self.start_times[operation_id] = time.time()
        self.logger.debug(
            f"Started operation: {operation_name}",
            extra={
                'operation_id': operation_id,
                'operation_name': operation_name,
                'context': context or {}
            }
        )
    
    def end_operation(self, operation_id: str, operation_name: str,
                     success: bool = True, context: Optional[Dict[str, Any]] = None) -> float:
        """End timing an operation and log the duration."""
        if operation_id not in self.start_times:
            self.logger.warning(f"No start time found for operation: {operation_id}")
            return 0.0
        
        duration = time.time() - self.start_times[operation_id]
        del self.start_times[operation_id]
        
        self.logger.info(
            f"Completed operation: {operation_name}",
            extra={
                'operation_id': operation_id,
                'operation_name': operation_name,
                'duration_seconds': duration,
                'success': success,
                'context': context or {}
            }
        )
        
        return duration
    
    def log_metric(self, metric_name: str, value: float, unit: str = '',
                  context: Optional[Dict[str, Any]] = None) -> None:
        """Log a performance metric."""
        self.logger.info(
            f"Metric: {metric_name} = {value} {unit}",
            extra={
                'metric_name': metric_name,
                'metric_value': value,
                'metric_unit': unit,
                'context': context or {}
            }
        )


def setup_audit_logging(log_dir: str, max_file_size: int, backup_count: int) -> AuditLogger:
    """Set up audit logging and return the audit logger instance."""
    return AuditLogger(log_dir, max_file_size, backup_count)


def get_audit_logger() -> AuditLogger:
    """Get the audit logger instance."""
    return AuditLogger('./logs')


def get_performance_logger(name: str = 'performance') -> PerformanceLogger:
    """Get a performance logger instance."""
    return PerformanceLogger(name)


class LogAnalyzer:
    """Utility class for analyzing log files."""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = Path(log_file_path)
    
    def analyze_error_patterns(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze error patterns in the log file."""
        if not self.log_file_path.exists():
            return {}
        
        error_counts = {}
        error_types = {}
        recent_errors = []
        
        cutoff_time = time.time() - (hours * 3600)
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # Parse timestamp
                        timestamp = datetime.fromisoformat(log_entry.get('timestamp', ''))
                        if timestamp.timestamp() < cutoff_time:
                            continue
                        
                        if log_entry.get('level') in ['ERROR', 'CRITICAL']:
                            error_msg = log_entry.get('message', '')
                            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
                            
                            # Extract error type from extra fields
                            extra = log_entry.get('extra', {})
                            error_type = extra.get('error_type', 'unknown')
                            error_types[error_type] = error_types.get(error_type, 0) + 1
                            
                            recent_errors.append({
                                'timestamp': log_entry.get('timestamp'),
                                'message': error_msg,
                                'type': error_type,
                                'context': extra.get('context', {})
                            })
                    
                    except (json.JSONDecodeError, ValueError):
                        # Skip non-JSON lines
                        continue
        
        except Exception as e:
            return {'error': f"Could not analyze log file: {str(e)}"}
        
        return {
            'analysis_period_hours': hours,
            'total_errors': sum(error_counts.values()),
            'unique_error_messages': len(error_counts),
            'error_counts': error_counts,
            'error_types': error_types,
            'recent_errors': recent_errors[-10:]  # Last 10 errors
        }
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary from log file."""
        if not self.log_file_path.exists():
            return {}
        
        operations = {}
        metrics = {}
        
        cutoff_time = time.time() - (hours * 3600)
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # Parse timestamp
                        timestamp = datetime.fromisoformat(log_entry.get('timestamp', ''))
                        if timestamp.timestamp() < cutoff_time:
                            continue
                        
                        extra = log_entry.get('extra', {})
                        
                        # Collect operation durations
                        if 'duration_seconds' in extra:
                            op_name = extra.get('operation_name', 'unknown')
                            duration = extra.get('duration_seconds', 0)
                            
                            if op_name not in operations:
                                operations[op_name] = []
                            operations[op_name].append(duration)
                        
                        # Collect metrics
                        if 'metric_name' in extra:
                            metric_name = extra.get('metric_name')
                            metric_value = extra.get('metric_value', 0)
                            
                            if metric_name not in metrics:
                                metrics[metric_name] = []
                            metrics[metric_name].append(metric_value)
                    
                    except (json.JSONDecodeError, ValueError):
                        continue
        
        except Exception as e:
            return {'error': f"Could not analyze performance data: {str(e)}"}
        
        # Calculate statistics
        operation_stats = {}
        for op_name, durations in operations.items():
            operation_stats[op_name] = {
                'count': len(durations),
                'avg_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'total_duration': sum(durations)
            }
        
        metric_stats = {}
        for metric_name, values in metrics.items():
            metric_stats[metric_name] = {
                'count': len(values),
                'avg_value': sum(values) / len(values),
                'min_value': min(values),
                'max_value': max(values)
            }
        
        return {
            'analysis_period_hours': hours,
            'operations': operation_stats,
            'metrics': metric_stats
        }