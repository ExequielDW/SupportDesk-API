# ADR 0003 — Refresh tokens rotativos con revocación

**Estado:** aceptado · **Fecha:** 2026-10-20

## Contexto
El token de acceso duraba 30 minutos, no se podía revocar y el `sub` era el
username (mutable: si el usuario cambiaba su nombre, el token quedaba huérfano).
No había forma de cerrar sesión de verdad.

## Decisión
- **Access token**: 15 min. Claims: `sub` (id de usuario), `rol`, `typ="access"`,
  `jti`, `iat`, `exp`, `iss`, `aud`.
- **Refresh token**: 7 días, `typ="refresh"`, con `jti` y `fam` (familia de sesión).
  Se entrega en **cookie `httpOnly` + `Secure` + `SameSite=Lax`**.
- **Allowlist en Redis** (`refresh:{jti}`): un refresh sin su `jti` en Redis es inválido
  → el logout revoca de verdad.
- **Rotación**: cada refresh emite un `jti` nuevo e invalida el anterior
  (`refresh:used:{jti}`). Si llega un `jti` ya rotado → **reuso** → se revoca la
  familia completa (`refresh:revoked:{fam}`) y se corta la sesión.
- `typ`, `iss` y `aud` se validan: un refresh no sirve como access token.

## Alternativas consideradas
- **Solo access token**: más simple, pero obliga a re-loguear cada 15-30 min.
- **Blacklist en vez de allowlist**: la allowlist falla de forma segura (si Redis
  se pierde, los refresh quedan invalidados) y no necesita limpiar entradas vencidas.

## Consecuencias
- Redis pasa a ser dependencia de la autenticación (con fallback en memoria en dev).
- `POST /usuarios/refresh` y `POST /usuarios/logout` son nuevos.
