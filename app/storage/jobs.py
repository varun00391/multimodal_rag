import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.config import Settings
from app.models.jobs import ExtractionPolicy, JobRecord, JobStatus


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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def create(self, job: JobRecord) -> JobRecord:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO extraction_jobs (
                    job_id, document_id, status, original_filename, source_path,
                    workspace_path, sha256, page_count, policy_json, error_code,
                    error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord | None:
        updated_at = datetime.now(timezone.utc)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE extraction_jobs
                SET status = ?, error_code = ?, error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    error_code,
                    error_message,
                    updated_at.isoformat(),
                    job_id,
                ),
            )
            await db.commit()
        return await self.get(job_id)

    def _row_to_job(self, row: aiosqlite.Row) -> JobRecord:
        policy_data = json.loads(row["policy_json"])
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
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def resolve_workspace_file(workspace_path: str, filename: str) -> Path:
    workspace = Path(workspace_path).resolve()
    target = (workspace / filename).resolve()
    if workspace not in target.parents and target != workspace:
        raise ValueError("Resolved path escapes workspace.")
    return target
