import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.config import Settings
from app.models.jobs import ExtractionPolicy, JobRecord, JobStatus

_EXTRA_COLUMNS = (
    ("duration_ms", "INTEGER"),
    ("cache_hit", "INTEGER DEFAULT 0"),
    ("document_path", "TEXT"),
    ("report_path", "TEXT"),
)


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_path = settings.extraction_database_path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS extraction_jobs (
                    job_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_filename TEXT,
                    source_path TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    policy_json TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    duration_ms INTEGER,
                    cache_hit INTEGER DEFAULT 0,
                    document_path TEXT,
                    report_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await self._ensure_columns(db)
            await db.commit()

    async def _ensure_columns(self, db: aiosqlite.Connection) -> None:
        async with db.execute("PRAGMA table_info(extraction_jobs)") as cursor:
            rows = await cursor.fetchall()
        existing = {row[1] for row in rows}
        for name, ddl in _EXTRA_COLUMNS:
            if name not in existing:
                await db.execute(f"ALTER TABLE extraction_jobs ADD COLUMN {name} {ddl}")

    async def create(self, job: JobRecord) -> JobRecord:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO extraction_jobs (
                    job_id, document_id, status, original_filename, source_path,
                    workspace_path, sha256, page_count, policy_json, error_code,
                    error_message, duration_ms, cache_hit, document_path, report_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.document_id,
                    job.status.value,
                    job.original_filename,
                    job.source_path,
                    job.workspace_path,
                    job.sha256,
                    job.page_count,
                    job.policy.model_dump_json(),
                    job.error_code,
                    job.error_message,
                    job.duration_ms,
                    1 if job.cache_hit else 0,
                    job.document_path,
                    job.report_path,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )
            await db.commit()
        return job

    async def get(self, job_id: str) -> JobRecord | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM extraction_jobs WHERE job_id = ?",
                (job_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    async def list_jobs(self, *, limit: int = 50) -> list[JobRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM extraction_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        cache_hit: bool | None = None,
        document_path: str | None = None,
        report_path: str | None = None,
    ) -> JobRecord | None:
        updated_at = datetime.now(timezone.utc)
        assignments = ["status = ?", "error_code = ?", "error_message = ?", "updated_at = ?"]
        values: list[object] = [
            status.value,
            error_code,
            error_message,
            updated_at.isoformat(),
        ]
        if duration_ms is not None:
            assignments.append("duration_ms = ?")
            values.append(duration_ms)
        if cache_hit is not None:
            assignments.append("cache_hit = ?")
            values.append(1 if cache_hit else 0)
        if document_path is not None:
            assignments.append("document_path = ?")
            values.append(document_path)
        if report_path is not None:
            assignments.append("report_path = ?")
            values.append(report_path)
        values.append(job_id)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE extraction_jobs SET {', '.join(assignments)} WHERE job_id = ?",
                values,
            )
            await db.commit()
        return await self.get(job_id)

    def _row_to_job(self, row: aiosqlite.Row) -> JobRecord:
        policy_data = json.loads(row["policy_json"])
        keys = row.keys()
        cache_hit = bool(row["cache_hit"]) if "cache_hit" in keys and row["cache_hit"] is not None else False
        return JobRecord(
            job_id=row["job_id"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            original_filename=row["original_filename"],
            source_path=row["source_path"],
            workspace_path=row["workspace_path"],
            sha256=row["sha256"],
            page_count=row["page_count"],
            policy=ExtractionPolicy.model_validate(policy_data),
            error_code=row["error_code"],
            error_message=row["error_message"],
            duration_ms=row["duration_ms"] if "duration_ms" in keys else None,
            cache_hit=cache_hit,
            document_path=row["document_path"] if "document_path" in keys else None,
            report_path=row["report_path"] if "report_path" in keys else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def resolve_workspace_file(workspace_path: str, filename: str) -> Path:
    workspace = Path(workspace_path).resolve()
    target = (workspace / filename).resolve()
    if workspace not in target.parents and target != workspace:
        raise ValueError("Resolved path escapes workspace.")
    return target
