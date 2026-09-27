from database.client import DB_CLIENT


def estats(user_id: str):
    pipelines = [
        {"$match": {"propietario": str(user_id)}},
        {"$group": {"_id": "$estado", "cantidad": {"$sum": 1}}},
    ]
    resultados = DB_CLIENT.tickets.aggregate(pipelines)
    # Mapeo inicial de la respuesta
    estadisticas = {
        "total": 0,
        "abiertos": 0,
        "en_progreso": 0,
        "resueltos": 0,
        "cerrados": 0,
    }
    # Mapeo de estados de MongoDB a las claves de tu diccionario
    mapa_estados = {
        "Abierto": "abiertos",
        "En Proceso": "en_progreso",
        "En Progreso": "en_progreso",
        "Resuelto": "resueltos",
        "Cerrado": "cerrados",
    }

    for item in resultados:
        estado_db = item["_id"]
        cantidad = item["cantidad"]
        estadisticas["total"] += cantidad
        if estado_db in mapa_estados:
            clave = mapa_estados[estado_db]
            estadisticas[clave] += cantidad
    return estadisticas
