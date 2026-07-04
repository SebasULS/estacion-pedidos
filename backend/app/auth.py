from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import requests
from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.db import fetch_one, transaction
from app.errors import ApiError
from app.nosql_logger import log_event

DEFAULT_SCOPE = "openid email profile"


def _realm_base() -> str:
    server = (current_app.config.get("KEYCLOAK_SERVER_URL") or "").rstrip("/")
    realm = current_app.config.get("KEYCLOAK_REALM") or "estacion-pedidos"
    return f"{server}/realms/{realm}"


def keycloak_auth_url() -> str:
    return f"{_realm_base()}/protocol/openid-connect/auth"


def keycloak_token_url() -> str:
    return f"{_realm_base()}/protocol/openid-connect/token"


def keycloak_userinfo_url() -> str:
    return f"{_realm_base()}/protocol/openid-connect/userinfo"


def keycloak_logout_url() -> str:
    return f"{_realm_base()}/protocol/openid-connect/logout"


def keycloak_certs_url() -> str:
    return f"{_realm_base()}/protocol/openid-connect/certs"


@dataclass(frozen=True)
class KeycloakOAuthSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = DEFAULT_SCOPE
    server_url: str = ""
    realm: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sqlite_datetime(value: datetime) -> str:
    """Formato compatible con TIMESTAMPTZ de PostgreSQL."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")


def get_serializer() -> URLSafeTimedSerializer:
    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        raise ApiError(500, "SECRET_KEY no configurado")
    return URLSafeTimedSerializer(secret_key=secret, salt="estacion-pedidos-api-token")


def generate_pkce_pair() -> tuple[str, str]:
    """Genera code_verifier y code_challenge para OAuth 2.0 PKCE S256."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def create_access_token(user: dict[str, Any], provider: str = "local", keycloak_access_token: str | None = None) -> str:
    """Crea un Bearer token local y registra su sesión en la BD.

    El access_token de Keycloak no se expone al frontend. Se guarda asociado
    al jti local para poder revocarlo al cerrar sesión.
    """
    expires_seconds = int(current_app.config.get("ACCESS_TOKEN_EXPIRES_SECONDS", 86400))
    now = utc_now()
    expires_at = now + timedelta(seconds=expires_seconds)
    jti = secrets.token_urlsafe(32)
    payload = {
        "id_usuario": user["id_usuario"],
        "email": user["email"],
        "nombre": user.get("nombre"),
        "id_rol": user.get("id_rol"),
        "provider": provider,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = get_serializer().dumps(payload)
    with transaction() as conn:
        with conn.cursor() if hasattr(conn, "cursor") else _null_ctx(conn) as cur:
            cur.execute(
                """
                INSERT INTO sesiones_api
                (id_usuario, jti, proveedor, keycloak_access_token, creado_en, expira_en)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user["id_usuario"],
                    jti,
                    provider,
                    keycloak_access_token if provider == "keycloak" else None,
                    sqlite_datetime(now),
                    sqlite_datetime(expires_at),
                ),
            )
    return token


class _null_ctx:
    """Helper para SQLite (sin .cursor())."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


def _exec_on_conn(conn, sql: str, params: tuple):
    """Ejecuta SQL en una conexión PostgreSQL o SQLite de forma uniforme."""
    if hasattr(conn, "cursor"):
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur
    return conn.execute(sql, params or ())


def _fetchone_on_conn(conn, sql: str, params: tuple):
    cur = _exec_on_conn(conn, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row, getattr(cur, "description", None))


def _fetchall_on_conn(conn, sql: str, params: tuple):
    cur = _exec_on_conn(conn, sql, params)
    rows = cur.fetchall()
    description = getattr(cur, "description", None)
    return [_row_to_dict(row, description) for row in rows]


def _row_to_dict(row, description) -> dict:
    """Convierte una fila (sqlite3.Row, _PgRow, tuple psycopg2, o dict) a dict."""
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return dict(zip(row.keys(), list(row)))
    # psycopg2 devuelve tuplas planas; usar description para los nombres.
    if isinstance(row, (tuple, list)) and description:
        colnames = [d[0] for d in description]
        return dict(zip(colnames, row))
    return dict(row)


def decode_access_token(token: str) -> dict[str, Any]:
    max_age = int(current_app.config.get("ACCESS_TOKEN_EXPIRES_SECONDS", 86400))
    try:
        data = get_serializer().loads(token, max_age=max_age)
    except SignatureExpired as exc:
        raise ApiError(401, "Token expirado") from exc
    except BadSignature as exc:
        raise ApiError(401, "Token inválido") from exc
    if not data.get("jti"):
        raise ApiError(401, "Token sin identificador de sesión")
    return data


def get_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def get_current_user(required: bool = True) -> dict[str, Any] | None:
    token = get_bearer_token()
    if not token:
        if required:
            raise ApiError(401, "Token Bearer requerido")
        return None
    claims = decode_access_token(token)

    active_session = fetch_one(
        """
        SELECT id_sesion, id_usuario, jti, proveedor, expira_en, cerrado_en
        FROM sesiones_api
        WHERE jti = %s
          AND cerrado_en IS NULL
          AND expira_en > NOW()
        """,
        (claims["jti"],),
    )
    if not active_session:
        raise ApiError(401, "Sesión expirada o cerrada")

    user = fetch_one(
        """
        SELECT u.id_usuario, u.nombre, u.email, u.id_rol, u.activo, u.creado_en,
               oc.avatar_url, oc.proveedor
        FROM usuarios u
        LEFT JOIN oauth_cuentas oc ON oc.id_usuario = u.id_usuario AND oc.proveedor = 'keycloak'
        WHERE u.id_usuario = %s
        """,
        (claims["id_usuario"],),
    )
    if not user or int(user.get("activo", 0)) != 1:
        raise ApiError(401, "Usuario no autorizado o inactivo")
    g.current_user = user
    g.token_claims = claims
    g.api_session = active_session
    return user


def token_required(view: Callable[..., Any]) -> Callable[..., Any]:
    from functools import wraps

    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        get_current_user(required=True)
        return view(*args, **kwargs)

    return wrapper


def get_keycloak_settings() -> KeycloakOAuthSettings:
    client_id = current_app.config.get("KEYCLOAK_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID")
    client_secret = current_app.config.get("KEYCLOAK_CLIENT_SECRET") or os.getenv("KEYCLOAK_CLIENT_SECRET")
    redirect_uri = current_app.config.get("KEYCLOAK_REDIRECT_URI") or os.getenv("KEYCLOAK_REDIRECT_URI")
    scope = current_app.config.get("KEYCLOAK_SCOPE") or os.getenv("KEYCLOAK_SCOPE", DEFAULT_SCOPE)
    server_url = current_app.config.get("KEYCLOAK_SERVER_URL") or os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
    realm = current_app.config.get("KEYCLOAK_REALM") or os.getenv("KEYCLOAK_REALM", "estacion-pedidos")
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/api/auth/oauth/keycloak/callback"
    if not client_id:
        raise ApiError(
            503,
            "OAuth Keycloak no configurado. Define KEYCLOAK_CLIENT_ID (y preferentemente KEYCLOAK_CLIENT_SECRET) en variables de entorno.",
        )
    return KeycloakOAuthSettings(
        client_id=client_id,
        client_secret=client_secret or "",
        redirect_uri=redirect_uri,
        scope=scope,
        server_url=server_url,
        realm=realm,
    )


def build_keycloak_authorization_url(
    state: str,
    settings: KeycloakOAuthSettings,
    code_challenge: str,
    prompt: str | None = None,
) -> str:
    params = {
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "response_type": "code",
        "scope": settings.scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if prompt:
        params["prompt"] = prompt
    return f"{keycloak_auth_url()}?{urlencode(params)}"


def exchange_keycloak_code(code: str, redirect_uri: str | None = None, code_verifier: str | None = None) -> dict[str, Any]:
    settings = get_keycloak_settings()
    data = {
        "code": code,
        "client_id": settings.client_id,
        "redirect_uri": redirect_uri or settings.redirect_uri,
        "grant_type": "authorization_code",
    }
    # Keycloak admite clientes públicos (sin secret) y confidenciales (con secret).
    if settings.client_secret:
        data["client_secret"] = settings.client_secret
    if code_verifier:
        data["code_verifier"] = code_verifier
    try:
        response = requests.post(keycloak_token_url(), data=data, timeout=12)
    except requests.RequestException as exc:
        raise ApiError(502, f"No se pudo conectar con Keycloak OAuth: {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(response.status_code, f"Keycloak rechazó el intercambio del código OAuth: {response.text}")
    return response.json()


def fetch_keycloak_userinfo(access_token: str) -> dict[str, Any]:
    """Valida el access_token consultando el endpoint userinfo de Keycloak."""
    try:
        response = requests.get(
            keycloak_userinfo_url(),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise ApiError(502, f"No se pudo validar el token con Keycloak: {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(401, f"Token inválido o rechazado por Keycloak: {response.text}")
    return response.json()


def verify_keycloak_id_token(id_token: str) -> dict[str, Any]:
    """Valida un id_token de Keycloak.

    Para producción se debería validar la firma JWKS. Aquí usamos el endpoint
    userinfo cuando hay un access_token, o un fallback a la validación contra
    el client_id para mantener compatibilidad con el flujo API.
    """
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            raise ApiError(401, "id_token mal formado")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ApiError(401, f"id_token inválido: {exc}") from exc

    settings = get_keycloak_settings()
    # aud puede venir como string o lista.
    aud = payload.get("aud")
    if isinstance(aud, list):
        if settings.client_id not in aud:
            raise ApiError(401, "El id_token no pertenece al client_id configurado")
    elif aud != settings.client_id:
        raise ApiError(401, "El id_token no pertenece al client_id configurado")

    # Verificación de expiración.
    exp = payload.get("exp")
    if exp and int(exp) < int(utc_now().timestamp()):
        raise ApiError(401, "id_token expirado")
    return payload


def normalize_keycloak_profile(userinfo: dict[str, Any]) -> dict[str, Any]:
    """Normaliza el userinfo de Keycloak al perfil interno."""
    sub = userinfo.get("sub")
    email = userinfo.get("email") or userinfo.get("preferred_username")
    if not email or not sub:
        raise ApiError(401, "El perfil Keycloak no contiene sub ni email/preferred_username")
    nombre = (
        userinfo.get("name")
        or " ".join(filter(None, [userinfo.get("given_name"), userinfo.get("family_name")]))
        or userinfo.get("preferred_username")
        or email
    )
    return {
        "proveedor": "keycloak",
        "proveedor_user_id": str(sub),
        "email": str(email).lower(),
        "nombre": nombre,
        "avatar_url": userinfo.get("picture"),
    }


def get_default_role_id(conn) -> int:
    configured = current_app.config.get("OAUTH_DEFAULT_ROLE_ID") or os.getenv("OAUTH_DEFAULT_ROLE_ID")
    if configured:
        return int(configured)
    row = _fetchone_on_conn(conn, "SELECT id_rol FROM roles WHERE nombre = 'Mozo'")
    if row:
        return int(row["id_rol"])
    _exec_on_conn(
        conn,
        "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (2, 'Mozo', 'Registra pedidos y consulta historial') ON CONFLICT (id_rol) DO NOTHING",
        (),
    )
    return 2


def upsert_oauth_user(profile: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza usuario local a partir del perfil OAuth validado."""
    proveedor = profile["proveedor"]
    proveedor_user_id = profile["proveedor_user_id"]
    email = profile["email"]
    nombre = profile["nombre"]
    avatar_url = profile.get("avatar_url")

    with transaction() as conn:
        oauth_row = _fetchone_on_conn(
            conn,
            """
            SELECT oc.id_usuario
            FROM oauth_cuentas oc
            WHERE oc.proveedor = %s AND oc.proveedor_user_id = %s
            """,
            (proveedor, proveedor_user_id),
        )

        if oauth_row:
            id_usuario = int(oauth_row["id_usuario"])
            _exec_on_conn(
                conn,
                "UPDATE usuarios SET nombre = %s, email = %s, activo = 1 WHERE id_usuario = %s",
                (nombre, email, id_usuario),
            )
            _exec_on_conn(
                conn,
                """
                UPDATE oauth_cuentas
                SET email = %s, nombre = %s, avatar_url = %s, ultimo_login = NOW()
                WHERE proveedor = %s AND proveedor_user_id = %s
                """,
                (email, nombre, avatar_url, proveedor, proveedor_user_id),
            )
        else:
            existing_user = _fetchone_on_conn(
                conn, "SELECT id_usuario FROM usuarios WHERE email = %s", (email,)
            )
            if existing_user:
                id_usuario = int(existing_user["id_usuario"])
                _exec_on_conn(
                    conn,
                    "UPDATE usuarios SET nombre = %s, activo = 1 WHERE id_usuario = %s",
                    (nombre, id_usuario),
                )
            else:
                default_role = get_default_role_id(conn)
                cur = _exec_on_conn(
                    conn,
                    """
                    INSERT INTO usuarios (nombre, email, password_hash, id_rol, activo)
                    VALUES (%s, %s, %s, %s, 1)
                    RETURNING id_usuario
                    """,
                    (nombre, email, "OAUTH_KEYCLOAK_NO_PASSWORD", default_role),
                )
                row = cur.fetchone()
                # PostgreSQL: RETURNING. SQLite fallback: lastrowid.
                if row is not None:
                    id_usuario = int(row[0] if isinstance(row, (tuple, list)) else row["id_usuario"])
                else:
                    id_usuario = int(cur.lastrowid)

            _exec_on_conn(
                conn,
                """
                INSERT INTO oauth_cuentas
                (id_usuario, proveedor, proveedor_user_id, email, nombre, avatar_url, ultimo_login)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (id_usuario, proveedor, proveedor_user_id, email, nombre, avatar_url),
            )

        user = _fetchone_on_conn(
            conn,
            """
            SELECT u.id_usuario, u.nombre, u.email, u.id_rol, u.activo, u.creado_en,
                   oc.avatar_url, oc.proveedor
            FROM usuarios u
            LEFT JOIN oauth_cuentas oc ON oc.id_usuario = u.id_usuario AND oc.proveedor = 'keycloak'
            WHERE u.id_usuario = %s
            """,
            (id_usuario,),
        )

    log_event("INFO", "OAUTH_LOGIN", "usuarios", "Inicio de sesión OAuth exitoso", {
        "id_usuario": user["id_usuario"],
        "email": user["email"],
        "proveedor": proveedor,
    })
    return user


def make_auth_response(user: dict[str, Any], provider: str = "keycloak", keycloak_access_token: str | None = None) -> dict[str, Any]:
    return {
        "token_type": "Bearer",
        "access_token": create_access_token(user, provider=provider, keycloak_access_token=keycloak_access_token),
        "expires_in": int(current_app.config.get("ACCESS_TOKEN_EXPIRES_SECONDS", 86400)),
        "user": user,
    }


def revoke_keycloak_token(access_token: str) -> dict[str, Any]:
    """Revoca el access_token en Keycloak. Si falla, no bloquea el logout local."""
    settings = get_keycloak_settings()
    data = {
        "token": access_token,
        "client_id": settings.client_id,
    }
    if settings.client_secret:
        data["client_secret"] = settings.client_secret
    try:
        response = requests.post(
            keycloak_logout_url(),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=8,
        )
        return {
            "revoked": response.status_code in (200, 204, 400),
            "status_code": response.status_code,
            "detail": response.text[:300],
        }
    except requests.RequestException as exc:
        return {"revoked": False, "status_code": None, "detail": str(exc)}


def close_current_session() -> dict[str, Any]:
    """Cierra el token Bearer actual y revoca Keycloak cuando existe token de proveedor."""
    token = get_bearer_token()
    if not token:
        return {"logout": True, "local_session_closed": False, "keycloak_revoked": False}

    claims = decode_access_token(token)
    jti = claims["jti"]
    session_row = fetch_one(
        "SELECT id_sesion, proveedor, keycloak_access_token FROM sesiones_api WHERE jti = %s",
        (jti,),
    )
    if not session_row:
        return {"logout": True, "local_session_closed": False, "keycloak_revoked": False}

    keycloak_result = {"revoked": False}
    keycloak_access_token = session_row.get("keycloak_access_token")
    if session_row.get("proveedor") == "keycloak" and keycloak_access_token:
        keycloak_result = revoke_keycloak_token(keycloak_access_token)

    with transaction() as conn:
        _exec_on_conn(
            conn,
            "UPDATE sesiones_api SET cerrado_en = NOW() WHERE jti = %s AND cerrado_en IS NULL",
            (jti,),
        )

    log_event(
        "INFO",
        "OAUTH_LOGOUT",
        "sesiones_api",
        "Cierre de sesión OAuth/API",
        {
            "id_usuario": claims.get("id_usuario"),
            "provider": claims.get("provider"),
            "keycloak_revoked": keycloak_result.get("revoked"),
        },
    )
    return {
        "logout": True,
        "local_session_closed": True,
        "keycloak_revoked": bool(keycloak_result.get("revoked")),
        "keycloak_revoke_detail": keycloak_result,
    }


def create_demo_token() -> dict[str, Any]:
    if not current_app.config.get("ALLOW_DEMO_AUTH", True):
        raise ApiError(403, "Login demo deshabilitado")
    with transaction() as conn:
        _exec_on_conn(
            conn,
            "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (1, 'Administrador', 'Acceso total al sistema') ON CONFLICT (id_rol) DO NOTHING",
            (),
        )
        _exec_on_conn(
            conn,
            """
            INSERT INTO usuarios (id_usuario, nombre, email, password_hash, id_rol, activo)
            VALUES (1, 'Administrador Demo', 'admin@estacion.local', 'demo_hash_no_productivo', 1, 1)
            ON CONFLICT (id_usuario) DO NOTHING
            """,
            (),
        )
        user = _fetchone_on_conn(
            conn,
            "SELECT id_usuario, nombre, email, id_rol, activo, creado_en FROM usuarios WHERE id_usuario = 1",
            (),
        )
    log_event("INFO", "DEMO_LOGIN", "usuarios", "Token demo generado para pruebas API", {"id_usuario": user["id_usuario"]})
    return make_auth_response(user, provider="demo")
