"""
Unit tests for FeedbackManager - User feedback collection and analytics
"""

import pytest
import json
import tempfile
from pathlib import Path
from src.feedback_manager import FeedbackManager


class TestFeedbackManager:
    """Test feedback management functionality."""

    @pytest.fixture
    def temp_feedback_file(self):
        """Create temporary feedback file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.write('[]')
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def feedback_mgr(self, temp_feedback_file):
        """Create FeedbackManager instance with temp file."""
        return FeedbackManager(feedback_file=temp_feedback_file)

    def test_save_feedback(self, feedback_mgr):
        """Test saving feedback."""
        entry = feedback_mgr.save_feedback(
            question="What is CAN?",
            answer="CAN is a vehicle bus standard",
            rating=1,
            comment="Very helpful!",
            domain="automotive"
        )

        assert entry['question'] == "What is CAN?"
        assert entry['rating'] == 1
        assert entry['comment'] == "Very helpful!"
        assert entry['domain'] == "automotive"
        assert 'id' in entry
        assert 'timestamp' in entry

    def test_negative_feedback(self, feedback_mgr):
        """Test saving negative feedback."""
        entry = feedback_mgr.save_feedback(
            question="Test question",
            answer="Test answer",
            rating=-1,
            comment="Not accurate"
        )

        assert entry['rating'] == -1
        assert entry['comment'] == "Not accurate"

    def test_get_statistics_empty(self, feedback_mgr):
        """Test statistics with no feedback."""
        stats = feedback_mgr.get_statistics()

        assert stats['total_feedback'] == 0
        assert stats['positive'] == 0
        assert stats['negative'] == 0
        assert stats['satisfaction_rate'] == 0.0

    def test_get_statistics(self, feedback_mgr):
        """Test statistics calculation."""
        # Add positive feedback
        feedback_mgr.save_feedback("Q1", "A1", rating=1, domain="automotive")
        feedback_mgr.save_feedback("Q2", "A2", rating=1, domain="fashion")

        # Add negative feedback
        feedback_mgr.save_feedback("Q3", "A3", rating=-1, domain="automotive")

        stats = feedback_mgr.get_statistics()

        assert stats['total_feedback'] == 3
        assert stats['positive'] == 2
        assert stats['negative'] == 1
        assert stats['satisfaction_rate'] == 66.67

    def test_domain_breakdown(self, feedback_mgr):
        """Test domain-level statistics."""
        feedback_mgr.save_feedback("Q1", "A1", rating=1, domain="automotive")
        feedback_mgr.save_feedback("Q2", "A2", rating=1, domain="automotive")
        feedback_mgr.save_feedback("Q3", "A3", rating=-1, domain="fashion")

        stats = feedback_mgr.get_statistics()
        domain_stats = stats['by_domain']

        assert 'automotive' in domain_stats
        assert 'fashion' in domain_stats
        assert domain_stats['automotive']['positive'] == 2
        assert domain_stats['automotive']['negative'] == 0
        assert domain_stats['fashion']['positive'] == 0
        assert domain_stats['fashion']['negative'] == 1

    def test_get_recent_feedback(self, feedback_mgr):
        """Test retrieving recent feedback."""
        # Add 5 feedback entries
        for i in range(5):
            feedback_mgr.save_feedback(
                question=f"Question {i}",
                answer=f"Answer {i}",
                rating=1
            )

        recent = feedback_mgr.get_recent_feedback(limit=3)

        assert len(recent) == 3
        # Should be in reverse chronological order
        assert recent[0]['question'] == "Question 4"
        assert recent[1]['question'] == "Question 3"
        assert recent[2]['question'] == "Question 2"

    def test_get_negative_feedback(self, feedback_mgr):
        """Test retrieving only negative feedback."""
        feedback_mgr.save_feedback("Q1", "A1", rating=1)
        feedback_mgr.save_feedback("Q2", "A2", rating=-1, comment="Bad")
        feedback_mgr.save_feedback("Q3", "A3", rating=1)
        feedback_mgr.save_feedback("Q4", "A4", rating=-1, comment="Wrong")

        negative = feedback_mgr.get_negative_feedback()

        assert len(negative) == 2
        assert all(f['rating'] == -1 for f in negative)
        assert negative[0]['comment'] == "Bad"
        assert negative[1]['comment'] == "Wrong"

    def test_answer_truncation(self, feedback_mgr):
        """Test that long answers are truncated."""
        long_answer = "A" * 1000

        entry = feedback_mgr.save_feedback(
            question="Test",
            answer=long_answer,
            rating=1
        )

        # Should be truncated to 500 chars
        assert len(entry['answer']) == 500

    def test_metadata_storage(self, feedback_mgr):
        """Test storing custom metadata."""
        entry = feedback_mgr.save_feedback(
            question="Test",
            answer="Test answer",
            rating=1,
            metadata={"response_time": 2.5, "chunks_used": 3}
        )

        assert entry['metadata']['response_time'] == 2.5
        assert entry['metadata']['chunks_used'] == 3

    def test_persistence(self, temp_feedback_file):
        """Test that feedback persists across instances."""
        # Save feedback with first instance
        mgr1 = FeedbackManager(feedback_file=temp_feedback_file)
        mgr1.save_feedback("Q1", "A1", rating=1)

        # Load with second instance
        mgr2 = FeedbackManager(feedback_file=temp_feedback_file)
        stats = mgr2.get_statistics()

        assert stats['total_feedback'] == 1

    def test_unique_ids(self, feedback_mgr):
        """Test that feedback IDs are unique."""
        entry1 = feedback_mgr.save_feedback("Q1", "A1", rating=1)
        entry2 = feedback_mgr.save_feedback("Q2", "A2", rating=1)

        assert entry1['id'] != entry2['id']
        assert entry1['id'].startswith('fb_')
        assert entry2['id'].startswith('fb_')
