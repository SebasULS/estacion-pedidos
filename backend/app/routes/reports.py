from flask import Blueprint, jsonify, request

from app.services import low_stock, orders_by_status, sales_summary, social_fund_summary, top_products

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reportes")


@reports_bp.get("/ventas")
def ventas():
    return jsonify(sales_summary(request.args.get("desde"), request.args.get("hasta")))


@reports_bp.get("/productos-mas-vendidos")
def productos_mas_vendidos():
    limit = int(request.args.get("limit", 10))
    return jsonify(top_products(limit))


@reports_bp.get("/stock-bajo")
def stock_bajo():
    return jsonify(low_stock())


@reports_bp.get("/pedidos-por-estado")
def pedidos_por_estado():
    return jsonify(orders_by_status())


@reports_bp.get("/fondo-social")
def fondo_social():
    return jsonify(social_fund_summary())
