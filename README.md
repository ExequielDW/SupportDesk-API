# 🎫 SupportDesk API

API RESTful de alto rendimiento para la gestión centralizada de tickets de soporte técnico, construida con **FastAPI**, **MongoDB** y **SlowAPI**. Implementa arquitectura modular, autenticación robusta mediante JSON Web Tokens (JWT) y limitación de tasa de peticiones para garantizar seguridad en producción.

---

## ⚡ Características Principales

* **Autenticación Segura (OAuth2 + JWT):** Flujo completo de registro e inicio de sesión con encriptación bcrypt para contraseñas.
* **Gestión de Tickets (CRUD):** Creación, lectura individual, listado filtrable y actualización de tickets aislados por usuario.
* **Control de Tasa (Rate Limiting):** Integración de SlowAPI para mitigar ataques de fuerza bruta y DoS (3-5 req/min en rutas sensibles).
* **Base de Datos NoSQL Optimizada:** Consultas eficientes en MongoDB con soporte para pipelines de agregación.
* **Validación de Datos Estricta:** Validación de tipos, correos y enums mediante Pydantic v2 y BSON ObjectIDs.

---

## 🛠️ Tecnologías Utilizadas

| Componente | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.10+ |
| **Framework Web** | FastAPI |
| **Base de Datos** | MongoDB (PyMongo) |
| **Rate Limiter** | SlowAPI |
| **Seguridad / Criptografía** | Passlib (Bcrypt), Python-Jose (JWT) |
| **Configuración** | Python-Decouple |

---

## 📁 Estructura del Proyecto

```text
SupportDesk API/
├── database/
│   └── client.py          # Conexión principal a MongoDB Client
├── models/
│   ├── ticket.py          # Modelos Pydantic y Enums para Tickets
│   └── user.py            # Modelos Pydantic para Usuarios (User / UserPW)
├── routers/
│   ├── auth.py            # Instancia central de Limiter y middleware JWT
│   ├── tickets.py         # Endpoints de gestión de tickets
│   └── users.py           # Endpoints de autenticación y perfiles
├── services/
│   ├── schemas.py         # Formateadores de BSON a diccionarios Python
│   ├── security.py        # Funciones aux. de hashing de contraseñas
│   └── validators.py      # Búsquedas en DB y validaciones de negocio
├── utils/
│   └── utilidad.py        # Pipelines de agregación para métricas
├── main.py                # Punto de entrada y montaje de la app FastAPI
├── .env                   # Variables de entorno secretas
└── requirements.txt       # Dependencias del proyecto