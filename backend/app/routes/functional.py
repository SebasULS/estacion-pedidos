from flask import Blueprint, jsonify, request

from app.services import adjust_inventory, confirm_payment, create_order, order_audit, update_order_status

functional_bp = Blueprint("functional", __name__, url_prefix="/api/funcionalidad")


@functional_bp.post("/pedidos")
def create_order_endpoint():
    return jsonify(create_order(request.get_json(silent=True) or {})), 201


@functional_bp.patch("/pedidos/<int:id_pedido>/estado")
def update_order_status_endpoint(id_pedido: int):
    payload = request.get_json(silent=True) or {}
    return jsonify(update_order_status(id_pedido, payload.get("estado")))


@functional_bp.post("/pedidos/<int:id_pedido>/pago")
def confirm_payment_endpoint(id_pedido: int):
    payload = request.get_json(silent=True) or {}
    return jsonify(confirm_payment(id_pedido, payload.get("metodo_pago"), payload.get("referencia")))


@functional_bp.post("/inventario/ajuste")
def adjust_inventory_endpoint():
    payload = request.get_json(silent=True) or {}
    return jsonify(adjust_inventory(
        int(payload.get("id_producto")),
        payload.get("tipo_movimiento"),
        int(payload.get("cantidad") or 0),
        payload.get("motivo") or "Ajuste manual",
    )), 201


@functional_bp.get("/pedidos/<int:id_pedido>/auditoria")
def order_audit_endpoint(id_pedido: int):
    return jsonify(order_audit(id_pedido))
