"""Pruebas de seguridad: autorización, aislamiento, abuse y validación."""

import routers.users as usuarios_router

TICKET = {
    "titulo": "Error de facturación",
    "descripcion": "El recibo arrives con el monto incorrecto",
    "categoria": "Facturacion",
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------- aislamiento (IDOR)
def test_no_puede_ver_ticket_de_otro_usuario(client, helpers):
    helpers.registrar(client, "alice")
    helpers.registrar(client, "mallory")
    token_alice = helpers.token(client, "alice")
    token_mallory = helpers.token(client, "mallory")

    creado = client.post("/tickets/created", json=TICKET, headers=_headers(token_alice))
    ticket_id = creado.json()["id"]

    lectura = client.get(f"/tickets/me/{ticket_id}", headers=_headers(token_mallory))
    assert lectura.status_code == 404

    actualizacion = client.put(
        f"/tickets/update/{ticket_id}", json=TICKET, headers=_headers(token_mallory)
    )
    assert actualizacion.status_code == 404


def test_no_puede_ver_el_listado_de_otro_usuario(client, helpers, usuario_autenticado):
    helpers.registrar(client, "otro")
    token_otro = helpers.token(client, "otro")
    client.post("/tickets/created", json=TICKET, headers=_headers(usuario_autenticado))

    listado = client.get("/tickets/me", headers=_headers(token_otro))
    assert listado.status_code == 200
    assert listado.json() == []


# ------------------------------------------------------------------------- RBAC
def test_usuario_normal_no_lista_tickets_globales(client, helpers, usuario_autenticado):
    respuesta = client.get("/tickets", headers=_headers(usuario_autenticado))
    assert respuesta.status_code == 403


def test_usuario_normal_no_cambia_roles(client, helpers, usuario_autenticado, entorno):
    objetivo = entorno.users.documentos[0]
    respuesta = client.patch(
        f"/usuarios/{objetivo['_id']}/rol",
        json={"rol": "admin"},
        headers=_headers(usuario_autenticado),
    )
    assert respuesta.status_code == 403


def test_soporte_lista_tickets_globales(client, helpers, entorno):
    helpers.registrar(client, "soporte1")
    entorno.users.documentos[0]["rol"] = "soporte"
    token = helpers.token(client, "soporte1")

    helpers.registrar(client, "cliente")
    token_cliente = helpers.token(client, "cliente")
    client.post("/tickets/created", json=TICKET, headers=_headers(token_cliente))

    listado = client.get("/tickets", headers=_headers(token))
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_admin_promueve_a_soporte(client, helpers, admin, entorno):
    helpers.registrar(client, "nuevo")
    objetivo = entorno.users.documentos[-1]

    respuesta = client.patch(
        f"/usuarios/{objetivo['_id']}/rol",
        json={"rol": "soporte"},
        headers=_headers(admin),
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "soporte"


def test_no_se_puede_degradar_al_ultimo_admin(client, helpers, admin, entorno):
    objetivo = entorno.users.documentos[0]
    respuesta = client.patch(
        f"/usuarios/{objetivo['_id']}/rol",
        json={"rol": "usuario"},
        headers=_headers(admin),
    )
    assert respuesta.status_code == 409


def test_no_se_puede_deshabilitar_al_ultimo_admin(client, helpers, admin, entorno):
    objetivo = entorno.users.documentos[0]
    respuesta = client.patch(
        f"/usuarios/{objetivo['_id']}/estado",
        json={"disabled": True},
        headers=_headers(admin),
    )
    assert respuesta.status_code == 409


def test_usuario_deshabilitado_no_puede_entrar(client, helpers, admin, entorno):
    helpers.registrar(client, "suspendido")
    objetivo = entorno.users.documentos[-1]
    client.patch(
        f"/usuarios/{objetivo['_id']}/estado",
        json={"disabled": True},
        headers=_headers(admin),
    )

    login = helpers.login(client, "suspendido")
    assert login.status_code == 401


# ------------------------------------------------------------- control de entrada
def test_el_cliente_no_puede_asignarse_rol_ni_disabled(client):
    respuesta = client.post(
        "/usuarios/register",
        json={
            "username": "listo",
            "email": "listo@test.com",
            "password": "Python2026",
            "rol": "admin",
            "disabled": False,
        },
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["rol"] == "usuario"
    assert cuerpo["disabled"] is False


def test_cuerpo_demasiado_grande(client, helpers, usuario_autenticado):
    grande = "x" * (200 * 1024)
    respuesta = client.post(
        "/tickets/created",
        json={**TICKET, "descripcion": grande},
        headers=_headers(usuario_autenticado),
    )
    assert respuesta.status_code == 413


def test_descripcion_demasiado_larga(client, helpers, usuario_autenticado):
    respuesta = client.post(
        "/tickets/created",
        json={**TICKET, "descripcion": "y" * 5000},
        headers=_headers(usuario_autenticado),
    )
    assert respuesta.status_code == 422


def test_transicion_invalida_de_estado(client, helpers, usuario_autenticado):
    creado = client.post(
        "/tickets/created", json=TICKET, headers=_headers(usuario_autenticado)
    )
    ticket_id = creado.json()["id"]

    # De "Abierto" no se puede saltar a "Resuelto".
    respuesta = client.patch(
        f"/tickets/{ticket_id}/estado",
        json={"estado": "Resuelto"},
        headers=_headers(usuario_autenticado),
    )
    assert respuesta.status_code == 422

    valida = client.patch(
        f"/tickets/{ticket_id}/estado",
        json={"estado": "En Proceso"},
        headers=_headers(usuario_autenticado),
    )
    assert valida.status_code == 200
    assert valida.json()["estado"] == "En Proceso"


def test_reabrir_ticket_cerrado_solo_admin(client, helpers, admin, entorno, usuario_autenticado):
    helpers.registrar(client, "due")
    token_due = helpers.token(client, "due")
    creado = client.post("/tickets/created", json=TICKET, headers=_headers(token_due))
    ticket_id = creado.json()["id"]

    client.patch(
        f"/tickets/{ticket_id}/estado",
        json={"estado": "Cerrado"},
        headers=_headers(token_due),
    )

    # El dueño no puede reabrirlo.
    dueño = client.patch(
        f"/tickets/{ticket_id}/estado",
        json={"estado": "Abierto"},
        headers=_headers(token_due),
    )
    assert dueño.status_code == 422

    # El admin sí.
    admin_respuesta = client.patch(
        f"/tickets/{ticket_id}/estado",
        json={"estado": "Abierto"},
        headers=_headers(admin),
    )
    assert admin_respuesta.status_code == 200


# ------------------------------------------------------------------ abuse /DoS
def test_rate_limit_por_usuario(client, helpers, monkeypatch):
    """El límite por usuario corta el bruteforce aunque la IP varíe."""
    monkeypatch.setattr(usuarios_router, "LOGIN_MAX_POR_USUARIO", 2)
    helpers.registrar(client, "victima")

    assert helpers.login(client, "victima", "mal").status_code == 401
    assert helpers.login(client, "victima", "mal").status_code == 401
    limited = helpers.login(client, "victima", "mal")
    assert limited.status_code == 429


def test_el_rate_limit_por_usuario_no_afecta_logins_correctos(client, helpers, monkeypatch):
    """Solo cuentan los intentos fallidos: un login correcto nunca bloquea."""
    monkeypatch.setattr(usuarios_router, "LOGIN_MAX_POR_USUARIO", 2)
    helpers.registrar(client, "correcto")

    assert helpers.login(client, "correcto").status_code == 200
    assert helpers.login(client, "correcto").status_code == 200
    assert helpers.login(client, "correcto").status_code == 200


def test_el_rate_limit_se_Reinicia_con_un_login_correcto(client, helpers, monkeypatch):
    monkeypatch.setattr(usuarios_router, "LOGIN_MAX_POR_USUARIO", 2)
    helpers.registrar(client, "alterno")

    assert helpers.login(client, "alterno", "mal").status_code == 401
    assert helpers.login(client, "alterno", "mal").status_code == 401
    # El tercer intento fallido ya supera el límite...
    assert helpers.login(client, "alterno", "mal").status_code == 429
    # ...pero un login correcto limpia el contador.
    assert helpers.login(client, "alterno").status_code == 200
    assert helpers.login(client, "alterno", "mal").status_code == 401


def test_el_hash_de_la_password_no_se_expone(client, helpers):
    helpers.registrar(client, "sara")
    respuesta = helpers.login(client, "sara")
    cuerpo = respuesta.text.lower()
    assert "password" not in cuerpo
    assert "hash" not in cuerpo
