# Estación de Pedidos — Frontend (Vue 3 + Vite)

SPA de gestión para restaurante construida con **Vue 3** (Options API) y empaquetada con **Vite**. Conversión 1:1 del frontend original (Vue 3 por CDN) a un proyecto Vite con un único SFC `App.vue`.

## Stack
- **Vue 3** (`vue@^3.4`) — Options API (`data`, `computed`, `mounted`, `methods`).
- **Vite 5** + `@vitejs/plugin-vue`.
- Autenticación mediante **Keycloak OAuth** (reemplaza al Google OAuth original).
- Estilos globales en `src/styles.css` (copia literal del `styles.css` original).

## Estructura
```
frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.js          # createApp(App).mount('#app') + import global styles
│   ├── App.vue          # Único SFC con todo el template + lógica del app.js original
│   ├── config.js        # API_BASE = import.meta.env.VITE_API_URL || '/api'
│   └── styles.css       # Estilos globales (idéntico al original)
├── index.html           # Entry Vite (#app + /src/main.js)
├── package.json
├── vite.config.js       # Proxy /api y /health a http://localhost:8000 en dev
├── .env.example
├── .gitignore
└── README.md
```

## Requisitos
- Node.js 18+ y npm.
- Backend Flask corriendo en `http://localhost:8000` (ver `../backend/`).

## Desarrollo
```bash
npm install
npm run dev
```
Vite sirve el frontend en `http://localhost:5173` y hace proxy de `/api` y `/health` al backend Flask en `http://localhost:8000` (configurado en `vite.config.js`). No se necesita configurar `VITE_API_URL` en desarrollo.

## Build
```bash
npm run build      # genera dist/
npm run preview    # sirve dist/ localmente para verificar el build
```
El directorio `dist/` contiene archivos estáticos que pueden ser servidos por:
- Flask (en producción, sirviendo `dist/` como estáticos).
- Vercel / Netlify / cualquier CDN estático (ajustando `VITE_API_URL` al backend deployado).

## Variables de entorno
| Variable         | Descripción                                                                |
| ---------------- | -------------------------------------------------------------------------- |
| `VITE_API_URL`   | URL base del backend. Vacío en dev (usa el proxy). En prod, p.ej. `https://api.midominio.com/api`. |

## Autenticación Keycloak OAuth
El botón **"Continuar con Keycloak"** en la pantalla de login redirige a:

```
GET /api/auth/oauth/keycloak/login?next=/
```

El backend Flask inicia el flujo OIDC contra Keycloak y, tras el callback, redirige al frontend (`/`) con el token en el hash:

```
http://localhost:5173/#access_token=...
```

`App.vue` lee `window.location.hash` en `mounted()` (método `restoreTokenFromHash`) y guarda el token en `localStorage` para usarlo como `Authorization: Bearer <token>` en todas las llamadas a `/api/*`.

El botón **"Usar token demo API"** llama a `POST /api/auth/demo-login` (útil para presentaciones sin Keycloak disponible).

## Notas de migración desde el frontend CDN original
- `app.js` y el `<div id="app">` del `index.html` originales se fusionan en `src/App.vue` (Options API, sin `<script setup>`).
- El campo `data.API = '/api'` ahora se lee de `src/config.js` (`API_BASE`).
- `googleLogin()` → `keycloakLogin()` con URL `/api/auth/oauth/keycloak/login?next=/` (antes `?next=/app`).
- `oauth_google_configurado` → `oauth_keycloak_configurado` en todo el código.
- Texto UI "Google OAuth" → "Keycloak OAuth" / "Continuar con Keycloak".
- `logout()`: `data.google_revoked` → `data.keycloak_revoked`; mensaje "autorización Google revocada" → "autorización Keycloak revocada".
- `restoreTokenFromHash()`: notificación "Sesión OAuth restaurada desde Google" → "...desde Keycloak".
- El ejemplo JSON del CRUD para `oauth_cuentas` usa `"proveedor": "keycloak"` (antes `"google"`).
- El enlace "API Health" del topbar ahora es `:href="API + '/health'"` para respetar el `API_BASE` (funciona tanto en dev con proxy como en producción con dominio configurado).
- `styles.css` es una copia **idéntica** del original (788 líneas, sin cambios).
