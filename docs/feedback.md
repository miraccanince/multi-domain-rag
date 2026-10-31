# Feedback System

Users can rate an answer with thumbs up (`1`) or thumbs down (`-1`) and add an optional comment. The ratings are stored so answer quality can be reviewed per domain.

## Components

- [rag/feedback_manager.py](../rag/feedback_manager.py): `FeedbackManager` stores entries in `storage/feedback.json`. Each entry has an ID, timestamp, question, answer (truncated to 500 characters), rating, comment, domain and a free-form metadata dict.
- It provides statistics (totals, satisfaction rate, per-domain breakdown), the most recent entries, the negative entries, and CSV or JSON export with optional start and end dates (`YYYY-MM-DD`).
- [api/main.py](../api/main.py): `POST /feedback` (rate limited to 30 per minute), `GET /feedback/stats` and `GET /feedback/export?format=csv|json&start_date=&end_date=`. None of these endpoints require authentication.
- [frontend/app.py](../frontend/app.py): thumbs up/down buttons under each answer, and an analytics tab that shows the statistics and exports the data.

## Storage

The store is a single JSON file that is rewritten on each save. It is not safe for several writer processes and is not meant for large volumes. The `storage/` directory is git-ignored, so feedback is never committed.

## Tests

[tests/test_feedback_manager.py](../tests/test_feedback_manager.py) covers saving, statistics, domain breakdown, recent and negative entries, truncation, persistence, ID uniqueness and the exports, including date filters computed relative to today.

## Not implemented

Notifications, trend charts over time, and use of the feedback to change retrieval or ranking. The ratings are only collected and reported.
