"""
Feedback Manager - Collect and analyze user feedback.

This module provides:
- Feedback collection (thumbs up/down, ratings, comments)
- Feedback storage (JSON file)
- Feedback analytics
- Answer quality tracking

Usage:
    from src.feedback_manager import FeedbackManager

    feedback_mgr = FeedbackManager()
    feedback_mgr.save_feedback(
        question="What is CAN?",
        answer="CAN is...",
        rating=1,  # 1 = thumbs up, -1 = thumbs down
        comment="Very helpful!"
    )
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import csv
import io


class FeedbackManager:
    """
    Manage user feedback for answer quality tracking.

    Features:
    - Save feedback to JSON file
    - Get feedback statistics
    - Track answer quality over time
    - Identify problematic queries
    """

    def __init__(self, feedback_file: str = "feedback/feedback_store.json"):
        """
        Initialize feedback manager.

        Args:
            feedback_file: Path to feedback JSON file
        """
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(exist_ok=True)

        # Create file if doesn't exist
        if not self.feedback_file.exists():
            self.feedback_file.write_text("[]")

    def save_feedback(
        self,
        question: str,
        answer: str,
        rating: int,
        comment: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Save user feedback.

        Args:
            question: User's question
            answer: System's answer
            rating: 1 (thumbs up) or -1 (thumbs down)
            comment: Optional user comment
            domain: Domain used for query
            metadata: Additional metadata (response time, etc.)

        Returns:
            Saved feedback entry
        """
        feedback_entry = {
            "id": self._generate_id(),
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer[:500],  # Truncate long answers
            "rating": rating,
            "comment": comment,
            "domain": domain,
            "metadata": metadata or {}
        }

        # Load existing feedback
        feedbacks = self._load_feedbacks()

        # Add new feedback
        feedbacks.append(feedback_entry)

        # Save back to file
        self._save_feedbacks(feedbacks)

        return feedback_entry

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get feedback statistics.

        Returns:
            Dictionary with feedback stats
        """
        feedbacks = self._load_feedbacks()

        if not feedbacks:
            return {
                "total_feedback": 0,
                "positive": 0,
                "negative": 0,
                "satisfaction_rate": 0.0
            }

        positive = sum(1 for f in feedbacks if f["rating"] > 0)
        negative = sum(1 for f in feedbacks if f["rating"] < 0)
        total = len(feedbacks)

        # Domain breakdown
        domain_stats = {}
        for f in feedbacks:
            domain = f.get("domain", "unknown")
            if domain not in domain_stats:
                domain_stats[domain] = {"positive": 0, "negative": 0}

            if f["rating"] > 0:
                domain_stats[domain]["positive"] += 1
            else:
                domain_stats[domain]["negative"] += 1

        return {
            "total_feedback": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": round((positive / total * 100), 2) if total > 0 else 0.0,
            "by_domain": domain_stats
        }

    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent feedback entries.

        Args:
            limit: Number of entries to return

        Returns:
            List of recent feedback entries
        """
        feedbacks = self._load_feedbacks()
        return list(reversed(feedbacks[-limit:]))

    def get_negative_feedback(self) -> List[Dict[str, Any]]:
        """
        Get all negative feedback for analysis.

        Returns:
            List of negative feedback entries
        """
        feedbacks = self._load_feedbacks()
        return [f for f in feedbacks if f["rating"] < 0]

    def _load_feedbacks(self) -> List[Dict[str, Any]]:
        """Load all feedbacks from file."""
        try:
            with open(self.feedback_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_feedbacks(self, feedbacks: List[Dict[str, Any]]):
        """Save feedbacks to file."""
        with open(self.feedback_file, 'w') as f:
            json.dump(feedbacks, f, indent=2)

    def export_to_csv(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """
        Export feedback to CSV format.

        Args:
            start_date: Filter from this date (ISO format: YYYY-MM-DD)
            end_date: Filter until this date (ISO format: YYYY-MM-DD)

        Returns:
            CSV string
        """
        feedbacks = self._load_feedbacks()

        # Filter by date if provided
        if start_date or end_date:
            filtered = []
            for f in feedbacks:
                timestamp = f['timestamp'][:10]  # Get date part
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered.append(f)
            feedbacks = filtered

        # Create CSV
        output = io.StringIO()
        if feedbacks:
            fieldnames = ['id', 'timestamp', 'question', 'answer', 'rating', 'comment', 'domain']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for feedback in feedbacks:
                writer.writerow({
                    'id': feedback.get('id', ''),
                    'timestamp': feedback.get('timestamp', ''),
                    'question': feedback.get('question', ''),
                    'answer': feedback.get('answer', ''),
                    'rating': feedback.get('rating', 0),
                    'comment': feedback.get('comment', ''),
                    'domain': feedback.get('domain', '')
                })

        return output.getvalue()

    def export_to_json(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """
        Export feedback to JSON format.

        Args:
            start_date: Filter from this date (ISO format: YYYY-MM-DD)
            end_date: Filter until this date (ISO format: YYYY-MM-DD)

        Returns:
            JSON string
        """
        feedbacks = self._load_feedbacks()

        # Filter by date if provided
        if start_date or end_date:
            filtered = []
            for f in feedbacks:
                timestamp = f['timestamp'][:10]  # Get date part
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                filtered.append(f)
            feedbacks = filtered

        return json.dumps(feedbacks, indent=2)

    def _generate_id(self) -> str:
        """Generate unique feedback ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"fb_{timestamp}"


# Global instance
_feedback_manager = None


def get_feedback_manager(feedback_file: str = "feedback/feedback_store.json") -> FeedbackManager:
    """
    Get global feedback manager instance (singleton).

    Args:
        feedback_file: Path to feedback file

    Returns:
        FeedbackManager instance
    """
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager(feedback_file=feedback_file)
    return _feedback_manager
