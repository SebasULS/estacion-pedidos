from __future__ import annotations

import secrets
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, request, session

from app.auth import (
    build_keycloak_authorization_url,
    close_current_session,
    create_demo_token,
    exchange_keycloak_code,
    fetch_keycloak_userinfo,
    generate_pkce_pair,
    get_current_user,
    get_keycloak_settings,
    keycloak_auth_url,
    make_auth_response,
    normalize_keycloak_profile,
    token_required,
    upsert_oauth_user,
    verify_keycloak_id_token,
)
from app.errors import ApiError
from app.nosql_logger import log_event


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.get("/config")
def auth_config():
    """Devuelve estado de configuración OAuth sin exponer secretos."""
    configured = True
    try:
        settings = get_keycloak_settings()
        redirect_uri = settings.redirect_uri
        scope = settings.scope
        client_id = settings.client_id
    except ApiError:
        configured = False
        redirect_uri = "http://localhost:8000/api/auth/oauth/keycloak/callback"
        scope = "openid email profile"
        client_id = None
    return jsonify({
        "oauth_keycloak_configurado": configured,
        "provider": "keycloak",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "token_type": "Bearer",
        "login_web": "/api/auth/oauth/keycloak/login",
        "login_api": "/api/auth/oauth/keycloak/login?mode=api",
        "callback": "/api/auth/oauth/keycloak/callback",
        "id_token_api": "/api/auth/oauth/keycloak/id-token",
        "logout": "/api/auth/logout",
        "me": "/api/auth/me",
        "seguridad": [
            "Authorization Code Flow",
            "PKCE S256",
            "state CSRF",
            "userinfo validado contra Keycloak",
            "logout local con revocación Keycloak cuando aplica",
        ],
    })


@auth_bp.get("/oauth/keycloak/login")
def keycloak_login():
    """Inicia OAuth 2.0 con Keycloak.

    Flujo web:
      GET /api/auth/oauth/keycloak/login?next=/
      Redirige a Keycloak y vuelve al callback configurado.

    Flujo API/Postman:
      GET /api/auth/oauth/keycloak/login?mode=api
      Devuelve authorization_url, state y code_verifier para completar el intercambio.
    """
    settings = get_keycloak_settings()
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    session["oauth_keycloak_state"] = state
    session["oauth_keycloak_code_verifier"] = code_verifier
    next_url = request.args.get("next") or "/"
    session["oauth_keycloak_next"] = next_url
    prompt = request.args.get("prompt")  # Keycloak admite "login", "consent", "none"
    authorization_url = build_keycloak_authorization_url(
        state=state,
        settings=settings,
        code_challenge=code_challenge,
        prompt=prompt,
    )

    mode = request.args.get("mode", "web")
    log_event("INFO", "OAUTH_START", "usuarios", "Inicio de flujo OAuth Keycloak", {"mode": mode})

    if mode == "api":
        return jsonify({
            "provider": "keycloak",
            "authorization_url": authorization_url,
            "state": state,
            "code_verifier": code_verifier,
            "code_challenge_method": "S256",
            "redirect_uri": settings.redirect_uri,
            "scope": settings.scope,
            "token_endpoint_local": "/api/auth/oauth/keycloak/token",
            "message": "Abre authorization_url, acepta permisos y usa el code junto con state y code_verifier en /api/auth/oauth/keycloak/token.",
        })
    return redirect(authorization_url)


def _validate_state(received_state: str | None):
    expected_state = session.get("oauth_keycloak_state")
    if not expected_state:
        raise ApiError(400, "State OAuth no encontrado en sesión. Inicia nuevamente desde /api/auth/oauth/keycloak/login")
    if received_state != expected_state:
        raise ApiError(400, "CSRF protection failed: el state no coincide con la sesión OAuth")


@auth_bp.get("/oauth/keycloak/callback")
def keycloak_callback():
    """Callback web configurado en Keycloak como 'Valid redirect URI'."""
    if request.args.get("error"):
        raise ApiError(401, f"Keycloak OAuth devolvió error: {request.args.get('error')}")

    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        raise ApiError(400, "Parámetro code obligatorio")
    _validate_state(state)

    code_verifier = session.get("oauth_keycloak_code_verifier")
    tokens = exchange_keycloak_code(code, code_verifier=code_verifier)
    access_token = tokens.get("access_token")
    if not access_token:
        raise ApiError(401, "Keycloak no devolvió access_token")

    userinfo = fetch_keycloak_userinfo(access_token)
    user = upsert_oauth_user(normalize_keycloak_profile(userinfo))
    auth_payload = make_auth_response(user, provider="keycloak", keycloak_access_token=access_token)

    wants_json = request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")
    session.pop("oauth_keycloak_state", None)
    session.pop("oauth_keycloak_code_verifier", None)
    next_url = session.pop("oauth_keycloak_next", None) or "/"

    if wants_json:
        return jsonify(auth_payload)

    fragment = urlencode({
        "access_token": auth_payload["access_token"],
        "token_type": auth_payload["token_type"],
        "auth": "ok",
    })
    return redirect(f"{next_url}#{fragment}")


@auth_bp.post("/oauth/keycloak/token")
def keycloak_token_api():
    """Intercambia authorization code por token local Bearer desde cliente API."""
    payload = request.get_json(silent=True) or {}
    code = payload.get("code")
    if not code:
        raise ApiError(400, "Campo code obligatorio")

    received_state = payload.get("state")
    expected_state = session.get("oauth_keycloak_state")
    if expected_state:
        _validate_state(received_state)
    elif not received_state:
        raise ApiError(400, "Campo state obligatorio para flujo API OAuth")

    code_verifier = session.get("oauth_keycloak_code_verifier") or payload.get("code_verifier")
    if not code_verifier:
        raise ApiError(400, "Campo code_verifier obligatorio para PKCE")

    tokens = exchange_keycloak_code(code, redirect_uri=payload.get("redirect_uri"), code_verifier=code_verifier)
    access_token = tokens.get("access_token")
    if not access_token:
        raise ApiError(401, "Keycloak no devolvió access_token")
    userinfo = fetch_keycloak_userinfo(access_token)
    user = upsert_oauth_user(normalize_keycloak_profile(userinfo))
    session.pop("oauth_keycloak_state", None)
    session.pop("oauth_keycloak_code_verifier", None)
    return jsonify(make_auth_response(user, provider="keycloak", keycloak_access_token=access_token))


@auth_bp.post("/oauth/keycloak/id-token")
def keycloak_id_token_api():
    """Valida un id_token de Keycloak y devuelve token local Bearer.

    Útil cuando el frontend usa el adaptador oficial keycloak-js y solo envía
    el id_token al backend.
    """
    payload = request.get_json(silent=True) or {}
    id_token = payload.get("id_token")
    if not id_token:
        raise ApiError(400, "Campo id_token obligatorio")
    token_info = verify_keycloak_id_token(id_token)
    # Normalizamos desde el payload decodificado del id_token.
    profile = {
        "proveedor": "keycloak",
        "proveedor_user_id": str(token_info.get("sub")),
        "email": (token_info.get("email") or token_info.get("preferred_username") or "").lower(),
        "nombre": (
            token_info.get("name")
            or " ".join(filter(None, [token_info.get("given_name"), token_info.get("family_name")]))
            or token_info.get("preferred_username")
            or token_info.get("email")
        ),
        "avatar_url": token_info.get("picture"),
    }
    if not profile["email"] or not profile["proveedor_user_id"]:
        raise ApiError(401, "id_token no contiene sub ni email/preferred_username")
    user = upsert_oauth_user(profile)
    return jsonify(make_auth_response(user, provider="keycloak"))


@auth_bp.post("/demo-login")
def demo_login():
    """Genera un token local para presentación offline o pruebas Postman."""
    return jsonify(create_demo_token())


@auth_bp.get("/me")
@token_required
def me():
    return jsonify({"authenticated": True, "user": get_current_user(required=True)})


@auth_bp.get("/protegido")
@token_required
def protected_example():
    user = get_current_user(required=True)
    return jsonify({
        "ok": True,
        "message": "Endpoint protegido accedido con Bearer token",
        "user": user,
    })


@auth_bp.post("/logout")
def logout():
    """Cierra sesión local y, si el login fue Keycloak, revoca el access_token del proveedor."""
    result = close_current_session()
    session.clear()
    return jsonify({
        **result,
        "message": "Sesión cerrada. El token Bearer local quedó invalidado; si existía token Keycloak, se intentó revocar.",
    })
