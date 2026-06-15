from __future__ import annotations

from pathlib import Path

import pytest

from nl2uri.domain_registry import repo_root as registry_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return registry_root()
