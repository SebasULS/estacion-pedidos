from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from app.nosql_logger import log_event

future_bp = Blueprint("future", __name__, url_prefix="/api/trabajos-futuros")


@future_bp.get("")
def list_future_work():
    return jsonify({
        "trabajos_futuros": [
            {
                "nombre": "Integración con SUNAT",
                "objetivo": "Emitir boletas y facturas electrónicas desde los pedidos pagados mediante API REST personalId + personaToken.",
                "estado": "implementado/simulado",
                "endpoint": "/api/sunat/comprobantes",
            },
            {
                "nombre": "Integración con PedidosYa",
                "objetivo": "Recibir pedidos de delivery y convertirlos en pedidos internos.",
                "estado": "simulado",
                "endpoint": "/api/trabajos-futuros/delivery/pedidosya/simular",
            },
            {
                "nombre": "Integración con Rappi",
                "objetivo": "Automatizar pedidos de delivery externos y controlarlos desde el backend.",
                "estado": "simulado",
                "endpoint": "/api/trabajos-futuros/delivery/rappi/simular",
            },
            {
                "nombre": "Integración contable",
                "objetivo": "Exportar ventas, impuestos y aportes a ollas comunes para contabilidad.",
                "estado": "planificado",
                "endpoint": "/api/trabajos-futuros/contabilidad/exportar/simular",
            },
        ]
    })


def simulation_response(source: str, payload: dict):
    document = {
        "simulado": True,
        "origen": source,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "payload_recibido": payload,
        "mensaje": "Endpoint preparado para conexión futura con API externa.",
    }
    log_event("INFO", "FUTURE_WORK_SIMULATION", source, "Simulación de integración futura", document)
    return jsonify(document)


@future_bp.post("/sunat/facturacion/simular")
def simulate_sunat():
    return simulation_response("SUNAT", request.get_json(silent=True) or {})


@future_bp.post("/delivery/pedidosya/simular")
def simulate_pedidosya():
    return simulation_response("PedidosYa", request.get_json(silent=True) or {})


@future_bp.post("/delivery/rappi/simular")
def simulate_rappi():
    return simulation_response("Rappi", request.get_json(silent=True) or {})


@future_bp.post("/contabilidad/exportar/simular")
def simulate_accounting():
    return simulation_response("Sistema Contable", request.get_json(silent=True) or {})
