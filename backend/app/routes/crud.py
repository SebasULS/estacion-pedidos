from flask import Blueprint, jsonify, request

from app.auth import _exec_on_conn, _fetchone_on_conn
from app.db import fetch_all, fetch_one, transaction
from app.errors import ApiError
from app.models_meta import TABLES
from app.nosql_logger import log_event

crud_bp = Blueprint("crud", __name__, url_prefix="/api")


def get_meta(table: str) -> dict:
    if table not in TABLES:
        raise ApiError(404, "Tabla no permitida o no existente")
    return TABLES[table]


def validate_payload(meta: dict, payload: dict, partial: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise ApiError(400, "El cuerpo debe ser un objeto JSON")
    allowed = set(meta["fields"])
    filtered = {k: v for k, v in payload.items() if k in allowed}
    unknown = set(payload) - allowed
    if unknown:
        raise ApiError(400, f"Campos no permitidos: {', '.join(sorted(unknown))}")
    if not partial:
        missing = [field for field in meta.get("required", []) if field not in filtered or filtered[field] in (None, "")]
        if missing:
            raise ApiError(400, f"Campos obligatorios faltantes: {', '.join(missing)}")
    if not filtered and partial:
        raise ApiError(400, "No se enviaron campos válidos para actualizar")
    return filtered


@crud_bp.get("/<table>")
def list_records(table: str):
    meta = get_meta(table)
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = max(int(request.args.get("offset", 0)), 0)
    pk = meta["pk"]
    records = fetch_all(f"SELECT * FROM {table} ORDER BY {pk} DESC LIMIT %s OFFSET %s", (limit, offset))
    total = fetch_one(f"SELECT COUNT(*) AS total FROM {table}")["total"]
    return jsonify({"tabla": table, "total": total, "limit": limit, "offset": offset, "data": records})


@crud_bp.get("/<table>/<int:record_id>")
def get_record(table: str, record_id: int):
    meta = get_meta(table)
    pk = meta["pk"]
    record = fetch_one(f"SELECT * FROM {table} WHERE {pk} = %s", (record_id,))
    if not record:
        raise ApiError(404, "Registro no encontrado")
    return jsonify(record)


@crud_bp.post("/<table>")
def create_record(table: str):
    meta = get_meta(table)
    payload = validate_payload(meta, request.get_json(silent=True) or {}, partial=False)
    columns = list(payload.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    pk = meta["pk"]
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING {pk}"
    try:
        with transaction() as conn:
            cur = _exec_on_conn(conn, sql, tuple(payload[col] for col in columns))
            row = cur.fetchone()
            record_id = int(row[0]) if row else int(getattr(cur, "lastrowid", 0) or 0)
            record = _fetchone_on_conn(conn, f"SELECT * FROM {table} WHERE {pk} = %s", (record_id,))
    except Exception as exc:
        raise ApiError(400, f"No se pudo crear el registro: {exc}") from exc
    log_event("INFO", "CRUD_CREATE", table, "Registro creado", {"id": record_id})
    return jsonify(record), 201


@crud_bp.put("/<table>/<int:record_id>")
@crud_bp.patch("/<table>/<int:record_id>")
def update_record(table: str, record_id: int):
    meta = get_meta(table)
    payload = validate_payload(meta, request.get_json(silent=True) or {}, partial=True)
    assignments = ", ".join([f"{col} = %s" for col in payload.keys()])
    pk = meta["pk"]
    try:
        with transaction() as conn:
            existing = _fetchone_on_conn(conn, f"SELECT * FROM {table} WHERE {pk} = %s", (record_id,))
            if existing is None:
                raise ApiError(404, "Registro no encontrado")
            _exec_on_conn(conn, f"UPDATE {table} SET {assignments} WHERE {pk} = %s", tuple(payload.values()) + (record_id,))
            record = _fetchone_on_conn(conn, f"SELECT * FROM {table} WHERE {pk} = %s", (record_id,))
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(400, f"No se pudo actualizar el registro: {exc}") from exc
    log_event("INFO", "CRUD_UPDATE", table, "Registro actualizado", {"id": record_id})
    return jsonify(record)


@crud_bp.delete("/<table>/<int:record_id>")
def delete_record(table: str, record_id: int):
    meta = get_meta(table)
    pk = meta["pk"]
    try:
        with transaction() as conn:
            existing = _fetchone_on_conn(conn, f"SELECT * FROM {table} WHERE {pk} = %s", (record_id,))
            if existing is None:
                raise ApiError(404, "Registro no encontrado")
            _exec_on_conn(conn, f"DELETE FROM {table} WHERE {pk} = %s", (record_id,))
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(400, f"No se pudo eliminar el registro: {exc}") from exc
    log_event("INFO", "CRUD_DELETE", table, "Registro eliminado", {"id": record_id})
    return jsonify({"deleted": True, "tabla": table, "id": record_id})


@crud_bp.get("/productos/disponibles")
def list_available_products():
    """Retorna productos activos con stock > 0, unidos con su inventario."""
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = max(int(request.args.get("offset", 0)), 0)
    records = fetch_all("""
        SELECT p.*, i.stock_actual, i.unidad_medida
        FROM productos p
        JOIN inventario i ON i.id_producto = p.id_producto
        WHERE p.activo = 1 AND i.stock_actual > 0
        ORDER BY p.id_producto DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))
    total_row = fetch_one("""
        SELECT COUNT(*) AS total
        FROM productos p
        JOIN inventario i ON i.id_producto = p.id_producto
        WHERE p.activo = 1 AND i.stock_actual > 0
    """)
    return jsonify({
        "tabla": "productos",
        "total": total_row["total"],
        "limit": limit,
        "offset": offset,
        "data": records,
    })


@crud_bp.get("/productos/buscar")
def search_products():
    """Busca productos disponibles (activos con stock > 0) por nombre, descripción o categoría."""
    q = (request.args.get("q") or "").strip()
    if not q:
        raise ApiError(400, "El parámetro de búsqueda 'q' es obligatorio")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    pattern = f"%{q}%"
    records = fetch_all("""
        SELECT p.*, c.nombre AS categoria, i.stock_actual, i.unidad_medida
        FROM productos p
        JOIN categorias c ON c.id_categoria = p.id_categoria
        JOIN inventario i ON i.id_producto = p.id_producto
        WHERE p.activo = 1
          AND i.stock_actual > 0
          AND (
            p.nombre LIKE %s
            OR p.descripcion LIKE %s
            OR c.nombre LIKE %s
          )
        ORDER BY p.nombre ASC
        LIMIT %s OFFSET %s
    """, (pattern, pattern, pattern, limit, offset))
    total_row = fetch_one("""
        SELECT COUNT(*) AS total
        FROM productos p
        JOIN categorias c ON c.id_categoria = p.id_categoria
        JOIN inventario i ON i.id_producto = p.id_producto
        WHERE p.activo = 1
          AND i.stock_actual > 0
          AND (
            p.nombre LIKE %s
            OR p.descripcion LIKE %s
            OR c.nombre LIKE %s
          )
    """, (pattern, pattern, pattern))
    return jsonify({
        "busqueda": q,
        "total": total_row["total"],
        "limit": limit,
        "offset": offset,
        "data": records,
    })
