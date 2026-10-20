"""Infraestructura de autenticación compartida por los routers.

El limiter de SlowAPI vive acá y los routers lo importan desde este módulo.
Las dependencias de autorización están en `services/authz.py`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from services.authz import current_user, require_admin, require_soporte

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

__all__ = ["current_user", "limiter", "require_admin", "require_soporte"]
