# Backend — Estación de Pedidos (Flask + Keycloak + Supabase)

API REST para la aplicación Estación de Pedidos. Implementa CRUD genérico,
operaciones funcionales (pedidos, pagos, inventario), reportes, integración
SUNAT, integración PedidosYa simulada, log NoSQL JSONL y **OAuth 2.0 / OpenID
Connect con Keycloak**. La base de datos es **PostgreSQL en Supabase** para
permitir deployment en Vercel.

## Stack

- **Framework**: Flask 3
- **Base de datos**: PostgreSQL (Supabase) vía `psycopg2-binary`
- **OAuth**: Keycloak 21+ con Authorization Code Flow + PKCE S256
- **CORS**: Flask-CORS (orígenes amplios para dev/prod)
- **Log NoSQL**: JSONL local (efímero en serverless; ver `nosql_logger.py`)
- **Tokens locales**: Bearer firmados con `itsdangerous`

## Estructura

```
backend/
├── app/
│   ├── __init__.py          # Factory de la app Flask
│   ├── auth.py              # OAuth Keycloak + tokens Bearer locales
│   ├── db.py                # Capa PostgreSQL (Supabase) con pool
│   ├── errors.py            # ApiError
│   ├── models_meta.py       # Metadatos de tablas para CRUD
│   ├── nosql_logger.py      # Logger JSONL
│   ├── schema.sql           # Esquema PostgreSQL (CREATE TABLE IF NOT EXISTS)
│   ├── seed.py              # Datos demo (roles, mesas, productos, etc.)
│   ├── services.py          # Lógica de pedidos/pagos/inventario/reportes
│   ├── integrations/
│   │   ├── sunat.py         # Integración SUNAT (real o simulada)
│   │   └── pedidosya.py     # Integración PedidosYa (simulada)
│   └── routes/
│       ├── auth.py          # /api/auth/* (Keycloak + demo + me + logout)
│       ├── crud.py          # /api/<tabla> CRUD genérico
│       ├── functional.py    # /api/funcionalidad/*
│       ├── reports.py       # /api/reportes/*
│       ├── future.py        # /api/trabajos-futuros/*
│       ├── logs.py          # /api/logs
│       ├── sunat.py         # /api/sunat/*
│       └── pedidosya.py     # /api/pedidosya/*
├── api/
│   └── index.py             # Entry point Vercel Serverless
├── requirements.txt
├── run.py                   # Entry point local (python run.py)
├── vercel.json              # Configuración Vercel
└── .env.example
```

## Instalación local

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Editar con datos de Supabase + Keycloak
python run.py                   # http://localhost:8000
```

> Si no hay `DATABASE_URL` configurada, el backend cae a SQLite local
> (`data/estacion_pedidos.db`) solo para desarrollo. **Para producción en
> Vercel es obligatorio configurar Supabase** (ver `../docs/GUIA_SUPABASE.md`).

## Endpoints principales

```http
GET  /api/health
GET  /api

# Auth (Keycloak)
GET  /api/auth/config
GET  /api/auth/oauth/keycloak/login            # redirige a Keycloak
GET  /api/auth/oauth/keycloak/login?mode=api   # devuelve authorization_url
GET  /api/auth/oauth/keycloak/callback
POST /api/auth/oauth/keycloak/token            # intercambio API
POST /api/auth/oauth/keycloak/id-token
POST /api/auth/demo-login                      # token demo (offline)
GET  /api/auth/me                               # requiere Bearer
GET  /api/auth/protegido                        # requiere Bearer
POST /api/auth/logout                           # requiere Bearer

# CRUD (todas las tablas: roles, usuarios, productos, pedidos, etc.)
GET    /api/<tabla>
GET    /api/<tabla>/<id>
POST   /api/<tabla>
PUT    /api/<tabla>/<id>
PATCH  /api/<tabla>/<id>
DELETE /api/<tabla>/<id>

# Funcionalidad
POST  /api/funcionalidad/pedidos
PATCH /api/funcionalidad/pedidos/<id>/estado
POST  /api/funcionalidad/pedidos/<id>/pago
POST  /api/funcionalidad/inventario/ajuste
GET   /api/funcionalidad/pedidos/<id>/auditoria

# Productos
GET /api/productos/disponibles
GET /api/productos/buscar?q=...

# Reportes
GET /api/reportes/ventas
GET /api/reportes/productos-mas-vendidos
GET /api/reportes/stock-bajo
GET /api/reportes/pedidos-por-estado
GET /api/reportes/fondo-social

# SUNAT
GET  /api/sunat/config
GET  /api/sunat/ruc/<ruc>
GET  /api/sunat/dni/<dni>
GET  /api/sunat/comprobantes
POST /api/sunat/comprobantes
POST /api/sunat/pedidos/<id>/boleta
POST /api/sunat/pedidos/<id>/factura
POST /api/sunat/comprobantes/<id>/consultar
POST /api/sunat/comprobantes/<id>/anular

# PedidosYa (simulado)
POST /api/pedidosya/nuevo
GET  /api/pedidosya/pedidos
POST /api/pedidosya/aceptar/<id>
POST /api/pedidosya/preparar/<id>
POST /api/pedidosya/listo/<id>
POST /api/pedidosya/camino/<id>
POST /api/pedidosya/entregado/<id>

# Logs NoSQL
GET  /api/logs?limit=100
POST /api/logs

# Trabajos futuros
GET  /api/trabajos-futuros
POST /api/trabajos-futuros/sunat/facturacion/simular
POST /api/trabajos-futuros/delivery/pedidosya/simular
POST /api/trabajos-futuros/delivery/rappi/simular
POST /api/trabajos-futuros/contabilidad/exportar/simular
```

## Variables de entorno

Ver `.env.example`. Las mínimas para producción:

```env
SECRET_KEY=<larga-y-segura>
DATABASE_URL=postgresql://postgres:<pass>@db.<proyecto>.supabase.co:5432/postgres?sslmode=require
KEYCLOAK_SERVER_URL=https://<tu-keycloak>
KEYCLOAK_REALM=estacion-pedidos
KEYCLOAK_CLIENT_ID=estacion-pedidos-frontend
KEYCLOAK_CLIENT_SECRET=<secret>
KEYCLOAK_REDIRECT_URI=https://<api-url>/api/auth/oauth/keycloak/callback
ALLOW_DEMO_AUTH=false   # desactivar en producción
```

## Guías relacionadas

- [`../docs/GUIA_SUPABASE.md`](../docs/GUIA_SUPABASE.md) — crear la base de datos en Supabase.
- [`../docs/GUIA_KEYCLOAK.md`](../docs/GUIA_KEYCLOAK.md) — configurar realm y cliente en Keycloak.
- [`../docs/GUIA_VERCEL.md`](../docs/GUIA_VERCEL.md) — desplegar backend + frontend en Vercel.

## Notas de seguridad

- `KEYCLOAK_CLIENT_SECRET` **no** debe subirse al repositorio.
- `ALLOW_DEMO_AUTH=true` solo en desarrollo; en producción, **`false`**.
- `SECRET_KEY` debe ser una cadena larga y aleatoria.
- El token Bearer local se firma con `SECRET_KEY`; rotarlo invalida todas las sesiones.
