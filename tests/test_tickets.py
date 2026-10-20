"""Contrato HTTP de usuarios y tickets (con fake de Mongo en memoria)."""

TICKET = {
    "titulo": "Impresora sin conexión",
    "descripcion": "La impresora de la oficina no responde al ping",
    "categoria": "Tecnico",
    "prioridad": "Media",
}


def test_register(client, helpers):
    response = helpers.registrar(client, "exequiel")
    assert response.status_code == 201
    cuerpo = response.json()
    assert cuerpo["username"] == "exequiel"
    assert cuerpo["rol"] == "usuario"
    assert "password" not in cuerpo
    assert "password_hash" not in cuerpo


def test_password_invalida(client, helpers):
    response = client.post(
        "/usuarios/register",
        json={"username": "exequiel", "email": "exe@test.com", "password": "123"},
    )
    assert response.status_code == 422


def test_login(client, helpers):
    helpers.registrar(client, "exequiel")
    response = helpers.login(client, "exequiel")
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_incorrecto(client, helpers):
    helpers.registrar(client, "exequiel")
    response = helpers.login(client, "exequiel", "password_incorrecta")
    assert response.status_code == 401


def test_tickets_sin_autenticacion(client):
    response = client.get("/tickets/me")
    assert response.status_code == 401


def test_crear_y_listar_ticket(client, helpers, usuario_autenticado):
    headers = {"Authorization": f"Bearer {usuario_autenticado}"}
    creado = client.post("/tickets/created", json=TICKET, headers=headers)
    assert creado.status_code == 201
    assert creado.json()["estado"] == "Abierto"

    listado = client.get("/tickets/me", headers=headers)
    assert listado.status_code == 200
    assert len(listado.json()) == 1

    ticket_id = creado.json()["id"]
    detalle = client.get(f"/tickets/me/{ticket_id}", headers=headers)
    assert detalle.status_code == 200
    assert detalle.json()["titulo"] == TICKET["titulo"]


def test_actualizar_ticket_conserva_estado(client, helpers, usuario_autenticado):
    """Regresión: el update solía borrar el campo `estado` (500)."""
    headers = {"Authorization": f"Bearer {usuario_autenticado}"}
    creado = client.post("/tickets/created", json=TICKET, headers=headers)
    ticket_id = creado.json()["id"]

    actualizado = client.put(
        f"/tickets/update/{ticket_id}",
        json={**TICKET, "titulo": "Impresora sin conexión (editado)"},
        headers=headers,
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["estado"] == "Abierto"
    assert actualizado.json()["titulo"] == "Impresora sin conexión (editado)"


def test_titulo_duplicado_del_mismo_usuario(client, helpers, usuario_autenticado):
    headers = {"Authorization": f"Bearer {usuario_autenticado}"}
    assert client.post("/tickets/created", json=TICKET, headers=headers).status_code == 201
    repetido = client.post("/tickets/created", json=TICKET, headers=headers)
    assert repetido.status_code == 409


def test_titulo_igual_otro_usuario_permitido(client, helpers):
    """El título es único por propietario, no global."""
    helpers.registrar(client, "uno")
    helpers.registrar(client, "dos")
    token_uno = helpers.token(client, "uno")
    token_dos = helpers.token(client, "dos")

    headers_uno = {"Authorization": f"Bearer {token_uno}"}
    headers_dos = {"Authorization": f"Bearer {token_dos}"}

    assert client.post("/tickets/created", json=TICKET, headers=headers_uno).status_code == 201
    assert client.post("/tickets/created", json=TICKET, headers=headers_dos).status_code == 201


def test_estadisticas(client, helpers, usuario_autenticado):
    headers = {"Authorization": f"Bearer {usuario_autenticado}"}
    client.post("/tickets/created", json=TICKET, headers=headers)
    stats = client.get("/tickets/stats", headers=headers)
    assert stats.status_code == 200
    cuerpo = stats.json()
    assert cuerpo["total"] == 1
    assert cuerpo["abiertos"] == 1


def test_paginacion(client, helpers, usuario_autenticado):
    headers = {"Authorization": f"Bearer {usuario_autenticado}"}
    for indice in range(3):
        client.post(
            "/tickets/created",
            json={**TICKET, "titulo": f"Problema número {indice}"},
            headers=headers,
        )
    respuesta = client.get("/tickets/me?limite=2", headers=headers)
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 2
