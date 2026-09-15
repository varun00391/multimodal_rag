from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionEvidence:
    engine: str
    model_version: str = ""
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    bbox: list[float] = field(default_factory=list)
    confidence: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, **kwargs) -> ExtractionEvidence | None:
        ...
