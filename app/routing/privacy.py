from app.models.jobs import ExtractionPolicy


def managed_apis_allowed(policy: ExtractionPolicy) -> bool:
    return bool(policy.allow_managed_apis)


def privacy_mode(policy: ExtractionPolicy) -> str:
    return "managed" if managed_apis_allowed(policy) else "local"
