"""
Timestamp parsing service for extracting and validating timestamps from video descriptions.
"""

import re
from typing import List, Optional, Tuple
from models.core import Timestamp
from services.interfaces import TimestampParserInterface
import logging

logger = logging.getLogger(__name__)


class TimestampParser(TimestampParserInterface):
    """
    Parser for extracting timestamps from video descriptions.
    
    Supports multiple timestamp formats:
    - 0:00, 5:30, 1:23:45 (basic format)
    - [0:00], [5:30] (bracketed format)
    - 0:00 -, 5:30 - (dash separator format)
    """
    
    # Regex patterns for different timestamp formats
    TIMESTAMP_PATTERNS = [
        # Pattern 1: Basic format (0:00, 5:30, 1:23:45) - space separated
        r'(?:^|\n)\s*(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<label>[^\n]+?)(?=\n|$)',
        
        # Pattern 2: Bracketed format ([0:00], [5:30])
        r'(?:^|\n)\s*\[(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<label>[^\n]*?)(?=\n|$)',
        
        # Pattern 3: Dash separator format (0:00 -, 5:30 -)
        r'(?:^|\n)\s*(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<label>[^\n]*?)(?=\n|$)',
        
        # Pattern 4: Colon separator format (0:00:, 5:30:) - but not HH:MM:SS
        r'(?:^|\n)\s*(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?):\s*(?P<label>[^\n]*?)(?=\n|$)',
    ]
    
    def __init__(self):
        """Initialize the timestamp parser."""
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE | re.IGNORECASE) 
                                for pattern in self.TIMESTAMP_PATTERNS]
    
    def parse_description(self, description: str) -> List[Timestamp]:
        """
        Parse timestamps from video description.
        
        Args:
            description: Video description text
            
        Returns:
            List of Timestamp objects found in the description
        """
        if not description or not description.strip():
            logger.debug("Empty description provided")
            return []
        
        timestamps = []
        found_positions = set()  # To avoid duplicates based on position
        
        # Try each pattern
        for pattern in self.compiled_patterns:
            matches = pattern.finditer(description)
            
            for match in matches:
                # Skip if we already found a timestamp at this position
                start_pos = match.start()
                if start_pos in found_positions:
                    continue
                
                timestamp_str = match.group('timestamp').strip()
                label = match.group('label').strip()
                original_text = match.group(0).strip()
                
                # Convert timestamp string to seconds
                try:
                    time_seconds = self._parse_time_string(timestamp_str)
                    
                    # Mark this position as found
                    found_positions.add(start_pos)
                    
                    # Clean up the label
                    cleaned_label = self._clean_label(label)
                    
                    timestamp = Timestamp(
                        time_seconds=time_seconds,
                        label=cleaned_label,
                        original_text=original_text
                    )
                    timestamps.append(timestamp)
                        
                except ValueError as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
                    continue
        
        # Remove duplicates based on time (in case different patterns matched the same timestamp)
        unique_timestamps = []
        seen_times = set()
        
        for timestamp in timestamps:
            if timestamp.time_seconds not in seen_times:
                seen_times.add(timestamp.time_seconds)
                unique_timestamps.append(timestamp)
        
        # Sort timestamps by time
        unique_timestamps.sort(key=lambda t: t.time_seconds)
        
        logger.info(f"Found {len(unique_timestamps)} timestamps in description")
        return unique_timestamps
    
    def validate_timestamps(self, timestamps: List[Timestamp]) -> bool:
        """
        Validate that timestamps are in chronological order and have valid values.
        
        Args:
            timestamps: List of timestamps to validate
            
        Returns:
            True if timestamps are valid, False otherwise
        """
        if not timestamps:
            return True
        
        # Check for negative timestamps
        for timestamp in timestamps:
            if timestamp.time_seconds < 0:
                logger.error(f"Invalid negative timestamp: {timestamp.time_seconds}")
                return False
        
        # Check chronological order
        for i in range(1, len(timestamps)):
            if timestamps[i].time_seconds <= timestamps[i-1].time_seconds:
                logger.error(f"Timestamps not in chronological order: "
                           f"{timestamps[i-1].time_seconds} >= {timestamps[i].time_seconds}")
                return False
        
        # Check for reasonable gaps (at least 1 second between timestamps)
        for i in range(1, len(timestamps)):
            gap = timestamps[i].time_seconds - timestamps[i-1].time_seconds
            if gap < 1.0:
                logger.warning(f"Very short gap between timestamps: {gap} seconds")
        
        logger.info(f"Validated {len(timestamps)} timestamps successfully")
        return True
    
    def extract_chapter_names(self, description: str, timestamps: List[Timestamp]) -> List[str]:
        """
        Extract chapter names from timestamp lines in the description.
        
        Args:
            description: Video description text
            timestamps: List of parsed timestamps
            
        Returns:
            List of chapter names corresponding to the timestamps
        """
        if not timestamps:
            return []
        
        chapter_names = []
        
        for timestamp in timestamps:
            if timestamp.label and timestamp.label.strip():
                # Use the existing label from the timestamp
                chapter_names.append(timestamp.label.strip())
            else:
                # Generate a default chapter name
                chapter_names.append(f"Chapter at {timestamp.format_time()}")
        
        logger.info(f"Extracted {len(chapter_names)} chapter names")
        return chapter_names
    
    def _parse_time_string(self, time_str: str) -> float:
        """
        Convert time string to seconds.
        
        Args:
            time_str: Time string in format MM:SS or HH:MM:SS
            
        Returns:
            Time in seconds as float
            
        Raises:
            ValueError: If time string format is invalid
        """
        time_str = time_str.strip()
        parts = time_str.split(':')
        
        if len(parts) == 2:
            # MM:SS format
            try:
                minutes = int(parts[0])
                seconds = int(parts[1])
                
                if minutes < 0 or seconds < 0 or seconds >= 60:
                    raise ValueError(f"Invalid time values: {minutes}:{seconds}")
                
                return minutes * 60 + seconds
            except ValueError as e:
                raise ValueError(f"Invalid MM:SS format '{time_str}': {e}")
                
        elif len(parts) == 3:
            # HH:MM:SS format
            try:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                
                if hours < 0 or minutes < 0 or seconds < 0 or minutes >= 60 or seconds >= 60:
                    raise ValueError(f"Invalid time values: {hours}:{minutes}:{seconds}")
                
                return hours * 3600 + minutes * 60 + seconds
            except ValueError as e:
                raise ValueError(f"Invalid HH:MM:SS format '{time_str}': {e}")
        else:
            raise ValueError(f"Invalid time format '{time_str}'. Expected MM:SS or HH:MM:SS")
    
    def _clean_label(self, label: str) -> str:
        """
        Clean and normalize chapter label text.
        
        Args:
            label: Raw label text
            
        Returns:
            Cleaned label text
        """
        if not label:
            return ""
        
        # Remove common prefixes and suffixes
        label = label.strip()
        
        # Remove leading/trailing punctuation
        label = label.strip('- \t')
        
        # Remove multiple spaces (but preserve single spaces)
        label = re.sub(r'\s{2,}', ' ', label)
        
        # Capitalize first letter if it's all lowercase
        if label and label.islower():
            label = label[0].upper() + label[1:]
        
        return label
    
    def get_timestamp_statistics(self, timestamps: List[Timestamp]) -> dict:
        """
        Get statistics about the parsed timestamps.
        
        Args:
            timestamps: List of timestamps
            
        Returns:
            Dictionary with statistics
        """
        if not timestamps:
            return {
                'count': 0,
                'total_duration': 0,
                'average_chapter_length': 0,
                'shortest_chapter': 0,
                'longest_chapter': 0
            }
        
        # Calculate chapter durations (approximate)
        chapter_durations = []
        for i in range(len(timestamps) - 1):
            duration = timestamps[i + 1].time_seconds - timestamps[i].time_seconds
            chapter_durations.append(duration)
        
        # Add a placeholder for the last chapter (we don't know video duration yet)
        if chapter_durations:
            # Use the average of existing chapters as estimate for last chapter
            avg_duration = sum(chapter_durations) / len(chapter_durations)
            chapter_durations.append(avg_duration)  # Estimate for last chapter
        elif len(timestamps) == 1:
            # Single timestamp - estimate a reasonable duration
            chapter_durations.append(300.0)  # 5 minutes default
        
        if not chapter_durations:
            return {
                'count': len(timestamps),
                'total_duration': timestamps[-1].time_seconds if timestamps else 0,
                'average_chapter_length': 0,
                'shortest_chapter': 0,
                'longest_chapter': 0
            }
        
        return {
            'count': len(timestamps),
            'total_duration': timestamps[-1].time_seconds if timestamps else 0,
            'average_chapter_length': sum(chapter_durations) / len(chapter_durations),
            'shortest_chapter': min(chapter_durations),
            'longest_chapter': max(chapter_durations)
        }