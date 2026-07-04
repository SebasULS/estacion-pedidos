from flask import Blueprint, jsonify

from app.integrations.pedidosya import PedidosYaAPI

pedidosya_bp = Blueprint(
    "pedidosya",
    __name__,
    url_prefix="/api/pedidosya"
)


@pedidosya_bp.post("/nuevo")
def nuevo():

    return jsonify(
        PedidosYaAPI.nuevo_pedido()
    )


@pedidosya_bp.get("/pedidos")
def pedidos():

    return jsonify(
        PedidosYaAPI.obtener_pedidos()
    )


@pedidosya_bp.post("/aceptar/<int:idPedido>")
def aceptar(idPedido):

    return jsonify(
        PedidosYaAPI.aceptar(idPedido)
    )


@pedidosya_bp.post("/preparar/<int:idPedido>")
def preparar(idPedido):

    return jsonify(
        PedidosYaAPI.preparar(idPedido)
    )


@pedidosya_bp.post("/listo/<int:idPedido>")
def listo(idPedido):

    return jsonify(
        PedidosYaAPI.listo(idPedido)
    )


@pedidosya_bp.post("/camino/<int:idPedido>")
def camino(idPedido):

    return jsonify(
        PedidosYaAPI.camino(idPedido)
    )


@pedidosya_bp.post("/entregado/<int:idPedido>")
def entregar(idPedido):

    return jsonify(
        PedidosYaAPI.entregar(idPedido)
    )
