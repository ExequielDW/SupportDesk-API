"""Middlewares de la aplicación."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import BODY_LIMIT_BYTES, IS_PRODUCTION


class LimiteBodyMiddleware(BaseHTTPMiddleware):
    """Rechaza cuerpos demasiado grandes (protección contra DoS de memoria)."""

    def __init__(self, app, limite: int = BODY_LIMIT_BYTES) -> None:
        super().__init__(app)
        self.limite = limite

    async def dispatch(self, request: Request, call_next) -> Response:
        largo = request.headers.get("content-length")
        if largo is not None:
            try:
                if int(largo) > self.limite:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "El cuerpo de la petición es demasiado grande"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "Content-Length inválido"}
                )
        return await call_next(request)


class HeadersSeguridadMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad a todas las respuestas."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if IS_PRODUCTION:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class TiempoProcesamientoMiddleware(BaseHTTPMiddleware):
    """Mide el tiempo de cada request y lo expone en `X-Process-Time`."""

    async def dispatch(self, request: Request, call_next) -> Response:
        inicio = time.perf_counter()
        response = await call_next(request)
        transcurrido = time.perf_counter() - inicio
        response.headers["X-Process-Time"] = f"{transcurrido * 1000:.2f}ms"
        return response
