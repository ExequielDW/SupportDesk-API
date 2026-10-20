"""Autenticación: login, refresh rotativo, revocación y anti-enumeración."""

from config import COOKIE_NAME


def test_login_deja_refresh_en_cookie_http_only(client, helpers):
    helpers.registrar(client, "ana")
    respuesta = helpers.login(client, "ana")
    assert respuesta.status_code == 200

    cabecera = respuesta.headers["set-cookie"]
    assert COOKIE_NAME in cabecera
    assert "HttpOnly" in cabecera
    assert "access_token" not in cabecera  # el access token va en el body


def test_login_con_email(client, helpers):
    helpers.registrar(client, "bob", email="bob@empresa.com")
    respuesta = client.post(
        "/usuarios/login", data={"username": "bob@empresa.com", "password": "Python2026"}
    )
    assert respuesta.status_code == 200


def test_no_enumeracion_de_cuentas(client, helpers):
    """Usuario inexistente y password incorrecta: mismo status y mismo mensaje."""
    helpers.registrar(client, "carla")
    inexistente = client.post(
        "/usuarios/login", data={"username": "fantasma", "password": "Python2026"}
    )
    incorrecta = client.post(
        "/usuarios/login", data={"username": "carla", "password": "otraCosa123"}
    )
    assert inexistente.status_code == incorrecta.status_code == 401
    assert inexistente.json()["detail"] == incorrecta.json()["detail"]


def test_refresh_rota_el_token(client, helpers):
    helpers.registrar(client, "dante")
    login = helpers.login(client, "dante")
    token_original = login.cookies[COOKIE_NAME]

    respuesta = client.post("/usuarios/refresh")
    assert respuesta.status_code == 200
    assert respuesta.json()["access_token"]
    assert respuesta.cookies[COOKIE_NAME] != token_original


def test_reuso_de_refresh_revoca_la_familia(client, helpers):
    helpers.registrar(client, "eva")
    login = helpers.login(client, "eva")
    token_original = login.cookies[COOKIE_NAME]

    # Primer refresh: rota el token.
    primera = client.post("/usuarios/refresh")
    assert primera.status_code == 200
    token_nuevo = primera.cookies[COOKIE_NAME]

    # Se reusa el token viejo: se detecta y se revoca la familia.
    client.cookies.delete(COOKIE_NAME)
    reutilizado = client.post("/usuarios/refresh", cookies={COOKIE_NAME: token_original})
    assert reutilizado.status_code == 401

    # El token nuevo también queda invalidado.
    client.cookies.delete(COOKIE_NAME)
    posterior = client.post("/usuarios/refresh", cookies={COOKIE_NAME: token_nuevo})
    assert posterior.status_code == 401


def test_refresh_sin_cookie(client):
    respuesta = client.post("/usuarios/refresh")
    assert respuesta.status_code == 401


def test_logout_revoca_el_acceso(client, helpers):
    helpers.registrar(client, "fede")
    login = helpers.login(client, "fede")
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/usuarios/me", headers=headers).status_code == 200

    logout = client.post("/usuarios/logout", headers=headers)
    assert logout.status_code == 200

    # El access token queda revocado.
    assert client.get("/usuarios/me", headers=headers).status_code == 401


def test_refresh_no_sirve_como_access(client, helpers):
    helpers.registrar(client, "gina")
    login = helpers.login(client, "gina")
    refresh = login.cookies[COOKIE_NAME]

    respuesta = client.get(
        "/usuarios/me", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert respuesta.status_code == 401


def test_access_no_sirve_para_refresh(client, helpers):
    helpers.registrar(client, "hugo")
    token = helpers.token(client, "hugo")

    respuesta = client.post("/usuarios/refresh", cookies={COOKIE_NAME: token})
    assert respuesta.status_code == 401
