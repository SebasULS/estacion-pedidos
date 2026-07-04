import json

from app.db import get_connection, init_db, reset_db
from app.nosql_logger import log_event


def seed_demo(reset: bool = False) -> dict:
    if reset:
        reset_db()
    else:
        init_db()

    with get_connection() as conn:
        # Roles
        _exec(conn, "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (1, 'Administrador', 'Acceso total al sistema') ON CONFLICT (id_rol) DO NOTHING")
        _exec(conn, "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (2, 'Mozo', 'Registra pedidos y consulta historial') ON CONFLICT (id_rol) DO NOTHING")
        _exec(conn, "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (3, 'Cocina', 'Consulta pedidos en preparación') ON CONFLICT (id_rol) DO NOTHING")

        # Usuarios demo
        _exec(
            conn,
            """
            INSERT INTO usuarios (id_usuario, nombre, email, password_hash, id_rol, activo)
            VALUES (1, 'Administrador Demo', 'admin@estacion.local', 'demo_hash_no_productivo', 1, 1)
            ON CONFLICT (id_usuario) DO NOTHING
            """,
        )
        _exec(
            conn,
            """
            INSERT INTO usuarios (id_usuario, nombre, email, password_hash, id_rol, activo)
            VALUES (2, 'Mozo Demo', 'mozo@estacion.local', 'demo_hash_no_productivo', 2, 1)
            ON CONFLICT (id_usuario) DO NOTHING
            """,
        )

        # Categorías
        categorias = [
            (1, 'Comidas rápidas', 'Platos principales de rápida preparación'),
            (2, 'Bebidas', 'Bebidas frías y calientes'),
            (3, 'Extras', 'Adicionales y complementos'),
        ]
        for row in categorias:
            _exec(
                conn,
                "INSERT INTO categorias (id_categoria, nombre, descripcion) VALUES (%s, %s, %s) ON CONFLICT (id_categoria) DO NOTHING",
                row,
            )

        # Mesas
        for id_mesa, codigo, capacidad in [(1, 'M01', 4), (2, 'M02', 4), (3, 'M03', 6), (4, 'M04', 2), (5, 'M05', 8)]:
            _exec(
                conn,
                "INSERT INTO mesas (id_mesa, codigo, capacidad) VALUES (%s, %s, %s) ON CONFLICT (id_mesa) DO NOTHING",
                (id_mesa, codigo, capacidad),
            )

        # Productos
        productos = [
            (1, 1, 'Hamburguesa', 'Hamburguesa clásica con papas', 12.00, 5, 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600'),
            (2, 1, 'Pan Caliente', 'Pan relleno caliente', 8.50, 5, 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600'),
            (3, 1, 'Pepito', 'Sándwich pepito', 10.00, 4, 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=600'),
            (4, 1, 'Alitas BBQ', 'Porción de alitas con salsa BBQ', 15.00, 4, 'https://images.unsplash.com/photo-1527477396000-e27163b481c2?w=600'),
            (5, 3, 'Tequeños', 'Porción de tequeños', 9.00, 4, 'https://images.unsplash.com/photo-1548340748-6d2b7d7da280?w=600'),
            (6, 1, 'Salchipapa', 'Salchipapa personal', 11.00, 5, 'https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?w=600'),
        ]
        for product in productos:
            _exec(
                conn,
                """
                INSERT INTO productos (id_producto, id_categoria, nombre, descripcion, precio, stock_minimo, imagen_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_producto) DO NOTHING
                """,
                product,
            )

        # Inventario
        inventario = [(1, 1, 30), (2, 2, 25), (3, 3, 20), (4, 4, 15), (5, 5, 18), (6, 6, 22)]
        for row in inventario:
            _exec(
                conn,
                """
                INSERT INTO inventario (id_inventario, id_producto, stock_actual, unidad_medida)
                VALUES (%s, %s, %s, 'unidad')
                ON CONFLICT (id_inventario) DO NOTHING
                """,
                row,
            )

        # Integraciones
        integraciones = [
            ('SUNAT', 'facturacion', 'https://api.sunat.example/desarrollo', 'simulado', {'modo': 'desarrollo', 'auth': 'personalId + personaToken', 'endpoints': ['/api/sunat/comprobantes', '/api/sunat/pedidos/<id>/boleta', '/api/sunat/pedidos/<id>/factura']}),
            ('PedidosYa', 'delivery', 'https://api.pedidosya.com/simulado', 'simulado', {'modo': 'sandbox'}),
            ('Rappi', 'delivery', 'https://api.rappi.com/simulado', 'simulado', {'modo': 'sandbox'}),
            ('Sistema Contable', 'contabilidad', None, 'planificado', {'formato': 'csv/xlsx/api'}),
        ]
        for nombre, tipo, endpoint, estado, config in integraciones:
            _exec(
                conn,
                """
                INSERT INTO integraciones (nombre, tipo, endpoint_base, estado, configuracion_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nombre) DO NOTHING
                """,
                (nombre, tipo, endpoint, estado, json.dumps(config, ensure_ascii=False)),
            )

        # Commit (solo necesario en SQLite fallback; PostgreSQL usa context manager transaccional)
        if hasattr(conn, "commit"):
            try:
                conn.commit()
            except Exception:
                pass

        counts = {}
        for table in ["roles", "usuarios", "categorias", "mesas", "productos", "inventario", "integraciones"]:
            row = _fetchone(conn, f"SELECT COUNT(*) AS total FROM {table}")
            counts[table] = row["total"] if row else 0

    log_event("INFO", "SEED_DEMO", "sistema", "Datos demo cargados", counts)
    return {"status": "ok", **counts}


def _exec(conn, sql: str, params: tuple = ()):
    """Ejecuta SQL en PostgreSQL o SQLite de forma uniforme."""
    if hasattr(conn, "cursor"):
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
    else:
        conn.execute(sql, params or ())


def _fetchone(conn, sql: str, params: tuple = ()):
    if hasattr(conn, "cursor"):
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            if row is None:
                return None
            colnames = [desc[0] for desc in cur.description]
            return dict(zip(colnames, row))
    row = conn.execute(sql, params or ()).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    print(seed_demo(reset=False))
