"""
Configuración central de la aplicación Transmetro Streamlit.
Carga las variables de entorno desde .env y expone parámetros del sistema.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Base de datos
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.bygdirqnzcyvhdcnjege:TKCVsRDPbYHyGXpK@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
)

# Seguridad y sesión
SECRET_KEY = os.getenv("SECRET_KEY", "transmetro-default-secret-key-2026")
APP_NAME = os.getenv("APP_NAME", "Transmetro GT - Sistema de Gestión Operativa")
DEFAULT_PAGE_TITLE = os.getenv("DEFAULT_PAGE_TITLE", "Transmetro Guatemala")
DEFAULT_PAGE_ICON = os.getenv("DEFAULT_PAGE_ICON", "🚌")

# Constantes de negocio
DEFAULT_LATITUDE = 14.634915
DEFAULT_LONGITUDE = -90.506882
DEFAULT_ZOOM = 12
