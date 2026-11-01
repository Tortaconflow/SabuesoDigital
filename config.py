import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Server settings
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "sabueso_cidiks_secret_key_default_local")

# Database settings
DB_PATH_STR = os.getenv("DATABASE_PATH", "data/sabueso_cidiks.db")
PRODUCTION_DATABASE_PATH = (BASE_DIR / DB_PATH_STR).resolve()
DATABASE_PATH = PRODUCTION_DATABASE_PATH
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

BACKUPS_DIR = BASE_DIR / "data" / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def is_test_environment() -> bool:
    """Detecta si el código se está ejecutando bajo pytest o modo de pruebas."""
    return (
        os.environ.get("SABUESO_TESTING") == "1"
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def get_database_path() -> Path:
    """
    Resuelve dinámicamente la ruta de SQLite y bloquea de forma estricta
    cualquier acceso a la base comercial de producción desde pruebas automatizadas.
    """
    override = os.environ.get("SABUESO_DB_PATH")
    target = Path(override).resolve() if override else DATABASE_PATH.resolve()

    if is_test_environment() and target == PRODUCTION_DATABASE_PATH:
        raise RuntimeError(
            f"[BLOQUEO DE SEGURIDAD] Las pruebas automatizadas no tienen permitido conectarse "
            f"a la base de datos comercial de producción ({PRODUCTION_DATABASE_PATH}). "
            f"Configure SABUESO_DB_PATH hacia una base temporal aislada."
        )
    return target

# Screenshots directory
SCREENSHOTS_DIR = BASE_DIR / "static" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# External API Keys (Optional, safe fallback to free engines)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

# Playwright configuration
ENABLE_PLAYWRIGHT = os.getenv("ENABLE_PLAYWRIGHT", "true").lower() in ("true", "1", "yes")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in ("true", "1", "yes")
PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "15000"))

# HTTP Security Limits
MAX_RESPONSE_SIZE_BYTES = int(os.getenv("MAX_RESPONSE_SIZE_BYTES", str(5 * 1024 * 1024))) # 5MB max
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))

# Legacy JSON DB file path (relative to BASE_DIR for consistency)
PROSPECTS_DB_FILE = BASE_DIR / "prospectos_current.json"
