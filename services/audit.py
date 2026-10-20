"""Auditoría de eventos de seguridad.

Se registran login exitoso/fallido, refresh, logout, cambios de rol y
cambios de estado. **Nunca** se registran contraseñas ni tokens: del token
solo se anota el `jti` (identificador aleatorio, no el token en sí).
"""

import logging

logger = logging.getLogger("security")


def registrar_evento(
    evento: str,
    *,
    usuario: str | None = None,
    ip: str | None = None,
    resultado: str = "ok",
    detalle: str | None = None,
) -> None:
    """Escribe un evento de seguridad en el log."""
    logger.info(
        "security_event=%s usuario=%s ip=%s resultado=%s detalle=%s",
        evento,
        usuario or "-",
        ip or "-",
        resultado,
        detalle or "-",
    )


def registrar_error(
    evento: str,
    *,
    usuario: str | None = None,
    ip: str | None = None,
    detalle: str | None = None,
) -> None:
    """Igual que `registrar_evento` pero con nivel de error."""
    logger.warning(
        "security_event=%s usuario=%s ip=%s resultado=error detalle=%s",
        evento,
        usuario or "-",
        ip or "-",
        detalle or "-",
    )
