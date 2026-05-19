from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.models import IssueRecommendation


SAVED_ISSUES_LIMIT = 10


class SavedIssueStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: ThreadedConnectionPool | None = None

    def init(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saved_issues (
                        id SERIAL PRIMARY KEY,
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

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def _connect(self) -> Iterator[psycopg2.extensions.connection]:
        pool = self._ensure_pool()
        connection = pool.getconn()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            pass
        finally:
            pool.putconn(connection)

    def _ensure_pool(self) -> ThreadedConnectionPool:
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        if not self._pool:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=self.database_url,
            )
        return self._pool

    def list_saved(self, client_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, issue_json, saved_at
                    FROM saved_issues
                    WHERE client_id = %s
                    ORDER BY saved_at DESC
                    """,
                    (client_id,),
                )
                rows = cursor.fetchall()
        return [self._row_to_response(row) for row in rows]

    def save_issue(self, client_id: str, issue: IssueRecommendation) -> dict[str, Any]:
        issue_dict = self._model_to_dict(issue)
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(issue_dict, ensure_ascii=True, default=str)
        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM saved_issues
                    WHERE client_id = %s AND html_url = %s
                    """,
                    (client_id, issue.html_url),
                )
                already_saved = cursor.fetchone() is not None

                if not already_saved:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS saved_count
                        FROM saved_issues
                        WHERE client_id = %s
                        """,
                        (client_id,),
                    )
                    count_row = cursor.fetchone()
                    saved_count = int(count_row["saved_count"]) if count_row else 0
                    if saved_count >= SAVED_ISSUES_LIMIT:
                        raise ValueError("limit_reached")

                cursor.execute(
                    """
                    INSERT INTO saved_issues (client_id, html_url, title, repository, score, issue_json, saved_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(client_id, html_url) DO UPDATE SET
                        title = excluded.title,
                        repository = excluded.repository,
                        score = excluded.score,
                        issue_json = excluded.issue_json
                    """,
                    (client_id, issue.html_url, issue.title, issue.repository, issue.score, payload, now),
                )
                cursor.execute(
                    """
                    SELECT id, issue_json, saved_at
                    FROM saved_issues
                    WHERE client_id = %s AND html_url = %s
                    """,
                    (client_id, issue.html_url),
                )
                row = cursor.fetchone()
                connection.commit()
        return self._row_to_response(row)

    def delete_issue(self, client_id: str, saved_id: int) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM saved_issues WHERE client_id = %s AND id = %s",
                    (client_id, saved_id),
                )
                deleted = cursor.rowcount > 0
                connection.commit()
        return deleted

    def _row_to_response(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "saved_id": row["id"],
            "saved_at": row["saved_at"],
            "issue": json.loads(row["issue_json"]),
        }

    def _model_to_dict(self, issue: IssueRecommendation) -> dict[str, Any]:
        if hasattr(issue, "model_dump"):
            return issue.model_dump(mode="json")
        return issue.dict()
