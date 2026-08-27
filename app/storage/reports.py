import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_model_json(path: Path, model: BaseModel | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(mode="json") if isinstance(model, BaseModel) else model
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
