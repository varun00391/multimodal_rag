import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_phase9_runtime():
    from app.execution.limits import reset_runtime_limits
    from app.observability.metrics import reset_metrics

    reset_runtime_limits()
    reset_metrics()
    yield
    reset_runtime_limits()
    reset_metrics()
