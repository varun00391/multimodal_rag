from pydantic import BaseModel, Field

from app.models.common import ConfidenceBand, ValidationStatus


class EvidenceCandidate(BaseModel):
    value: str
    sources: list[str] = Field(default_factory=list)
    confidence: float | None = None


class ValidationResult(BaseModel):
    confidence: float = 0.0
    band: ConfidenceBand = ConfidenceBand.LOW
    status: ValidationStatus = ValidationStatus.PARTIAL
    reasons: list[str] = Field(default_factory=list)
    needs_review: bool = False
    candidates: list[EvidenceCandidate] = Field(default_factory=list)
    checks: dict[str, bool | str | float] = Field(default_factory=dict)
