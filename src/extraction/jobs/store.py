from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from extraction.models.jobs import JobRecord

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._connect() as conn:
            conn.execute(CREATE_SQL)
            conn.execute("PRAGMA journal_mode=WAL;")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, job_id: str, document_id: str, filename: str) -> JobRecord:
        now = utcnow()
        record = JobRecord(
            job_id=job_id,
            document_id=document_id,
            filename=filename,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, document_id, filename, status, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, ?, ?)
                """,
                (record.job_id, record.document_id, record.filename, record.status, now, now),
            )
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRecord.model_validate(dict(row))

    def claim_next(self) -> JobRecord | None:
        now = utcnow()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE jobs SET status = 'running', updated_at = ? WHERE job_id = ? AND status = 'queued'",
                (now, row["job_id"]),
            )
            updated = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return JobRecord.model_validate(dict(updated))

    def complete(self, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'completed', updated_at = ?, error = NULL WHERE job_id = ?",
                (utcnow(), job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', updated_at = ?, error = ? WHERE job_id = ?",
                (utcnow(), error, job_id),
            )
