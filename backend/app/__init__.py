"""Factory de la aplicación Flask para Estación de Pedidos.

Stack:
- Flask 3 + Flask-CORS
- PostgreSQL (Supabase) vía psycopg2
- OAuth 2.0 / OpenID Connect con Keycloak
- Log NoSQL en JSONL (compatible con Vercel cuando se monta en /tmp o storage externo)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, send_from_directory
from flask_cors import CORS

from app.db import init_db
from app.errors import ApiError
from app.seed import seed_demo

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "dist"
load_dotenv(BASE_DIR / ".env")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)

    # --- Base de datos (Supabase PostgreSQL) ---
    database_url = os.getenv("DATABASE_URL", "")
    # psycopg2 necesita postgresql:// pero Supabase a veces entrega postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # --- OAuth Keycloak ---
    keycloak_server_url = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
    keycloak_realm = os.getenv("KEYCLOAK_REALM", "estacion-pedidos")
    keycloak_client_id = os.getenv("KEYCLOAK_CLIENT_ID", "estacion-pedidos-frontend")
    keycloak_client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    keycloak_redirect_uri = os.getenv(
        "KEYCLOAK_REDIRECT_URI",
        "http://localhost:8000/api/auth/oauth/keycloak/callback",
    )

    app.config.update(
        DATABASE_URL=database_url,
        LOG_PATH=os.getenv("LOG_PATH", str(BASE_DIR / "data" / "logs_nosql.jsonl")),
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        # Keycloak OIDC
        KEYCLOAK_SERVER_URL=keycloak_server_url,
        KEYCLOAK_REALM=keycloak_realm,
        KEYCLOAK_CLIENT_ID=keycloak_client_id,
        KEYCLOAK_CLIENT_SECRET=keycloak_client_secret,
        KEYCLOAK_REDIRECT_URI=keycloak_redirect_uri,
        KEYCLOAK_SCOPE=os.getenv("KEYCLOAK_SCOPE", "openid email profile"),
        # Tokens locales
        ACCESS_TOKEN_EXPIRES_SECONDS=int(os.getenv("ACCESS_TOKEN_EXPIRES_SECONDS", "86400")),
        OAUTH_DEFAULT_ROLE_ID=int(os.getenv("OAUTH_DEFAULT_ROLE_ID", "2")),
        ALLOW_DEMO_AUTH=os.getenv("ALLOW_DEMO_AUTH", "true").lower() == "true",
        # SUNAT
        SUNAT_API_REAL=os.getenv("SUNAT_API_REAL", "false"),
        SUNAT_API_ENV=os.getenv("SUNAT_API_ENV", "DESARROLLO"),
        SUNAT_API_BASE_URL=os.getenv("SUNAT_API_BASE_URL", "https://api.sunat.example/desarrollo"),
        SUNAT_PERSONAL_ID=os.getenv("SUNAT_PERSONAL_ID"),
        SUNAT_PERSONA_TOKEN=os.getenv("SUNAT_PERSONA_TOKEN"),
        SUNAT_EMITIR_PATH=os.getenv("SUNAT_EMITIR_PATH", "/api/rest/documentos"),
        SUNAT_CONSULTAR_PATH=os.getenv("SUNAT_CONSULTAR_PATH", "/api/rest/documentos/consultar"),
        SUNAT_ANULAR_PATH=os.getenv("SUNAT_ANULAR_PATH", "/api/rest/documentos/anular"),
        SUNAT_SERIE_BOLETA=os.getenv("SUNAT_SERIE_BOLETA", "B001"),
        SUNAT_SERIE_FACTURA=os.getenv("SUNAT_SERIE_FACTURA", "F001"),
        SUNAT_TIMEOUT_SECONDS=os.getenv("SUNAT_TIMEOUT_SECONDS", "20"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        JSON_AS_ASCII=False,
        PREFERRED_URL_SCHEME=os.getenv("PREFERRED_URL_SCHEME", "http"),
    )
    if test_config:
        app.config.update(test_config)

    # CORS amplio para que el frontend Vite (puerto 5173) y Vercel llamen a la API.
    CORS(app, supports_credentials=True, origins="*")

    with app.app_context():
        try:
            init_db()
            if not app.config.get("TESTING"):
                seed_demo(reset=False)
        except Exception as exc:  # pragma: no cover - solo logging
            # En Vercel / entornos serverless no queremos romper el arranque
            # si la BD no está lista: las rutas devolverán 503 al consumirse.
            app.logger.warning(f"init_db/seed_demo falló: {exc}")

    # --- Blueprints ---
    from app.routes.crud import crud_bp
    from app.routes.functional import functional_bp
    from app.routes.reports import reports_bp
    from app.routes.future import future_bp
    from app.routes.logs import logs_bp
    from app.routes.sunat import sunat_bp
    from app.routes.pedidosya import pedidosya_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(crud_bp)
    app.register_blueprint(functional_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(future_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(sunat_bp)
    app.register_blueprint(pedidosya_bp)
    app.register_blueprint(auth_bp)

    # --- Manejadores de error ---
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify({"error": True, "detail": error.detail}), error.status_code

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({"error": True, "detail": "Ruta no encontrada"}), 404

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify({"error": True, "detail": "Error interno del servidor"}), 500

    # --- Rutas raíz y health ---
    @app.get("/health")
    @app.get("/api/health")
    def health():
        db_engine = "PostgreSQL (Supabase)" if database_url else "no configurada (falta DATABASE_URL)"
        db_ok = bool(database_url)
        return jsonify({
            "status": "ok" if db_ok else "degraded",
            "stack": "Flask + PostgreSQL/Supabase + JSONL NoSQL Log + OAuth 2.0 Keycloak + SUNAT API REST",
            "db_engine": db_engine,
            "oauth_provider": "keycloak",
            "database_configured": db_ok,
        })

    @app.get("/")
    def root():
        # En desarrollo: redirige al frontend Vite. En producción (Vercel) el
        # frontend se sirve desde su propio dominio; esta ruta sigue siendo útil
        # para inspección rápida de la API.
        frontend_dev_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        if os.getenv("VERCEL_ENV"):
            return jsonify({
                "nombre": "Estación de Pedidos API",
                "framework": "Flask",
                "oauth_provider": "keycloak",
                "frontend": "Desplegado por separado en Vercel",
                "api_base": "/api",
                "auth": "/api/auth/config",
            })
        return redirect(frontend_dev_url)

    @app.get("/api")
    def api_root():
        return jsonify({
            "nombre": "Estación de Pedidos API",
            "framework": "Flask",
            "database": "PostgreSQL / Supabase",
            "oauth_provider": "keycloak",
            "frontend": FRONTEND_DIR if FRONTEND_DIR.exists() else "Vue.js 3 (Vite) — ver /frontend",
            "api_base": "/api",
            "auth": "/api/auth/config",
            "documentacion": "Ver README.md y carpeta docs/",
        })

    # --- Servir frontend construido si existe (producción) ---
    @app.get("/app")
    def frontend_index():
        if FRONTEND_DIR.exists():
            return send_from_directory(FRONTEND_DIR, "index.html")
        return jsonify({
            "message": "Frontend no construido. Ejecuta `npm run build` dentro de /frontend.",
            "frontend_dev_url": os.getenv("FRONTEND_URL", "http://localhost:5173"),
        }), 404

    @app.get("/frontend/<path:filename>")
    def frontend_assets(filename: str):
        if FRONTEND_DIR.exists():
            return send_from_directory(FRONTEND_DIR, filename)
        return jsonify({"error": True, "detail": "Frontend no construido"}), 404

    return app
