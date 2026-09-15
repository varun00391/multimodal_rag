from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import DocumentNotFoundError, JobNotFoundError
from app.models.common import JobStatus
from app.models.document import DocumentRecord, JobRecord, ReviewItem

_LOCK = threading.Lock()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, db_path: Path | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.sqlite_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _tx(self):
        with _LOCK:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    page_count INTEGER,
                    status TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_code TEXT,
                    warnings TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS review_items (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    region_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    bbox TEXT NOT NULL DEFAULT '[]',
                    candidates TEXT NOT NULL DEFAULT '[]',
                    confidence REAL,
                    decision TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_review_document ON review_items(document_id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def create_document(self, document: DocumentRecord) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, filename, content_type, sha256, size_bytes, page_count,
                    status, job_id, created_at, updated_at, error_code, warnings
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.filename,
                    document.content_type,
                    document.sha256,
                    document.size_bytes,
                    document.page_count,
                    document.status.value,
                    document.job_id,
                    document.created_at,
                    document.updated_at,
                    document.error_code,
                    json.dumps(document.warnings),
                ),
            )

    def create_job(self, job: JobRecord) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, document_id, status, current_step, error_code, error_message,
                    created_at, updated_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.document_id,
                    job.status.value,
                    job.current_step,
                    job.error_code,
                    job.error_message,
                    job.created_at,
                    job.updated_at,
                    job.started_at,
                    job.finished_at,
                ),
            )

    def get_document(self, document_id: str) -> DocumentRecord:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return self._document_from_row(row)

    def get_job(self, job_id: str) -> JobRecord:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job {job_id} was not found.")
        return self._job_from_row(row)

    def get_job_for_document(self, document_id: str) -> JobRecord:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
                (document_id,),
            ).fetchone()
        if row is None:
            raise JobNotFoundError(f"No job found for document {document_id}.")
        return self._job_from_row(row)

    def update_document(
        self,
        document_id: str,
        *,
        status: JobStatus | None = None,
        page_count: int | None = None,
        error_code: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        document = self.get_document(document_id)
        with self._tx() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status = ?, page_count = ?, error_code = ?, warnings = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    (status or document.status).value,
                    page_count if page_count is not None else document.page_count,
                    error_code if error_code is not None else document.error_code,
                    json.dumps(warnings if warnings is not None else document.warnings),
                    utcnow(),
                    document_id,
                ),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        current_step: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        job = self.get_job(job_id)
        now = utcnow()
        with self._tx() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_step = ?, error_code = ?, error_message = ?,
                    updated_at = ?, started_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    (status or job.status).value,
                    current_step if current_step is not None else job.current_step,
                    error_code if error_code is not None else job.error_code,
                    error_message if error_message is not None else job.error_message,
                    now,
                    now if started else job.started_at,
                    now if finished else job.finished_at,
                    job_id,
                ),
            )

    def claim_next_queued(self) -> JobRecord | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                (JobStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None
            now = utcnow()
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_step = ?, updated_at = ?, started_at = ?
                WHERE id = ?
                """,
                (JobStatus.PROFILING.value, "profiling", now, now, row["id"]),
            )
            conn.execute(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
                (JobStatus.PROFILING.value, now, row["document_id"]),
            )
        job = self._job_from_row(row)
        job.status = JobStatus.PROFILING
        job.current_step = "profiling"
        job.started_at = now
        job.updated_at = now
        return job

    def create_review_item(self, item: ReviewItem) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO review_items (
                    id, document_id, region_id, page_number, status, reason, bbox,
                    candidates, confidence, decision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.document_id,
                    item.region_id,
                    item.page_number,
                    item.status,
                    item.reason,
                    json.dumps(item.bbox),
                    json.dumps(item.candidates),
                    item.confidence,
                    json.dumps(item.decision) if item.decision else None,
                    item.created_at,
                    item.updated_at,
                ),
            )

    def list_review_items(self, document_id: str) -> list[ReviewItem]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items WHERE document_id = ? ORDER BY created_at ASC",
                (document_id,),
            ).fetchall()
        return [self._review_from_row(row) for row in rows]

    def get_review_item(self, review_id: str) -> ReviewItem:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM review_items WHERE id = ?", (review_id,)
            ).fetchone()
        if row is None:
            raise DocumentNotFoundError(f"Review item {review_id} was not found.")
        return self._review_from_row(row)

    def resolve_review_item(self, review_id: str, decision: dict) -> ReviewItem:
        item = self.get_review_item(review_id)
        now = utcnow()
        with self._tx() as conn:
            conn.execute(
                """
                UPDATE review_items
                SET status = ?, decision = ?, updated_at = ?
                WHERE id = ?
                """,
                ("RESOLVED", json.dumps(decision), now, review_id),
            )
        item.status = "RESOLVED"
        item.decision = decision
        item.updated_at = now
        return item

    def pending_review_count(self, document_id: str) -> int:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM review_items WHERE document_id = ? AND status = 'PENDING'",
                (document_id,),
            ).fetchone()
        return int(row["n"]) if row else 0

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            filename=row["filename"],
            content_type=row["content_type"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            page_count=row["page_count"],
            status=JobStatus(row["status"]),
            job_id=row["job_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_code=row["error_code"],
            warnings=json.loads(row["warnings"] or "[]"),
        )

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            current_step=row["current_step"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> ReviewItem:
        return ReviewItem(
            id=row["id"],
            document_id=row["document_id"],
            region_id=row["region_id"],
            page_number=row["page_number"],
            status=row["status"],
            reason=row["reason"],
            bbox=json.loads(row["bbox"] or "[]"),
            candidates=json.loads(row["candidates"] or "[]"),
            confidence=row["confidence"],
            decision=json.loads(row["decision"]) if row["decision"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


_REPO: Repository | None = None


def get_repository() -> Repository:
    global _REPO
    if _REPO is None:
        _REPO = Repository()
    return _REPO
