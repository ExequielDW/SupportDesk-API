"""Configuración central de la aplicación.

Todos los secretos y parámetros salen de `.env` (nunca hardcodeados).
`decouple` se encarga de leer el archivo; `config.py` es el único lugar
donde se decide qué variable existe y qué valor por defecto tiene.
"""

from decouple import config

# --- Entorno ---------------------------------------------------------------
ENVIRONMENT = config("ENVIRONMENT", default="development")
IS_PRODUCTION = ENVIRONMENT.strip().lower() == "production"

# --- MongoDB ---------------------------------------------------------------
# MONGODB_FAKE=true levanta la API con un MongoDB en memoria: sirve para
# probar la app y para la demo del repositorio, sin cluster ni Docker.
MONGODB_FAKE = config("MONGODB_FAKE", default="false", cast=bool)
MONGODB_URI = config("URI", default="")
DB_NAME = config("DB_NAME", default="supportdesk")
POOL_MAX_SIZE = int(config("POOL_MAX_SIZE", default=10))
POOL_MIN_SIZE = int(config("POOL_MIN_SIZE", default=1))

# --- JWT / sesiones --------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
ALGORITHM = config("ALGORITHM", default="HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(config("ACCESS_TOKEN_EXPIRE_MINUTES", default=15))
REFRESH_TOKEN_EXPIRE_DAYS = int(config("REFRESH_TOKEN_EXPIRE_DAYS", default=7))
JWT_ISSUER = config("JWT_ISSUER", default="supportdesk-api")
JWT_AUDIENCE = config("JWT_AUDIENCE", default="supportdesk-clients")

# --- Redis -----------------------------------------------------------------
# Si queda vacío o no responde, la app sigue funcionando con un cache en
# memoria (solo apto para un solo proceso: ver docs/SECURITY.md).
REDIS_URL = config("REDIS_URL", default="")

# --- HTTP ------------------------------------------------------------------
def _lista(valor: str) -> list[str]:
    """Convierte "a,b,c" en ["a", "b", "c"] (ignora entradas vacías)."""
    return [item.strip() for item in valor.split(",") if item.strip()]


CORS_ORIGINS = _lista(config("CORS_ORIGINS", default=""))
ALLOWED_HOSTS = _lista(config("ALLOWED_HOSTS", default="localhost,127.0.0.1"))
COOKIE_SECURE = config("COOKIE_SECURE", default="false", cast=bool)
COOKIE_NAME = "sd_refresh"
COOKIE_SAMESITE = "lax"
BODY_LIMIT_BYTES = int(config("BODY_LIMIT_BYTES", default=102400))

# --- Rate limiting ---------------------------------------------------------
LOGIN_MAX_POR_USUARIO = int(config("LOGIN_MAX_POR_USUARIO", default=5))
LOGIN_VENTANA_SEGUNDOS = int(config("LOGIN_VENTANA_SEGUNDOS", default=60))
LOGIN_MAX_HORARIO_POR_USUARIO = int(config("LOGIN_MAX_HORARIO_POR_USUARIO", default=10))
CACHE_USUARIO_TTL = int(config("CACHE_USUARIO_TTL", default=60))
CACHE_STATS_TTL = int(config("CACHE_STATS_TTL", default=30))
