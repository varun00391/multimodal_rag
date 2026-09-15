from fastapi import APIRouter, HTTPException

from app.api.deps import get_repo
from app.core.exceptions import JobNotFoundError

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        job = get_repo().get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return job.model_dump()
