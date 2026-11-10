"""Put the monorepo's three source roots on sys.path for the test run.

The packages the code imports — ``app`` (server/), ``reading`` (services/ocr/)
and ``shared`` (repo root) — are not pip-installed; they are resolved by path
(see pyproject.toml's ``[tool.pytest.ini_options] pythonpath`` and the Makefile
``dev`` target). pytest already honours that ``pythonpath`` key, so this file is
belt-and-suspenders: it guarantees the same three roots are importable even when
a tool loads conftest without reading the ini options, and it pins them to the
repo root so the test's own working directory cannot change what resolves.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT, _ROOT / "server", _ROOT / "services" / "ocr"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)
