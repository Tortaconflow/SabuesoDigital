import os
import sys
import hashlib
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
import db


def _compute_file_sha256(filepath: Path) -> str:
    if not filepath.exists():
        return "NON_EXISTENT"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def verify_production_db_untouched_across_session():
    """
    Guardia de sesión completa: calcula el SHA-256 de la base comercial real
    antes y después de ejecutar toda la suite de pytest. Falla inmediatamente
    si cualquier prueba altera un solo byte de data/sabueso_cidiks.db.
    """
    prod_path = config.PRODUCTION_DATABASE_PATH.resolve()
    sha_before = _compute_file_sha256(prod_path)
    mtime_before = prod_path.stat().st_mtime_ns if prod_path.exists() else None

    yield

    sha_after = _compute_file_sha256(prod_path)
    mtime_after = prod_path.stat().st_mtime_ns if prod_path.exists() else None
    assert sha_before == sha_after, (
        f"[VIOLACIÓN CRÍTICA DE AISLAMIENTO] La base de producción {prod_path} "
        f"cambió durante pytest! SHA antes={sha_before}, SHA después={sha_after}"
    )
    assert mtime_before == mtime_after, (
        f"[VIOLACIÓN CRÍTICA DE AISLAMIENTO] El timestamp de {prod_path} "
        f"fue modificado durante pytest!"
    )


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    """
    Aísla cada prueba individual en su propio archivo SQLite temporal dentro de tmp_path.
    Desactiva la migración automática de prospectos_current.json para que cada test
    inicie con una base limpia y determinista.
    """
    test_db_file = tmp_path / "test_sabueso_isolated.db"
    monkeypatch.setenv("SABUESO_DB_PATH", str(test_db_file))
    monkeypatch.setenv("SABUESO_SKIP_LEGACY_MIGRATION", "1")
    db.init_db()
    yield test_db_file
