"""Catálogo de tablas expuestas por el CRUD genérico.

Sin cambios respecto a la versión original: solo metadatos de tablas y campos.
"""
TABLES = {
    "roles": {
        "pk": "id_rol",
        "fields": ["nombre", "descripcion"],
        "required": ["nombre"],
    },
    "usuarios": {
        "pk": "id_usuario",
        "fields": ["nombre", "email", "password_hash", "id_rol", "activo"],
        "required": ["nombre", "email", "password_hash", "id_rol"],
    },
    "oauth_cuentas": {
        "pk": "id_oauth",
        "fields": ["id_usuario", "proveedor", "proveedor_user_id", "email", "nombre", "avatar_url", "ultimo_login"],
        "required": ["id_usuario", "proveedor", "proveedor_user_id", "email"],
    },
    "sesiones_api": {
        "pk": "id_sesion",
        "fields": ["id_usuario", "jti", "proveedor", "keycloak_access_token", "expira_en", "cerrado_en"],
        "required": ["id_usuario", "jti", "proveedor", "expira_en"],
    },
    "categorias": {
        "pk": "id_categoria",
        "fields": ["nombre", "descripcion", "activo"],
        "required": ["nombre"],
    },
    "mesas": {
        "pk": "id_mesa",
        "fields": ["codigo", "capacidad", "estado"],
        "required": ["codigo"],
    },
    "productos": {
        "pk": "id_producto",
        "fields": ["id_categoria", "nombre", "descripcion", "precio", "stock_minimo", "imagen_url", "activo"],
        "required": ["id_categoria", "nombre", "precio"],
    },
    "inventario": {
        "pk": "id_inventario",
        "fields": ["id_producto", "stock_actual", "unidad_medida"],
        "required": ["id_producto"],
    },
    "pedidos": {
        "pk": "id_pedido",
        "fields": ["id_mesa", "id_usuario", "estado", "comentario", "subtotal", "impuesto", "descuento", "total"],
        "required": ["id_usuario"],
    },
    "pedido_detalles": {
        "pk": "id_detalle",
        "fields": ["id_pedido", "id_producto", "cantidad", "precio_unitario", "comentario", "subtotal"],
        "required": ["id_pedido", "id_producto", "cantidad", "precio_unitario", "subtotal"],
    },
    "transacciones": {
        "pk": "id_transaccion",
        "fields": ["id_pedido", "metodo_pago", "monto", "estado", "referencia"],
        "required": ["id_pedido", "metodo_pago", "monto"],
    },
    "inventario_movimientos": {
        "pk": "id_movimiento",
        "fields": ["id_producto", "tipo_movimiento", "cantidad", "stock_anterior", "stock_nuevo", "motivo", "id_pedido"],
        "required": ["id_producto", "tipo_movimiento", "cantidad", "stock_anterior", "stock_nuevo", "motivo"],
    },
    "fondos_sociales": {
        "pk": "id_fondo",
        "fields": ["id_pedido", "porcentaje", "monto_base", "monto_aporte", "destino"],
        "required": ["id_pedido", "monto_base", "monto_aporte"],
    },
    "integraciones": {
        "pk": "id_integracion",
        "fields": ["nombre", "tipo", "endpoint_base", "estado", "configuracion_json"],
        "required": ["nombre", "tipo"],
    },
    "comprobantes_electronicos": {
        "pk": "id_comprobante",
        "fields": [
            "id_pedido", "tipo_comprobante", "codigo_tipo_comprobante", "serie", "numero",
            "cliente_tipo_documento", "cliente_numero_documento", "cliente_nombre", "cliente_direccion",
            "subtotal", "igv", "total", "estado_sunat", "codigo_sunat", "mensaje_sunat",
            "external_id", "pdf_url", "xml_url", "cdr_url", "payload_json", "respuesta_json"
        ],
        "required": ["tipo_comprobante", "codigo_tipo_comprobante", "serie", "numero", "cliente_tipo_documento", "cliente_nombre", "subtotal", "igv", "total", "payload_json"],
    },
}
