from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.models import IssueRecommendation


class SavedIssueStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    html_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    score REAL NOT NULL,
                    issue_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    UNIQUE(client_id, html_url)
                )
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def list_saved(self, client_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, issue_json, saved_at
                FROM saved_issues
                WHERE client_id = ?
                ORDER BY saved_at DESC
                """,
                (client_id,),
            ).fetchall()
        return [self._row_to_response(row) for row in rows]

    def save_issue(self, client_id: str, issue: IssueRecommendation) -> dict[str, Any]:
        issue_dict = self._model_to_dict(issue)
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(issue_dict, ensure_ascii=True, default=str)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO saved_issues (client_id, html_url, title, repository, score, issue_json, saved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id, html_url) DO UPDATE SET
                    title = excluded.title,
                    repository = excluded.repository,
                    score = excluded.score,
                    issue_json = excluded.issue_json
                """,
                (client_id, issue.html_url, issue.title, issue.repository, issue.score, payload, now),
            )
            row = connection.execute(
                """
                SELECT id, issue_json, saved_at
                FROM saved_issues
                WHERE client_id = ? AND html_url = ?
                """,
                (client_id, issue.html_url),
            ).fetchone()
            connection.commit()
        return self._row_to_response(row)

    def delete_issue(self, client_id: str, saved_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_issues WHERE client_id = ? AND id = ?",
                (client_id, saved_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def _row_to_response(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "saved_id": row["id"],
            "saved_at": row["saved_at"],
            "issue": json.loads(row["issue_json"]),
        }

    def _model_to_dict(self, issue: IssueRecommendation) -> dict[str, Any]:
        if hasattr(issue, "model_dump"):
            return issue.model_dump(mode="json")
        return issue.dict()
