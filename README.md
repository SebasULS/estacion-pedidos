# Estación de Pedidos

Aplicación full-stack para gestión de pedidos en restaurante: mozo, cocina,
inventario, pagos, reportes, facturación SUNAT, integraciones de delivery y
OAuth con Keycloak.

## Stack

| Capa | Tecnología |
|---|---|
| **Frontend** | Vue.js 3 + Vite |
| **Backend** | Flask 3 (Python) |
| **Base de datos** | PostgreSQL en Supabase |
| **OAuth 2.0 / OIDC** | Keycloak (Authorization Code Flow + PKCE S256) |
| **Log NoSQL** | JSONL local |
| **Deploy** | Vercel (backend serverless + frontend estático) |

## Estructura del proyecto

```
estacion-pedidos/
├── backend/      # Flask API + Keycloak + Supabase
│   ├── app/      # Código de la aplicación
│   ├── api/      # Entry point Vercel serverless
│   ├── requirements.txt
│   ├── run.py
│   ├── vercel.json
│   └── .env.example
├── frontend/     # Vue 3 + Vite
│   ├── src/
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
├── docs/         # Guías de configuración
│   ├── GUIA_SUPABASE.md
│   ├── GUIA_KEYCLOAK.md
│   └── GUIA_VERCEL.md
├── .gitignore
└── README.md     # Este archivo
```

## Módulos funcionales

- **Dashboard** con KPIs (ventas, ticket promedio, fondo social, stock bajo).
- **Mozo**: catálogo visual, búsqueda, carrito y registro de pedidos.
- **Pedidos**: historial, cambio de estado y auditoría completa.
- **Inventario**: stock, ajustes (entrada/salida/ajuste) y movimientos.
- **Pagos**: confirmación de pagos con múltiples métodos.
- **Reportes**: ventas, productos más vendidos, pedidos por estado, stock bajo, fondo social.
- **Facturación SUNAT**: emisión de boletas/facturas vía API REST (`personalId` + `personaToken`), modo simulado o real.
- **Integraciones**: PedidosYa, Rappi, sistema contable (trabajos futuros simulados).
- **CRUD API**: panel para probar endpoints de las 15 tablas.
- **Logs NoSQL**: visor del log JSONL.
- **OAuth Keycloak**: login con Authorization Code Flow + PKCE, token Bearer local, logout con revocación.

## Quickstart (desarrollo local)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Editar con tus credenciales
python run.py                     # http://localhost:8000
```

> Sin `DATABASE_URL`, el backend usa SQLite local como fallback. Para
> integración real con Supabase + Keycloak, sigue las guías en `docs/`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxy a :8000)
```

### 3. Probar el flujo

1. Abre <http://localhost:5173>.
2. Si Keycloak está configurado: clic en **Continuar con Keycloak**.
3. Si no: clic en **Usar token demo API** (modo offline).

## Guías de configuración (acciones humanas)

| Guía | Qué cubre |
|---|---|
| [`docs/GUIA_SUPABASE.md`](./docs/GUIA_SUPABASE.md) | Crear proyecto Supabase, obtener `DATABASE_URL`, crear esquema, seed, RLS |
| [`docs/GUIA_KEYCLOAK.md`](./docs/GUIA_KEYCLOAK.md) | Levantar Keycloak (Docker), crear realm/client/usuarios, obtener `CLIENT_SECRET` |
| [`docs/GUIA_VERCEL.md`](./docs/GUIA_VERCEL.md) | Importar repo en Vercel, configurar backend serverless + frontend estático, dominios |

## Variables de entorno mínimas

### Backend (`backend/.env`)
```env
SECRET_KEY=<larga-y-aleatoria>
DATABASE_URL=postgresql://postgres:<pass>@db.<proyecto>.supabase.co:5432/postgres?sslmode=require
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=estacion-pedidos
KEYCLOAK_CLIENT_ID=estacion-pedidos-frontend
KEYCLOAK_CLIENT_SECRET=<secret>
KEYCLOAK_REDIRECT_URI=http://localhost:8000/api/auth/oauth/keycloak/callback
ALLOW_DEMO_AUTH=true   # false en producción
```

### Frontend (`frontend/.env`)
```env
VITE_API_URL=           # vacío en dev (proxy Vite), URL completa en prod
```

## Endpoints principales

Ver [`backend/README.md`](./backend/README.md) para el listado completo de
rutas, métodos y ejemplos.

## Migración desde la versión anterior

Esta versión reemplaza la implementación anterior (SQLite + Google OAuth):
- **Base de datos**: SQLite → PostgreSQL (Supabase). Esquema migrado a
  `BIGSERIAL`, `NOW()`, `TIMESTAMPTZ`, `INSERT ... ON CONFLICT DO NOTHING`.
- **OAuth**: Google → Keycloak. Endpoints `/api/auth/oauth/keycloak/*`,
  columna `google_access_token` → `keycloak_access_token`, proveedor
  `'google'` → `'keycloak'`.
- **Frontend**: CDN (`vue.global.prod.js`) → Vite + SFCs (`App.vue`).
- **Lógica de negocio**: sin cambios (servicios, integraciones SUNAT/PedidosYa,
  reportes, CRUD, logs JSONL).

## Licencia

Proyecto académico / demostración. Uso libre con atribución.
