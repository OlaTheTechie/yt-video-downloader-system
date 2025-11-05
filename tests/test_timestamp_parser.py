"""
Unit tests for TimestampParser class.
"""

import pytest
from services.timestamp_parser import TimestampParser
from models.core import Timestamp


class TestTimestampParser:
    """Test cases for TimestampParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = TimestampParser()
    
    def test_parse_basic_format(self):
        """Test parsing basic timestamp format (MM:SS)."""
        description = """
        0:00 Introduction
        5:30 Main Topic
        12:45 Conclusion
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 3
        assert timestamps[0].time_seconds == 0
        assert timestamps[0].label == "Introduction"
        assert timestamps[1].time_seconds == 330  # 5*60 + 30
        assert timestamps[1].label == "Main Topic"
        assert timestamps[2].time_seconds == 765  # 12*60 + 45
        assert timestamps[2].label == "Conclusion"
    
    def test_parse_extended_format(self):
        """Test parsing extended timestamp format (HH:MM:SS)."""
        description = """
        0:00:00 Start
        1:23:45 Middle Section
        2:30:15 End
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 3
        assert timestamps[0].time_seconds == 0
        assert timestamps[1].time_seconds == 5025  # 1*3600 + 23*60 + 45
        assert timestamps[2].time_seconds == 9015  # 2*3600 + 30*60 + 15
    
    def test_parse_bracketed_format(self):
        """Test parsing bracketed timestamp format ([MM:SS])."""
        description = """
        [0:00] Introduction
        [5:30] Main Content
        [12:45] Wrap Up
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 3
        assert timestamps[0].time_seconds == 0
        assert timestamps[0].label == "Introduction"
        assert timestamps[1].time_seconds == 330
        assert timestamps[1].label == "Main Content"
    
    def test_parse_dash_separator_format(self):
        """Test parsing dash separator format (MM:SS -)."""
        description = """
        0:00 - Introduction
        5:30 - Main Topic
        12:45 - Conclusion
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 3
        assert timestamps[0].label == "Introduction"
        assert timestamps[1].label == "Main Topic"
        assert timestamps[2].label == "Conclusion"
    
    def test_parse_colon_separator_format(self):
        """Test parsing colon separator format (MM:SS:)."""
        description = """
        0:00: Introduction
        5:30: Main Topic
        12:45: Conclusion
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 3
        assert timestamps[0].label == "Introduction"
        assert timestamps[1].label == "Main Topic"
        assert timestamps[2].label == "Conclusion"
    
    def test_parse_mixed_formats(self):
        """Test parsing mixed timestamp formats."""
        description = """
        0:00 Introduction
        [5:30] Main Topic
        12:45 - Conclusion
        1:23:45: Extended Section
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 4
        # Should be sorted by time
        assert timestamps[0].time_seconds == 0
        assert timestamps[1].time_seconds == 330
        assert timestamps[2].time_seconds == 765
        assert timestamps[3].time_seconds == 5025
    
    def test_parse_empty_description(self):
        """Test parsing empty description."""
        timestamps = self.parser.parse_description("")
        assert len(timestamps) == 0
        
        timestamps = self.parser.parse_description(None)
        assert len(timestamps) == 0
        
        timestamps = self.parser.parse_description("   ")
        assert len(timestamps) == 0
    
    def test_parse_no_timestamps(self):
        """Test parsing description with no timestamps."""
        description = """
        This is a video about programming.
        It covers various topics and concepts.
        No timestamps are included here.
        """
        
        timestamps = self.parser.parse_description(description)
        assert len(timestamps) == 0
    
    def test_parse_invalid_timestamps(self):
        """Test parsing description with invalid timestamps."""
        description = """
        0:00 Valid timestamp
        25:70 Invalid seconds (>59)
        -5:30 Negative timestamp
        abc:def Invalid format
        5:30 Another valid timestamp
        """
        
        timestamps = self.parser.parse_description(description)
        
        # Should only get the valid timestamps
        assert len(timestamps) == 2
        assert timestamps[0].time_seconds == 0
        assert timestamps[1].time_seconds == 330
    
    def test_parse_duplicate_timestamps(self):
        """Test parsing description with duplicate timestamps."""
        description = """
        0:00 Introduction
        0:00 Also Introduction
        5:30 Main Topic
        5:30 Still Main Topic
        """
        
        timestamps = self.parser.parse_description(description)
        
        # Should remove duplicates
        assert len(timestamps) == 2
        assert timestamps[0].time_seconds == 0
        assert timestamps[1].time_seconds == 330
    
    def test_validate_timestamps_valid(self):
        """Test validating valid timestamps."""
        timestamps = [
            Timestamp(0, "Start", "0:00 Start"),
            Timestamp(300, "Middle", "5:00 Middle"),
            Timestamp(600, "End", "10:00 End")
        ]
        
        assert self.parser.validate_timestamps(timestamps) is True
    
    def test_validate_timestamps_empty(self):
        """Test validating empty timestamp list."""
        assert self.parser.validate_timestamps([]) is True
    
    def test_validate_timestamps_negative(self):
        """Test validating timestamps with negative values."""
        # Create timestamp with negative value by bypassing validation
        timestamp1 = Timestamp.__new__(Timestamp)
        timestamp1.time_seconds = -10
        timestamp1.label = "Invalid"
        timestamp1.original_text = "-0:10 Invalid"
        
        timestamp2 = Timestamp(300, "Valid", "5:00 Valid")
        timestamps = [timestamp1, timestamp2]
        
        assert self.parser.validate_timestamps(timestamps) is False
    
    def test_validate_timestamps_wrong_order(self):
        """Test validating timestamps in wrong chronological order."""
        timestamps = [
            Timestamp(300, "Later", "5:00 Later"),
            Timestamp(100, "Earlier", "1:40 Earlier")
        ]
        
        assert self.parser.validate_timestamps(timestamps) is False
    
    def test_validate_timestamps_equal_times(self):
        """Test validating timestamps with equal times."""
        timestamps = [
            Timestamp(300, "First", "5:00 First"),
            Timestamp(300, "Second", "5:00 Second")
        ]
        
        assert self.parser.validate_timestamps(timestamps) is False
    
    def test_extract_chapter_names_with_labels(self):
        """Test extracting chapter names when labels exist."""
        timestamps = [
            Timestamp(0, "Introduction", "0:00 Introduction"),
            Timestamp(300, "Main Content", "5:00 Main Content"),
            Timestamp(600, "Conclusion", "10:00 Conclusion")
        ]
        
        chapter_names = self.parser.extract_chapter_names("", timestamps)
        
        assert len(chapter_names) == 3
        assert chapter_names[0] == "Introduction"
        assert chapter_names[1] == "Main Content"
        assert chapter_names[2] == "Conclusion"
    
    def test_extract_chapter_names_without_labels(self):
        """Test extracting chapter names when labels are missing."""
        timestamps = [
            Timestamp(0, "", "0:00"),
            Timestamp(300, "", "5:00"),
            Timestamp(600, "", "10:00")
        ]
        
        chapter_names = self.parser.extract_chapter_names("", timestamps)
        
        assert len(chapter_names) == 3
        assert "Chapter at 00:00" in chapter_names[0]
        assert "Chapter at 05:00" in chapter_names[1]
        assert "Chapter at 10:00" in chapter_names[2]
    
    def test_extract_chapter_names_empty(self):
        """Test extracting chapter names from empty timestamp list."""
        chapter_names = self.parser.extract_chapter_names("", [])
        assert len(chapter_names) == 0
    
    def test_parse_time_string_mm_ss(self):
        """Test parsing MM:SS time strings."""
        assert self.parser._parse_time_string("0:00") == 0
        assert self.parser._parse_time_string("5:30") == 330
        assert self.parser._parse_time_string("12:45") == 765
        assert self.parser._parse_time_string("59:59") == 3599
    
    def test_parse_time_string_hh_mm_ss(self):
        """Test parsing HH:MM:SS time strings."""
        assert self.parser._parse_time_string("0:00:00") == 0
        assert self.parser._parse_time_string("1:23:45") == 5025
        assert self.parser._parse_time_string("2:30:15") == 9015
        assert self.parser._parse_time_string("10:59:59") == 39599
    
    def test_parse_time_string_invalid_format(self):
        """Test parsing invalid time string formats."""
        with pytest.raises(ValueError):
            self.parser._parse_time_string("5")  # Only one part
        
        with pytest.raises(ValueError):
            self.parser._parse_time_string("5:30:45:10")  # Too many parts
        
        with pytest.raises(ValueError):
            self.parser._parse_time_string("abc:def")  # Non-numeric
        
        with pytest.raises(ValueError):
            self.parser._parse_time_string("5:70")  # Invalid seconds
        
        with pytest.raises(ValueError):
            self.parser._parse_time_string("1:70:30")  # Invalid minutes
    
    def test_clean_label(self):
        """Test label cleaning functionality."""
        test_cases = [
            ("  Introduction  ", "Introduction"),
            ("- Main Topic -", "Main Topic"),
            ("   - Chapter 1 -   ", "Chapter 1"),
            ("multiple    spaces", "Multiple spaces"),
            ("lowercase title", "Lowercase title"),
            ("UPPERCASE TITLE", "UPPERCASE TITLE"),
            ("", ""),
            ("   ", ""),
            ("- - -", ""),
        ]
        
        for input_label, expected in test_cases:
            result = self.parser._clean_label(input_label)
            assert result == expected
    
    def test_get_timestamp_statistics(self):
        """Test getting timestamp statistics."""
        timestamps = [
            Timestamp(0, "Start", "0:00 Start"),
            Timestamp(300, "Middle", "5:00 Middle"),
            Timestamp(600, "End", "10:00 End")
        ]
        
        stats = self.parser.get_timestamp_statistics(timestamps)
        
        assert stats['count'] == 3
        assert stats['total_duration'] == 600
        assert stats['average_chapter_length'] == 300  # (300 + 300 + 300) / 3
        assert stats['shortest_chapter'] == 300  # All chapters same length
        assert stats['longest_chapter'] == 300
    
    def test_get_timestamp_statistics_empty(self):
        """Test getting statistics for empty timestamp list."""
        stats = self.parser.get_timestamp_statistics([])
        
        assert stats['count'] == 0
        assert stats['total_duration'] == 0
        assert stats['average_chapter_length'] == 0
        assert stats['shortest_chapter'] == 0
        assert stats['longest_chapter'] == 0
    
    def test_get_timestamp_statistics_single(self):
        """Test getting statistics for single timestamp."""
        timestamps = [Timestamp(300, "Only Chapter", "5:00 Only Chapter")]
        
        stats = self.parser.get_timestamp_statistics(timestamps)
        
        assert stats['count'] == 1
        assert stats['total_duration'] == 300
        # Single timestamp gets estimated duration
        assert stats['average_chapter_length'] > 0
    
    def test_real_world_description(self):
        """Test parsing a realistic video description."""
        description = """
        Learn Python programming in this comprehensive tutorial!
        
        📚 Chapters:
        0:00 Introduction
        2:15 Setting up Python
        8:30 Variables and Data Types
        15:45 Control Structures
        [25:20] Functions and Modules
        35:10 - Object-Oriented Programming
        48:55: Error Handling
        1:02:30 File Operations
        1:15:45 Final Project
        
        Don't forget to like and subscribe!
        """
        
        timestamps = self.parser.parse_description(description)
        
        assert len(timestamps) == 9
        assert timestamps[0].time_seconds == 0
        assert timestamps[0].label == "Introduction"
        assert timestamps[1].time_seconds == 135  # 2:15
        assert timestamps[1].label == "Setting up Python"
        assert timestamps[-1].time_seconds == 4545  # 1:15:45
        assert timestamps[-1].label == "Final Project"
        
        # Verify chronological order
        for i in range(1, len(timestamps)):
            assert timestamps[i].time_seconds > timestamps[i-1].time_seconds
        
        # Validate all timestamps
        assert self.parser.validate_timestamps(timestamps) is True