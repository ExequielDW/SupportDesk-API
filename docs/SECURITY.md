# Guía de Seguridad — SupportDesk API

## 1. Estado de los secretos

| Comprobación | Resultado | Cómo se verificó |
| :--- | :--- | :--- |
| La URI de Mongo estuvo alguna vez en git | **No** | `git log --all -p \| grep mongodb+srv` → vacío |
| `.env` trackeado por git | **No** | `git ls-files --error-unmatch .env` → error |
| `.env` ignorado | **Sí** | `.gitignore:7` (`*.env`) |
| Secretos hardcodeados en el código | **No** | todo sale de `config()` / `config.py` |
| `SECRET_KEY` con entropía suficiente | **Sí** | hex de 64 chars (256 bits), no es un placeholder |

### Procedimiento para rotar un secreto

1. `SECRET_KEY`: generar `python -c "import secrets; print(secrets.token_hex(32))"` y reemplazar en `.env`.
   **Invalida todos los tokens emitidos** (access y refresh) → ejecutar en ventana de mantenimiento.
2. `URI` (password de Atlas): rotar la contraseña en el panel de Atlas → actualizar `.env` → reiniciar.
   La contraseña actual debe considerarse **comprometida**: apareció en texto plano en el
   `.env` local y en conversaciones del equipo.
3. `REDIS_URL`: contiene credenciales → misma política.

Nunca dejar el valor viejo en el historial de la terminal compartida ni en un ticket.

## 2. Checklist antes de producción

- [ ] `ENVIRONMENT=production` en `.env` → `/docs`, `/redoc` y `/openapi.json` devuelven 404.
- [ ] `COOKIE_SECURE=true` (HTTPS obligatorio).
- [ ] `ALLOWED_HOSTS` con los dominios reales ( TrustedHostMiddleware ).
- [ ] `CORS_ORIGINS` con los orígenes exactos del front. **Nunca `*`** (el refresh va en cookie → `allow_credentials=True`).
- [ ] `SECRET_KEY` rotado y de 32+ bytes aleatorios.
- [ ] Atlas: usuario de base de datos dedicado con rol `readWrite` **solo** sobre `supportdesk`.
- [ ] Atlas: IP allowlist activada para el usuario de la aplicación.
- [ ] Atlas: backups automáticos activados (los tickets son datos de negocio).
- [ ] TLS: `mongodb+srv` ya fuerza TLS. Prohibido `tlsAllowInvalidCertificates`.
- [ ] Permisos del archivo `.env`: `chmod 600 .env` (Linux) o
      `icacls .env /inheritance:r /grant:r "$env:USERNAME:(R,W)"` (Windows).
- [ ] Redis con contraseña (`REDIS_URL=redis://:pass@host:6379/0`) y vínculo a red privada.
- [ ] HTTPS terminado en el proxy + HSTS activo.
- [ ] `uvicorn` **sin** `--reload` y **con** `--workers N`.
- [ ] `/health` expuesto solo en la red interna.

## 3. Controles implementados

### Autenticación
- Access token 15 min, refresh token 7 días **rotativo** y revocable.
- Refresh en cookie `httpOnly` + `Secure` + `SameSite=Lax`; access token en el body.
- Allowlist de refresh tokens en Redis (`refresh:{jti}`) → el logout invalida de verdad.
- Detección de reuso: si llega un `jti` ya rotado se revoca la familia completa.
- Claims verificados: `sub` (id de usuario), `typ`, `iss`, `aud`, `exp`, `jti`.
- `typ` obligatorio: un refresh token **no** sirve como access token.
- Anti-enumeración: usuario inexistente y contraseña incorrecta devuelven el mismo
  status, el mismo mensaje y el mismo tiempo (hash dummy en el camino del usuario inexistente).

### Autorización
- RBAC: `usuario` (0) < `soporte` (1) < `admin` (2).
- `rol` y `disabled` **nunca** se aceptan desde el cuerpo de la petición: los asigna el servidor.
- Anti-escalación: solo `admin` asigna roles y solo `admin` degrada a otro `admin`.
- El último `admin` no se puede degradar ni deshabilitar (409).
- Aislamiento por propietario en todos los endpoints de tickets (anti-IDOR).

### Entrada y salida
- Límites de longitud en todos los strings (`username`, `email`, `password`, `titulo`, `descripcion`).
- Límite de tamaño del body (100 KB) → 413.
- Regex restrictiva de username (`^[a-zA-Z0-9_.-]+$`), normalización a minúsculas.
- Headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS condicional.
- `TrustedHostMiddleware` contra Host header poisoning.

### Rate limiting y auditoría
- SlowAPI con storage Redis (compartido entre workers).
- Login: límite por IP **y** por username con ventana decreciente.
- Auditoría: `security_event` (login ok/fallido, refresh, logout, cambio de rol, cambio de estado).
  **Nunca** se loguean contraseñas ni tokens completos (solo el `jti`).

## 4. Qué NO hacer

- No loguear `config()` completo ni el `.env`.
- No loguear el body de login ni el token.
- No devolver `password` ni `hashed_password` en ninguna respuesta (los `response_model` lo impiden).
- No usar `allow_origins=["*"]` junto con `allow_credentials=True`.
- No desactivar la verificación de `exp`/`aud`/`iss` "para probar".
- No commitear `.env` ni logs.

## 5. Reporte de incidentes (rotación de credenciales)

1. Rotar `SECRET_KEY` (invalida todos los tokens).
2. Rotar la contraseña del usuario de Atlas y de Redis.
3. Revocar todos los refresh tokens: `redis-cli --scan --pattern 'refresh:*' | xargs redis-cli del`.
4. Revisar los logs `security_event` en busca de accesos anómalos.
5. Documentar el incidente en `CHANGELOG.md`.
