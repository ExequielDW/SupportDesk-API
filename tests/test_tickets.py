from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_register():
    response = client.post(
        "/usuarios/register",
        json={
            "username": "exequiel",
            "email": "exe@test.com",
            "password": "Python2026",
            "disabled": False,
        },
    )
    assert response.status_code == 201


def test_password_invalida():
    response = client.post(
        "/usuarios/register",
        json={
            "username": "exequiel",
            "email": "exe@test.com",
            "password": "123",
            "disabled": False,
        },
    )
    assert response.status_code == 422


def test_login():
    response = client.post(
        "/usuarios/login",
        data={"username": "exequiel", "password": "Python2026"},
    )
    assert response.status_code == 200


def test_login_incorrecto():
    response = client.post(
        "/usuarios/login",
        data={"username": "exequiel", "password": "password_incorrecta"},
    )
    assert response.status_code == 401


def test_tickets_sin_autenticacion():
    response = client.get("/tickets/me")
    assert response.status_code == 401
