from pydantic import BaseModel, Field


class ValidationFailure(BaseModel):
    code: str
    message: str
    element_id: str | None = None
    details: dict[str, str | float | int | bool] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    page: int
    confidence: float
    passed: bool
    failures: list[ValidationFailure] = Field(default_factory=list)
