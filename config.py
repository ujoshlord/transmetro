from pathlib import Path
import tomllib

BASE_DIR = Path(__file__).resolve().parent
TOML_PATH = BASE_DIR / ".toml" 

with open(TOML_PATH, "rb") as f:
    config = tomllib.load(f)

DATABASE_URL = config.get("database", {}).get(
    "url",
    "postgresql://postgres.bygdirqnzcyvhdcnjege:TKCVsRDPbYHyGXpK@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
)

security_config = config.get("security", {})
app_config = config.get("app", {})

SECRET_KEY = security_config.get("secret_key", "transmetro-default-secret-key-2026")
APP_NAME = app_config.get("name", "Transmetro GT - Sistema de Gestión Operativa")
DEFAULT_PAGE_TITLE = app_config.get("default_page_title", "Transmetro Guatemala")
DEFAULT_PAGE_ICON = app_config.get("default_page_icon", "🚌")

DEFAULT_LATITUDE = 14.634915
DEFAULT_LONGITUDE = -90.506882
DEFAULT_ZOOM = 12
