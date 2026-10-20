"""Genera y actualiza las partes automáticas de `memory.md`.

    python scripts/context.py            # imprime el contexto a stdout
    python scripts/context.py --update   # reescribe los bloques [AUTO] de memory.md
    python scripts/context.py --check    # sale con 1 si memory.md quedó desactualizado

Los bloques se delimitan con marcadores en `memory.md`:

    <!-- autogenerado:nombre -->
    ...contenido generado...
    <!-- autogenerado:/nombre -->

Todo lo que se genera sale del código real (árbol del repo, docstrings de los
módulos, rutas de la app y resultado de los tests), así que no se puede
desincronizar del proyecto.
"""

import argparse
import ast
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MEMORY = RAIZ / "memory.md"

# Para poder importar la app (routers, main) desde el script.
sys.path.insert(0, str(RAIZ))

ENCABEZADO = "cabecera"
MAPA = "mapa"
API = "api"
VERIFICACION = "verificacion"

# Archivos que no se listan en el mapa (no son código).
EXCLUIDOS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "node_modules",
}

# Descripción de los archivos que no son código.
NO_CODIGO = {
    "README.md": "cara al público: qué es, cómo se usa y endpoints",
    "AGENTS.md": "reglas del proyecto y cómo trabajar acá",
    "memory.md": "contexto vivo del proyecto (este archivo)",
    "CHANGELOG.md": "historial de cambios por versión",
    "requirements.txt": "dependencias de Python",
    "ruff.toml": "configuración del linter",
    ".env.example": "plantilla de variables de entorno (sin secretos)",
    ".gitignore": "archivos excluidos de git",
}


# --------------------------------------------------------------------- utilidades
def _leer_bloque(texto: str, nombre: str) -> str | None:
    patron = re.compile(
        rf"<!-- autogenerado:{re.escape(nombre)} -->\s*(.*?)\s*"
        rf"<!-- autogenerado:/{re.escape(nombre)} -->",
        re.S,
    )
    encontrado = patron.search(texto)
    return encontrado.group(1) if encontrado else None


def _reemplazar_bloque(texto: str, nombre: str, contenido: str) -> str:
    patron = re.compile(
        rf"<!-- autogenerado:{re.escape(nombre)} -->\s*.*?\s*"
        rf"<!-- autogenerado:/{re.escape(nombre)} -->",
        re.S,
    )
    if not patron.search(texto):
        raise SystemExit(f"memory.md no tiene el bloque autogenerado:{nombre}")
    nuevo = f"<!-- autogenerado:{nombre} -->\n{contenido}\n<!-- autogenerado:/{nombre} -->"
    return patron.sub(lambda _match: nuevo, texto, count=1)


def _docstring(archivo: Path) -> str:
    """Primera línea del docstring del módulo."""
    try:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ""
    doc = ast.get_docstring(arbol) or ""
    return doc.strip().splitlines()[0].strip() if doc else ""


# ----------------------------------------------------------------------- bloques
def bloque_encabezado() -> str:
    commit = _git("rev-parse", "--short", "HEAD") or "?"
    rama = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"> **Actualizado:** {ahora} · **Commit:** `{commit}` · **Rama:** `{rama}`"
    )


def bloque_mapa() -> str:
    filas = []
    for archivo in sorted(RAIZ.rglob("*")):
        if not archivo.is_file():
            continue
        if any(parte in EXCLUIDOS for parte in archivo.parts):
            continue
        relativo = archivo.relative_to(RAIZ).as_posix()
        if relativo.startswith("docs/"):
            continue  # la documentación se describe en las secciones 4 y 5
        if archivo.suffix == ".py":
            if archivo.name == "__init__.py" and not _docstring(archivo):
                continue  # los __init__.py vacíos no aportan nada
            descripcion = _docstring(archivo) or "sin docstring"
            filas.append((relativo, descripcion))
        elif relativo in NO_CODIGO:
            filas.append((relativo, NO_CODIGO[relativo]))

    if not filas:
        return "_Sin archivos._"
    lineas = ["| Archivo | Qué hace |", "| :--- | :--- |"]
    for ruta, descripcion in filas:
        lineas.append(f"| `{ruta}` | {descripcion} |")
    return "\n".join(lineas)


def bloque_api() -> str:
    from fastapi.routing import APIRoute

    from routers import tickets, users

    filas = []
    for router in (users.router, tickets.router):
        for ruta in router.routes:
            if not isinstance(ruta, APIRoute):
                continue
            acceso = _acceso_de(ruta)
            resumen = (ruta.summary or ruta.name.replace("_", " ")).strip().capitalize()
            for metodo in sorted(ruta.methods - {"HEAD", "OPTIONS"}):
                filas.append((metodo, ruta.path, acceso, resumen))

    if not filas:
        return "_Sin rutas._"
    filas.sort(key=lambda fila: (fila[1], fila[0]))
    lineas = ["| Método | Ruta | Acceso | Qué hace |", "| :--- | :--- | :--- | :--- |"]
    for metodo, path, acceso, resumen in filas:
        lineas.append(f"| `{metodo}` | `{path}` | {acceso} | {resumen} |")
    lineas.append("")
    lineas.append(
        "Base: `/` y `/health`. En `ENVIRONMENT=production` se agregan `/docs`, "
        "`/redoc` y `/openapi.json`."
    )
    return "\n".join(lineas)


def _acceso_de(ruta) -> str:
    """Deduce el nivel de acceso mirando las dependencias del endpoint."""
    import inspect

    try:
        fuente = inspect.getsource(ruta.endpoint)
    except (OSError, TypeError):
        return "autenticado"
    if "require_admin" in fuente:
        return "**admin**"
    if "require_soporte" in fuente:
        return "soporte/admin"
    if "current_user" in fuente:
        return "autenticado"
    return "público"


def bloque_verificacion() -> str:
    lineas = ["| Comprobación | Resultado |", "| :--- | :--- |"]
    lineas.append(f"| Tests | {_pytest()} |")
    lineas.append(f"| Lint (ruff) | {_ruff()} |")
    lineas.append(f"| Rutas registradas | {_contar_rutas()} |")
    return "\n".join(lineas)


def _pytest() -> str:
    resultado = _correr([sys.executable, "-m", "pytest", "-q"], timeout=300)
    if resultado is None:
        return "pytest no disponible"
    for linea in reversed(resultado.splitlines()):
        if "passed" in linea or "failed" in linea or "error" in linea:
            limpio = re.sub(r",\s*\d+ warnings?", "", linea.strip())
            return re.sub(r"\s+in\s+[\d.]+s\s*$", "", limpio)
    return "sin resultado"


def _ruff() -> str:
    resultado = _correr([sys.executable, "-m", "ruff", "check", "."], timeout=120)
    if resultado is None:
        return "ruff no disponible"
    if "All checks passed" in resultado:
        return "sin hallazgos"
    cuenta = [linea for linea in resultado.splitlines() if "Found " in linea]
    return cuenta[-1].strip() if cuenta else "con errores"


def _contar_rutas() -> str:
    """Cuenta las operaciones de la API (paths x métodos)."""
    try:
        from main import app

        paths = app.openapi().get("paths", {})
        operaciones = sum(
            1
            for metodos in paths.values()
            for metodo in metodos
            if metodo in {"get", "post", "put", "patch", "delete"}
        )
        return f"{operaciones} operaciones en {len(paths)} paths"
    except Exception:  # noqa: BLE001
        return "no disponible"


# ------------------------------------------------------------------------ helpers
def _git(*args: str) -> str:
    resultado = _correr(["git", *args], timeout=30)
    return (resultado or "").strip()


def _correr(comando: list[str], timeout: int = 60) -> str | None:
    try:
        proceso = subprocess.run(
            comando,
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (proceso.stdout or "") + (proceso.stderr or "")


# -------------------------------------------------------------------------- main
def _construir() -> dict[str, str]:
    return {
        ENCABEZADO: bloque_encabezado(),
        MAPA: bloque_mapa(),
        API: bloque_api(),
        VERIFICACION: bloque_verificacion(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Contexto del proyecto")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--update", action="store_true", help="actualiza memory.md")
    grupo.add_argument("--check", action="store_true", help="verifica si está al día")
    args = parser.parse_args()

    if not MEMORY.exists():
        raise SystemExit("No existe memory.md en la raíz del proyecto")

    bloques = _construir()

    if args.check:
        texto = MEMORY.read_text(encoding="utf-8")
        desactualizado = [
            nombre
            for nombre, contenido in bloques.items()
            if _leer_bloque(texto, nombre) != contenido
        ]
        if desactualizado:
            print(f"memory.md está desactualizado: {', '.join(desactualizado)}")
            raise SystemExit(1)
        print("memory.md está al día")
        return

    if args.update:
        texto = MEMORY.read_text(encoding="utf-8")
        for nombre, contenido in bloques.items():
            texto = _reemplazar_bloque(texto, nombre, contenido)
        MEMORY.write_text(texto, encoding="utf-8")
        print("memory.md actualizado")
        return

    print("# Contexto del proyecto\n")
    for nombre, contenido in bloques.items():
        print(f"## {nombre}\n")
        print(contenido)
        print()


if __name__ == "__main__":
    main()
