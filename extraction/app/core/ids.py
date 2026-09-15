import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def document_id() -> str:
    return new_id("doc")


def job_id() -> str:
    return new_id("job")


def review_id() -> str:
    return new_id("rev")


def region_id(page_number: int, index: int) -> str:
    return f"p{page_number:04d}_r{index:04d}"


def element_id(kind: str, page_number: int, index: int) -> str:
    return f"{kind}_p{page_number:04d}_{index:04d}"
