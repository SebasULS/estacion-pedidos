from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, jsonify, request

from app.auth import _exec_on_conn, _fetchone_on_conn
from app.db import fetch_all, fetch_one, transaction
from app.errors import ApiError
from app.integrations.sunat import SunatAPI, build_sunat_payload, normalize_tipo_comprobante
from app.nosql_logger import log_event

sunat_bp = Blueprint("sunat", __name__, url_prefix="/api/sunat")


def _response_to_record_fields(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "estado_sunat": response.get("estado_sunat") or "ENVIADO",
        "codigo_sunat": response.get("codigo_sunat"),
        "mensaje_sunat": response.get("mensaje_sunat"),
        "external_id": response.get("external_id"),
        "pdf_url": response.get("pdf_url"),
        "xml_url": response.get("xml_url"),
        "cdr_url": response.get("cdr_url"),
        "respuesta_json": json.dumps(response.get("respuesta_original", response), ensure_ascii=False),
    }


def _insert_comprobante(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    cliente = payload["cliente"]
    totales = payload["totales"]
    fields = _response_to_record_fields(response)
    try:
        with transaction() as conn:
            cur = _exec_on_conn(
                conn,
                """
                INSERT INTO comprobantes_electronicos
                (id_pedido, tipo_comprobante, codigo_tipo_comprobante, serie, numero,
                 cliente_tipo_documento, cliente_numero_documento, cliente_nombre, cliente_direccion,
                 subtotal, igv, total, estado_sunat, codigo_sunat, mensaje_sunat, external_id,
                 pdf_url, xml_url, cdr_url, payload_json, respuesta_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_comprobante
                """,
                (
                    payload.get("id_pedido"),
                    payload.get("tipo_comprobante_nombre"),
                    payload.get("tipo_comprobante"),
                    payload.get("serie"),
                    payload.get("numero"),
                    cliente.get("tipo_documento"),
                    cliente.get("numero_documento"),
                    cliente.get("nombre"),
                    cliente.get("direccion"),
                    totales.get("subtotal"),
                    totales.get("igv"),
                    totales.get("total"),
                    fields["estado_sunat"],
                    fields["codigo_sunat"],
                    fields["mensaje_sunat"],
                    fields["external_id"],
                    fields["pdf_url"],
                    fields["xml_url"],
                    fields["cdr_url"],
                    json.dumps(payload, ensure_ascii=False),
                    fields["respuesta_json"],
                ),
            )
            row = cur.fetchone()
            id_comprobante = int(row[0]) if row else int(getattr(cur, "lastrowid", 0) or 0)
            record = _fetchone_on_conn(conn, "SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    except Exception as exc:
        raise ApiError(400, f"No se pudo registrar el comprobante electrónico: {exc}") from exc

    log_event(
        "INFO",
        "SUNAT_COMPROBANTE_REGISTRADO",
        "comprobantes_electronicos",
        "Comprobante electrónico registrado",
        {"id_comprobante": record["id_comprobante"], "serie": record["serie"], "numero": record["numero"], "estado": record["estado_sunat"]},
    )
    return record


def _load_order_for_sunat(id_pedido: int) -> dict[str, Any]:
    pedido = fetch_one("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
    if not pedido:
        raise ApiError(404, "Pedido no encontrado")
    detalles = fetch_all(
        """
        SELECT d.id_producto, p.nombre AS descripcion, d.cantidad, d.precio_unitario, d.subtotal
        FROM pedido_detalles d
        JOIN productos p ON p.id_producto = d.id_producto
        WHERE d.id_pedido = %s
        ORDER BY d.id_detalle ASC
        """,
        (id_pedido,),
    )
    if not detalles:
        raise ApiError(400, "El pedido no tiene detalles para facturación")
    transaccion = fetch_one("SELECT * FROM transacciones WHERE id_pedido = %s", (id_pedido,))
    return {"pedido": pedido, "detalles": detalles, "transaccion": transaccion}


def _build_payload_from_request(data: dict[str, Any]) -> dict[str, Any]:
    tipo = data.get("tipo_comprobante") or data.get("tipo") or "boleta"
    if data.get("id_pedido"):
        source = _load_order_for_sunat(int(data["id_pedido"]))
        pedido = source["pedido"]
        cliente = data.get("cliente") or {
            "tipo_documento": "1",
            "numero_documento": "00000000",
            "nombre": "Cliente varios",
            "direccion": "-",
        }
        if data.get("exigir_pago") and pedido.get("estado") != "pagado":
            raise ApiError(409, "El pedido debe estar pagado para emitir comprobante SUNAT")
        return build_sunat_payload(
            tipo_comprobante=tipo,
            cliente=cliente,
            items=source["detalles"],
            subtotal=pedido.get("subtotal"),
            igv=pedido.get("impuesto"),
            total=pedido.get("total"),
            id_pedido=pedido.get("id_pedido"),
            observacion=data.get("observacion"),
        )

    return build_sunat_payload(
        tipo_comprobante=tipo,
        cliente=data.get("cliente") or {},
        items=data.get("items") or [],
        subtotal=data.get("subtotal"),
        igv=data.get("igv"),
        total=data.get("total"),
        observacion=data.get("observacion"),
    )


@sunat_bp.get("/config")
def config():
    return jsonify(SunatAPI.configuracion())


@sunat_bp.get("/ruc/<ruc>")
def consultar_ruc(ruc):
    return jsonify(SunatAPI.consultar_ruc(ruc))


@sunat_bp.get("/dni/<dni>")
def consultar_dni(dni):
    return jsonify(SunatAPI.consultar_dni(dni))


@sunat_bp.get("/comprobantes")
def listar_comprobantes():
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = max(int(request.args.get("offset", 0)), 0)
    rows = fetch_all(
        "SELECT * FROM comprobantes_electronicos ORDER BY id_comprobante DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
    total = fetch_one("SELECT COUNT(*) AS total FROM comprobantes_electronicos")["total"]
    return jsonify({"tabla": "comprobantes_electronicos", "total": total, "limit": limit, "offset": offset, "data": rows})


@sunat_bp.get("/comprobantes/<int:id_comprobante>")
def obtener_comprobante(id_comprobante: int):
    row = fetch_one("SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    if not row:
        raise ApiError(404, "Comprobante electrónico no encontrado")
    return jsonify(row)


@sunat_bp.post("/comprobantes")
def emitir_comprobante():
    data = request.get_json(silent=True) or {}
    payload = _build_payload_from_request(data)
    response = SunatAPI.emitir(payload)
    record = _insert_comprobante(payload, response)
    return jsonify({"success": response.get("success", True), "payload_enviado": payload, "respuesta_sunat": response, "comprobante": record}), 201


@sunat_bp.post("/pedidos/<int:id_pedido>/boleta")
def emitir_boleta_desde_pedido(id_pedido: int):
    data = request.get_json(silent=True) or {}
    data["id_pedido"] = id_pedido
    data["tipo_comprobante"] = "boleta"
    payload = _build_payload_from_request(data)
    response = SunatAPI.emitir(payload)
    record = _insert_comprobante(payload, response)
    return jsonify({"success": response.get("success", True), "payload_enviado": payload, "respuesta_sunat": response, "comprobante": record}), 201


@sunat_bp.post("/pedidos/<int:id_pedido>/factura")
def emitir_factura_desde_pedido(id_pedido: int):
    data = request.get_json(silent=True) or {}
    data["id_pedido"] = id_pedido
    data["tipo_comprobante"] = "factura"
    payload = _build_payload_from_request(data)
    response = SunatAPI.emitir(payload)
    record = _insert_comprobante(payload, response)
    return jsonify({"success": response.get("success", True), "payload_enviado": payload, "respuesta_sunat": response, "comprobante": record}), 201


@sunat_bp.post("/boleta")
def emitir_boleta():
    data = request.get_json(silent=True) or {}
    data["tipo_comprobante"] = "boleta"
    payload = _build_payload_from_request(data)
    response = SunatAPI.emitir(payload)
    record = _insert_comprobante(payload, response)
    return jsonify({"success": response.get("success", True), "payload_enviado": payload, "respuesta_sunat": response, "comprobante": record}), 201


@sunat_bp.post("/factura")
def emitir_factura():
    data = request.get_json(silent=True) or {}
    data["tipo_comprobante"] = "factura"
    payload = _build_payload_from_request(data)
    response = SunatAPI.emitir(payload)
    record = _insert_comprobante(payload, response)
    return jsonify({"success": response.get("success", True), "payload_enviado": payload, "respuesta_sunat": response, "comprobante": record}), 201


@sunat_bp.post("/comprobantes/<int:id_comprobante>/consultar")
def consultar_comprobante(id_comprobante: int):
    record = fetch_one("SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    if not record:
        raise ApiError(404, "Comprobante electrónico no encontrado")
    payload = {
        "id_comprobante": id_comprobante,
        "tipo_comprobante": record["codigo_tipo_comprobante"],
        "serie": record["serie"],
        "numero": record["numero"],
        "external_id": record.get("external_id"),
    }
    response = SunatAPI.consultar_comprobante(payload)
    fields = _response_to_record_fields(response)
    with transaction() as conn:
        _exec_on_conn(
            conn,
            """
            UPDATE comprobantes_electronicos
            SET estado_sunat = %s, codigo_sunat = %s, mensaje_sunat = %s, external_id = COALESCE(%s, external_id),
                pdf_url = COALESCE(%s, pdf_url), xml_url = COALESCE(%s, xml_url), cdr_url = COALESCE(%s, cdr_url),
                respuesta_json = %s, actualizado_en = NOW()
            WHERE id_comprobante = %s
            """,
            (fields["estado_sunat"], fields["codigo_sunat"], fields["mensaje_sunat"], fields["external_id"], fields["pdf_url"], fields["xml_url"], fields["cdr_url"], fields["respuesta_json"], id_comprobante),
        )
        updated = _fetchone_on_conn(conn, "SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    log_event("INFO", "SUNAT_COMPROBANTE_CONSULTADO", "comprobantes_electronicos", "Consulta de estado SUNAT", {"id_comprobante": id_comprobante})
    return jsonify({"success": response.get("success", True), "respuesta_sunat": response, "comprobante": updated})


@sunat_bp.post("/comprobantes/<int:id_comprobante>/anular")
def anular_comprobante(id_comprobante: int):
    data = request.get_json(silent=True) or {}
    record = fetch_one("SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    if not record:
        raise ApiError(404, "Comprobante electrónico no encontrado")
    payload = {
        "id_comprobante": id_comprobante,
        "tipo_comprobante": record["codigo_tipo_comprobante"],
        "serie": record["serie"],
        "numero": record["numero"],
        "external_id": record.get("external_id"),
        "motivo": data.get("motivo") or "Anulación solicitada desde Estación de Pedidos",
    }
    response = SunatAPI.anular_comprobante(payload)
    fields = _response_to_record_fields(response)
    with transaction() as conn:
        _exec_on_conn(
            conn,
            """
            UPDATE comprobantes_electronicos
            SET estado_sunat = %s, codigo_sunat = %s, mensaje_sunat = %s, respuesta_json = %s, actualizado_en = NOW()
            WHERE id_comprobante = %s
            """,
            (fields["estado_sunat"], fields["codigo_sunat"], fields["mensaje_sunat"], fields["respuesta_json"], id_comprobante),
        )
        updated = _fetchone_on_conn(conn, "SELECT * FROM comprobantes_electronicos WHERE id_comprobante = %s", (id_comprobante,))
    log_event("INFO", "SUNAT_COMPROBANTE_ANULADO", "comprobantes_electronicos", "Anulación SUNAT registrada", {"id_comprobante": id_comprobante})
    return jsonify({"success": response.get("success", True), "respuesta_sunat": response, "comprobante": updated})
