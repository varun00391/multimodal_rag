from app.db.repository import get_repository
from app.ingestion.storage import get_storage


def get_repo():
    return get_repository()


def storage():
    return get_storage()
