-- ============================================================
-- Estación de Pedidos - Esquema PostgreSQL (Supabase)
-- ============================================================
-- Migrado desde SQLite para correr en Supabase / PostgreSQL 14+.
-- Cambios principales:
--   * INTEGER PRIMARY KEY AUTOINCREMENT -> BIGSERIAL PRIMARY KEY
--   * datetime('now')                   -> NOW()
--   * Proveedor OAuth: 'google'         -> 'keycloak'
--   * Columna google_access_token       -> keycloak_access_token
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id_rol BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    id_rol BIGINT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
);

CREATE TABLE IF NOT EXISTS sesiones_api (
    id_sesion BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    jti TEXT NOT NULL UNIQUE,
    proveedor TEXT NOT NULL DEFAULT 'local' CHECK (proveedor IN ('local','demo','keycloak')),
    keycloak_access_token TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_en TIMESTAMPTZ NOT NULL,
    cerrado_en TIMESTAMPTZ,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS oauth_cuentas (
    id_oauth BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    proveedor TEXT NOT NULL CHECK (proveedor IN ('keycloak')),
    proveedor_user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    nombre TEXT,
    avatar_url TEXT,
    ultimo_login TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    UNIQUE (proveedor, proveedor_user_id)
);

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS mesas (
    id_mesa BIGSERIAL PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    capacidad INTEGER NOT NULL DEFAULT 4,
    estado TEXT NOT NULL DEFAULT 'disponible' CHECK (estado IN ('disponible','ocupada','reservada','inactiva'))
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto BIGSERIAL PRIMARY KEY,
    id_categoria BIGINT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    precio NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 5 CHECK (stock_minimo >= 0),
    imagen_url TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);

CREATE TABLE IF NOT EXISTS inventario (
    id_inventario BIGSERIAL PRIMARY KEY,
    id_producto BIGINT NOT NULL UNIQUE,
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    unidad_medida TEXT NOT NULL DEFAULT 'unidad',
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido BIGSERIAL PRIMARY KEY,
    id_mesa BIGINT,
    id_usuario BIGINT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'registrado' CHECK (estado IN ('registrado','en_preparacion','entregado','pagado','cancelado')),
    comentario TEXT,
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    impuesto NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (impuesto >= 0),
    descuento NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    total NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_mesa) REFERENCES mesas(id_mesa),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

CREATE TABLE IF NOT EXISTS pedido_detalles (
    id_detalle BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL,
    id_producto BIGINT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    comentario TEXT,
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

CREATE TABLE IF NOT EXISTS transacciones (
    id_transaccion BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL UNIQUE,
    metodo_pago TEXT NOT NULL CHECK (metodo_pago IN ('efectivo','yape','plin','tarjeta','transferencia')),
    monto NUMERIC(12,2) NOT NULL CHECK (monto >= 0),
    estado TEXT NOT NULL DEFAULT 'pagado' CHECK (estado IN ('pendiente','pagado','anulado')),
    referencia TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventario_movimientos (
    id_movimiento BIGSERIAL PRIMARY KEY,
    id_producto BIGINT NOT NULL,
    tipo_movimiento TEXT NOT NULL CHECK (tipo_movimiento IN ('entrada','salida','ajuste')),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    stock_anterior INTEGER NOT NULL CHECK (stock_anterior >= 0),
    stock_nuevo INTEGER NOT NULL CHECK (stock_nuevo >= 0),
    motivo TEXT NOT NULL,
    id_pedido BIGINT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS fondos_sociales (
    id_fondo BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL UNIQUE,
    porcentaje NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (porcentaje >= 0),
    monto_base NUMERIC(12,2) NOT NULL CHECK (monto_base >= 0),
    monto_aporte NUMERIC(12,2) NOT NULL CHECK (monto_aporte >= 0),
    destino TEXT NOT NULL DEFAULT 'Ollas comunes',
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS integraciones (
    id_integracion BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL CHECK (tipo IN ('facturacion','delivery','contabilidad','notificacion')),
    endpoint_base TEXT,
    estado TEXT NOT NULL DEFAULT 'planificado' CHECK (estado IN ('planificado','simulado','activo','inactivo')),
    configuracion_json TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comprobantes_electronicos (
    id_comprobante BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT,
    tipo_comprobante TEXT NOT NULL CHECK (tipo_comprobante IN ('boleta','factura')),
    codigo_tipo_comprobante TEXT NOT NULL CHECK (codigo_tipo_comprobante IN ('01','03')),
    serie TEXT NOT NULL,
    numero TEXT NOT NULL,
    cliente_tipo_documento TEXT NOT NULL,
    cliente_numero_documento TEXT,
    cliente_nombre TEXT NOT NULL,
    cliente_direccion TEXT,
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    igv NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (igv >= 0),
    total NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    estado_sunat TEXT NOT NULL DEFAULT 'PENDIENTE',
    codigo_sunat TEXT,
    mensaje_sunat TEXT,
    external_id TEXT,
    pdf_url TEXT,
    xml_url TEXT,
    cdr_url TEXT,
    payload_json TEXT NOT NULL,
    respuesta_json TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE SET NULL,
    UNIQUE (serie, numero)
);

CREATE INDEX IF NOT EXISTS idx_oauth_usuario ON oauth_cuentas(id_usuario);
CREATE INDEX IF NOT EXISTS idx_oauth_provider_user ON oauth_cuentas(proveedor, proveedor_user_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_jti ON sesiones_api(jti);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones_api(id_usuario);
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(id_categoria);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(creado_en);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos(estado);
CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha);
CREATE INDEX IF NOT EXISTS idx_detalles_producto ON pedido_detalles(id_producto);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto ON inventario_movimientos(id_producto);
CREATE INDEX IF NOT EXISTS idx_comprobantes_pedido ON comprobantes_electronicos(id_pedido);
CREATE INDEX IF NOT EXISTS idx_comprobantes_estado ON comprobantes_electronicos(estado_sunat);
