from typing import Any

from app.auth import _exec_on_conn, _fetchall_on_conn, _fetchone_on_conn
from app.db import fetch_all, fetch_one, transaction
from app.errors import ApiError
from app.nosql_logger import log_event

VALID_ORDER_STATES = {"registrado", "en_preparacion", "entregado", "pagado", "cancelado"}
VALID_PAYMENT_METHODS = {"efectivo", "yape", "plin", "tarjeta", "transferencia"}


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []
    if not items:
        raise ApiError(400, "El pedido debe tener al menos un producto")

    id_usuario = payload.get("id_usuario")
    if not id_usuario:
        raise ApiError(400, "id_usuario es obligatorio")

    metodo_pago = payload.get("metodo_pago")
    if metodo_pago and metodo_pago not in VALID_PAYMENT_METHODS:
        raise ApiError(400, "Método de pago no válido")

    descuento = float(payload.get("descuento") or 0)
    porcentaje_fondo = float(payload.get("porcentaje_fondo") or 0)
    comentario = payload.get("comentario")
    id_mesa = payload.get("id_mesa")

    try:
        with transaction() as conn:
            user = _fetchone_on_conn(conn, "SELECT * FROM usuarios WHERE id_usuario = %s AND activo = 1", (id_usuario,))
            if user is None:
                raise ApiError(404, "Usuario no encontrado o inactivo")
            if id_mesa:
                mesa = _fetchone_on_conn(conn, "SELECT * FROM mesas WHERE id_mesa = %s", (id_mesa,))
                if mesa is None:
                    raise ApiError(404, "Mesa no encontrada")

            prepared_items: list[dict[str, Any]] = []
            subtotal = 0.0
            for raw_item in items:
                id_producto = raw_item.get("id_producto")
                cantidad = int(raw_item.get("cantidad") or 0)
                if not id_producto or cantidad <= 0:
                    raise ApiError(400, "Cada item requiere id_producto y cantidad mayor a cero")

                product = _fetchone_on_conn(conn, """
                    SELECT p.*, i.stock_actual
                    FROM productos p
                    JOIN inventario i ON i.id_producto = p.id_producto
                    WHERE p.id_producto = %s AND p.activo = 1
                """, (id_producto,))
                if product is None:
                    raise ApiError(404, f"Producto {id_producto} no encontrado, inactivo o sin inventario")
                if product["stock_actual"] < cantidad:
                    raise ApiError(409, f"Stock insuficiente para {product['nombre']}. Disponible: {product['stock_actual']}")

                item_subtotal = round(float(product["precio"]) * cantidad, 2)
                subtotal += item_subtotal
                prepared_items.append({
                    "id_producto": id_producto,
                    "nombre": product["nombre"],
                    "cantidad": cantidad,
                    "precio_unitario": float(product["precio"]),
                    "comentario": raw_item.get("comentario"),
                    "subtotal": item_subtotal,
                    "stock_anterior": int(product["stock_actual"]),
                })

            subtotal = round(subtotal, 2)
            impuesto = round(float(payload.get("impuesto") or 0), 2)
            total = round(max(subtotal + impuesto - descuento, 0), 2)

            cur = _exec_on_conn(conn, """
                INSERT INTO pedidos (id_mesa, id_usuario, estado, comentario, subtotal, impuesto, descuento, total)
                VALUES (%s, %s, 'registrado', %s, %s, %s, %s, %s)
                RETURNING id_pedido
            """, (id_mesa, id_usuario, comentario, subtotal, impuesto, descuento, total))
            row = cur.fetchone()
            id_pedido = int(row[0]) if row else int(getattr(cur, "lastrowid", 0) or 0)

            for item in prepared_items:
                _exec_on_conn(conn, """
                    INSERT INTO pedido_detalles (id_pedido, id_producto, cantidad, precio_unitario, comentario, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_pedido, item["id_producto"], item["cantidad"], item["precio_unitario"], item["comentario"], item["subtotal"]))

                stock_nuevo = item["stock_anterior"] - item["cantidad"]
                _exec_on_conn(
                    conn,
                    "UPDATE inventario SET stock_actual = %s, actualizado_en = NOW() WHERE id_producto = %s",
                    (stock_nuevo, item["id_producto"]),
                )
                _exec_on_conn(conn, """
                    INSERT INTO inventario_movimientos
                    (id_producto, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, motivo, id_pedido)
                    VALUES (%s, 'salida', %s, %s, %s, %s, %s)
                """, (item["id_producto"], item["cantidad"], item["stock_anterior"], stock_nuevo, "Consumo por pedido", id_pedido))

            if id_mesa:
                _exec_on_conn(conn, "UPDATE mesas SET estado = 'ocupada' WHERE id_mesa = %s", (id_mesa,))

            transaction_doc = None
            if metodo_pago:
                cur_tx = _exec_on_conn(conn, """
                    INSERT INTO transacciones (id_pedido, metodo_pago, monto, estado, referencia)
                    VALUES (%s, %s, %s, 'pagado', %s)
                    RETURNING id_transaccion
                """, (id_pedido, metodo_pago, total, payload.get("referencia")))
                row_tx = cur_tx.fetchone()
                id_transaccion = int(row_tx[0]) if row_tx else int(getattr(cur_tx, "lastrowid", 0) or 0)
                _exec_on_conn(conn, "UPDATE pedidos SET estado = 'pagado', actualizado_en = NOW() WHERE id_pedido = %s", (id_pedido,))
                if id_mesa:
                    _exec_on_conn(conn, "UPDATE mesas SET estado = 'disponible' WHERE id_mesa = %s", (id_mesa,))
                transaction_doc = {"id_transaccion": id_transaccion, "metodo_pago": metodo_pago, "monto": total}

            fondo_doc = None
            if porcentaje_fondo > 0:
                monto_aporte = round(total * porcentaje_fondo / 100, 2)
                cur_fondo = _exec_on_conn(conn, """
                    INSERT INTO fondos_sociales (id_pedido, porcentaje, monto_base, monto_aporte, destino)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_fondo
                """, (id_pedido, porcentaje_fondo, total, monto_aporte, payload.get("destino_fondo") or "Ollas comunes"))
                row_fondo = cur_fondo.fetchone()
                id_fondo = int(row_fondo[0]) if row_fondo else int(getattr(cur_fondo, "lastrowid", 0) or 0)
                fondo_doc = {"id_fondo": id_fondo, "porcentaje": porcentaje_fondo, "monto_aporte": monto_aporte}

            order = _fetchone_on_conn(conn, "SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            details = _fetchall_on_conn(conn, "SELECT * FROM pedido_detalles WHERE id_pedido = %s", (id_pedido,))
    except ApiError:
        raise
    except Exception as exc:
        log_event("ERROR", "CREATE_ORDER", "pedidos", "Error al crear pedido", {"error": str(exc), "payload": payload})
        raise ApiError(400, str(exc)) from exc

    response = {"pedido": order, "detalles": details, "transaccion": transaction_doc, "fondo_social": fondo_doc}
    log_event("INFO", "CREATE_ORDER", "pedidos", "Pedido creado con descuento de stock", {"id_pedido": id_pedido, "total": total})
    return response


def update_order_status(id_pedido: int, estado: str) -> dict[str, Any]:
    if estado not in VALID_ORDER_STATES:
        raise ApiError(400, "Estado no válido")
    with transaction() as conn:
        row = _fetchone_on_conn(conn, "SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        if row is None:
            raise ApiError(404, "Pedido no encontrado")
        _exec_on_conn(conn, "UPDATE pedidos SET estado = %s, actualizado_en = NOW() WHERE id_pedido = %s", (estado, id_pedido))
        if estado in {"entregado", "pagado", "cancelado"} and row["id_mesa"]:
            _exec_on_conn(conn, "UPDATE mesas SET estado = 'disponible' WHERE id_mesa = %s", (row["id_mesa"],))
        updated = _fetchone_on_conn(conn, "SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
    log_event("INFO", "UPDATE_ORDER_STATUS", "pedidos", "Estado de pedido actualizado", {"id_pedido": id_pedido, "estado": estado})
    return updated


def confirm_payment(id_pedido: int, metodo_pago: str, referencia: str | None = None) -> dict[str, Any]:
    if metodo_pago not in VALID_PAYMENT_METHODS:
        raise ApiError(400, "Método de pago no válido")
    with transaction() as conn:
        pedido = _fetchone_on_conn(conn, "SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        if pedido is None:
            raise ApiError(404, "Pedido no encontrado")
        tx = _fetchone_on_conn(conn, "SELECT * FROM transacciones WHERE id_pedido = %s", (id_pedido,))
        if tx is None:
            cur = _exec_on_conn(
                conn,
                "INSERT INTO transacciones (id_pedido, metodo_pago, monto, estado, referencia) VALUES (%s, %s, %s, 'pagado', %s) RETURNING id_transaccion",
                (id_pedido, metodo_pago, pedido["total"], referencia),
            )
            row = cur.fetchone()
            id_transaccion = int(row[0]) if row else int(getattr(cur, "lastrowid", 0) or 0)
        else:
            _exec_on_conn(
                conn,
                "UPDATE transacciones SET metodo_pago = %s, estado = 'pagado', referencia = %s, fecha = NOW() WHERE id_pedido = %s",
                (metodo_pago, referencia, id_pedido),
            )
            id_transaccion = tx["id_transaccion"]
        _exec_on_conn(conn, "UPDATE pedidos SET estado = 'pagado', actualizado_en = NOW() WHERE id_pedido = %s", (id_pedido,))
        if pedido["id_mesa"]:
            _exec_on_conn(conn, "UPDATE mesas SET estado = 'disponible' WHERE id_mesa = %s", (pedido["id_mesa"],))
        transaction_row = _fetchone_on_conn(conn, "SELECT * FROM transacciones WHERE id_transaccion = %s", (id_transaccion,))
    log_event("INFO", "CONFIRM_PAYMENT", "transacciones", "Pago confirmado", {"id_pedido": id_pedido, "id_transaccion": id_transaccion})
    return transaction_row


def adjust_inventory(id_producto: int, tipo_movimiento: str, cantidad: int, motivo: str) -> dict[str, Any]:
    if tipo_movimiento not in {"entrada", "salida", "ajuste"}:
        raise ApiError(400, "tipo_movimiento no válido")
    if cantidad <= 0:
        raise ApiError(400, "cantidad debe ser mayor a cero")
    with transaction() as conn:
        inv = _fetchone_on_conn(conn, "SELECT * FROM inventario WHERE id_producto = %s", (id_producto,))
        if inv is None:
            raise ApiError(404, "Inventario no encontrado para el producto")
        stock_anterior = int(inv["stock_actual"])
        if tipo_movimiento == "entrada":
            stock_nuevo = stock_anterior + cantidad
        elif tipo_movimiento == "salida":
            if stock_anterior < cantidad:
                raise ApiError(409, "Stock insuficiente para salida")
            stock_nuevo = stock_anterior - cantidad
        else:
            stock_nuevo = cantidad
        _exec_on_conn(conn, "UPDATE inventario SET stock_actual = %s, actualizado_en = NOW() WHERE id_producto = %s", (stock_nuevo, id_producto))
        cur = _exec_on_conn(conn, """
            INSERT INTO inventario_movimientos (id_producto, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, motivo)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_movimiento
        """, (id_producto, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, motivo))
        row = cur.fetchone()
        id_movimiento = int(row[0]) if row else int(getattr(cur, "lastrowid", 0) or 0)
        movimiento = _fetchone_on_conn(conn, "SELECT * FROM inventario_movimientos WHERE id_movimiento = %s", (id_movimiento,))
    log_event("INFO", "ADJUST_INVENTORY", "inventario", "Inventario ajustado", movimiento)
    return movimiento


def sales_summary(desde: str | None = None, hasta: str | None = None) -> dict[str, Any]:
    where = ["t.estado = 'pagado'"]
    params: list[Any] = []
    if desde:
        where.append("CAST(t.fecha AS DATE) >= CAST(%s AS DATE)")
        params.append(desde)
    if hasta:
        where.append("CAST(t.fecha AS DATE) <= CAST(%s AS DATE)")
        params.append(hasta)
    where_sql = " AND ".join(where)
    row = fetch_one(f"""
        SELECT COUNT(*) AS transacciones_pagadas,
               COALESCE(SUM(t.monto), 0) AS ventas_totales,
               COALESCE(AVG(t.monto), 0) AS ticket_promedio
        FROM transacciones t
        WHERE {where_sql}
    """, tuple(params))
    fondo = fetch_one("""
        SELECT COALESCE(SUM(monto_aporte), 0) AS aporte_ollas_comunes
        FROM fondos_sociales
        WHERE (%s IS NULL OR CAST(fecha AS DATE) >= CAST(%s AS DATE))
          AND (%s IS NULL OR CAST(fecha AS DATE) <= CAST(%s AS DATE))
    """, (desde, desde, hasta, hasta))
    return {**(row or {}), **(fondo or {})}


def top_products(limit: int = 10) -> list[dict[str, Any]]:
    return fetch_all("""
        SELECT p.id_producto, p.nombre, SUM(d.cantidad) AS cantidad_vendida,
               ROUND(SUM(d.subtotal), 2) AS ingreso_generado
        FROM pedido_detalles d
        JOIN productos p ON p.id_producto = d.id_producto
        JOIN pedidos pe ON pe.id_pedido = d.id_pedido
        WHERE pe.estado != 'cancelado'
        GROUP BY p.id_producto, p.nombre
        ORDER BY cantidad_vendida DESC, ingreso_generado DESC
        LIMIT %s
    """, (limit,))


def low_stock() -> list[dict[str, Any]]:
    return fetch_all("""
        SELECT p.id_producto, p.nombre, i.stock_actual, p.stock_minimo, i.unidad_medida,
               CASE WHEN i.stock_actual = 0 THEN 'agotado' ELSE 'bajo' END AS estado_stock
        FROM productos p
        JOIN inventario i ON i.id_producto = p.id_producto
        WHERE i.stock_actual <= p.stock_minimo AND p.activo = 1
        ORDER BY i.stock_actual ASC
    """)


def orders_by_status() -> list[dict[str, Any]]:
    return fetch_all("""
        SELECT estado, COUNT(*) AS total_pedidos, COALESCE(SUM(total), 0) AS monto_total
        FROM pedidos
        GROUP BY estado
        ORDER BY total_pedidos DESC
    """)


def social_fund_summary() -> dict[str, Any]:
    row = fetch_one("""
        SELECT COUNT(*) AS pedidos_con_aporte,
               COALESCE(SUM(monto_base), 0) AS base_total,
               COALESCE(SUM(monto_aporte), 0) AS aporte_total,
               COALESCE(MAX(destino), 'Ollas comunes') AS destino
        FROM fondos_sociales
    """)
    latest = fetch_all("SELECT * FROM fondos_sociales ORDER BY fecha DESC LIMIT 10")
    return {"resumen": row, "ultimos_aportes": latest}


def order_audit(id_pedido: int) -> dict[str, Any]:
    pedido = fetch_one("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
    if not pedido:
        raise ApiError(404, "Pedido no encontrado")
    detalles = fetch_all("""
        SELECT d.*, p.nombre AS producto
        FROM pedido_detalles d
        JOIN productos p ON p.id_producto = d.id_producto
        WHERE d.id_pedido = %s
    """, (id_pedido,))
    transaccion = fetch_one("SELECT * FROM transacciones WHERE id_pedido = %s", (id_pedido,))
    movimientos = fetch_all("SELECT * FROM inventario_movimientos WHERE id_pedido = %s", (id_pedido,))
    fondo = fetch_one("SELECT * FROM fondos_sociales WHERE id_pedido = %s", (id_pedido,))
    return {
        "pedido": pedido,
        "detalles": detalles,
        "transaccion": transaccion,
        "movimientos_inventario": movimientos,
        "fondo_social": fondo,
    }
