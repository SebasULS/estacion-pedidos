"""Integración SUNAT / facturación electrónica mediante API REST.

La integración queda lista para trabajar con proveedores que entregan credenciales
basadas en ``personalId`` + ``personaToken``. Por seguridad, los secretos se leen
solo desde variables de entorno y nunca se guardan en el frontend.

Modo de operación:
- SUNAT_API_REAL=false: responde en modo desarrollo/simulación para exposición.
- SUNAT_API_REAL=true: envía el comprobante al endpoint configurado en SUNAT_API_BASE_URL.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from flask import current_app

from app.errors import ApiError
from app.nosql_logger import log_event


EMPRESAS_DEMO = {
    "20123456789": {
        "ruc": "20123456789",
        "razon_social": "Empresa Demo SAC",
        "direccion": "Av. Principal 123 - Lima",
        "estado": "ACTIVO",
        "condicion": "HABIDO",
    },
    "20698765432": {
        "ruc": "20698765432",
        "razon_social": "Comercial ABC EIRL",
        "direccion": "Jr. Comercio 456 - Arequipa",
        "estado": "ACTIVO",
        "condicion": "HABIDO",
    },
}

PERSONAS_DEMO = {
    "12345678": {
        "dni": "12345678",
        "nombres": "Juan",
        "apellido_paterno": "Perez",
        "apellido_materno": "Gomez",
    },
    "87654321": {
        "dni": "87654321",
        "nombres": "Maria",
        "apellido_paterno": "Lopez",
        "apellido_materno": "Torres",
    },
}

DOCUMENT_TYPES = {
    "factura": "01",
    "boleta": "03",
}

DOCUMENT_NAMES = {
    "01": "factura",
    "03": "boleta",
}


@dataclass(frozen=True)
class SunatSettings:
    api_base_url: str
    personal_id: str | None
    persona_token: str | None
    environment: str
    real_mode: bool
    emitir_path: str
    consultar_path: str
    anular_path: str
    serie_boleta: str
    serie_factura: str
    timeout_seconds: int

    @property
    def configured(self) -> bool:
        return bool(self.api_base_url and self.personal_id and self.persona_token)


def _config_value(name: str, default: str | None = None) -> str | None:
    try:
        return current_app.config.get(name) or os.getenv(name, default)
    except RuntimeError:
        return os.getenv(name, default)


def get_sunat_settings() -> SunatSettings:
    real_raw = str(_config_value("SUNAT_API_REAL", "false") or "false").lower()
    return SunatSettings(
        api_base_url=str(_config_value("SUNAT_API_BASE_URL", "https://api.sunat.example/desarrollo") or "").rstrip("/"),
        personal_id=_config_value("SUNAT_PERSONAL_ID"),
        persona_token=_config_value("SUNAT_PERSONA_TOKEN"),
        environment=str(_config_value("SUNAT_API_ENV", "DESARROLLO") or "DESARROLLO"),
        real_mode=real_raw in {"1", "true", "yes", "on"},
        emitir_path=str(_config_value("SUNAT_EMITIR_PATH", "/api/rest/documentos") or "/api/rest/documentos"),
        consultar_path=str(_config_value("SUNAT_CONSULTAR_PATH", "/api/rest/documentos/consultar") or "/api/rest/documentos/consultar"),
        anular_path=str(_config_value("SUNAT_ANULAR_PATH", "/api/rest/documentos/anular") or "/api/rest/documentos/anular"),
        serie_boleta=str(_config_value("SUNAT_SERIE_BOLETA", "B001") or "B001"),
        serie_factura=str(_config_value("SUNAT_SERIE_FACTURA", "F001") or "F001"),
        timeout_seconds=int(_config_value("SUNAT_TIMEOUT_SECONDS", "20") or "20"),
    )


def sunat_config_status() -> dict[str, Any]:
    settings = get_sunat_settings()
    return {
        "proveedor": "SUNAT / API REST compatible",
        "ambiente": settings.environment,
        "modo_real": settings.real_mode,
        "configurado": settings.configured,
        "endpoint_base_configurado": bool(settings.api_base_url),
        "personal_id_configurado": bool(settings.personal_id),
        "persona_token_configurado": bool(settings.persona_token),
        "serie_boleta": settings.serie_boleta,
        "serie_factura": settings.serie_factura,
        "nota": "El personalId y personaToken se configuran en .env. No se exponen sus valores por seguridad.",
    }


def _headers(settings: SunatSettings) -> dict[str, str]:
    if not settings.configured:
        raise ApiError(
            503,
            "API SUNAT no configurada. Define SUNAT_API_BASE_URL, SUNAT_PERSONAL_ID y SUNAT_PERSONA_TOKEN en .env.",
        )
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "personalId": settings.personal_id or "",
        "personaToken": settings.persona_token or "",
        "Authorization": f"Bearer {settings.persona_token}",
    }


def _url(settings: SunatSettings, path: str) -> str:
    return f"{settings.api_base_url}/{path.lstrip('/')}"


def normalize_tipo_comprobante(value: str | None) -> tuple[str, str]:
    raw = str(value or "boleta").strip().lower()
    if raw in {"01", "factura", "fact", "f"}:
        return "factura", "01"
    if raw in {"03", "boleta", "bol", "b"}:
        return "boleta", "03"
    raise ApiError(400, "tipo_comprobante no válido. Usa boleta, factura, 03 u 01.")


def _doc_number(settings: SunatSettings, tipo: str) -> tuple[str, str]:
    serie = settings.serie_factura if tipo == "factura" else settings.serie_boleta
    numero = str(random.randint(1, 999999)).zfill(6)
    return serie, numero


def _round2(value: Any) -> float:
    return round(float(value or 0), 2)


def build_sunat_payload(
    *,
    tipo_comprobante: str,
    cliente: dict[str, Any],
    items: list[dict[str, Any]],
    subtotal: float | None = None,
    igv: float | None = None,
    total: float | None = None,
    id_pedido: int | None = None,
    observacion: str | None = None,
) -> dict[str, Any]:
    tipo, codigo_tipo = normalize_tipo_comprobante(tipo_comprobante)
    settings = get_sunat_settings()
    serie, numero = _doc_number(settings, tipo)

    if not cliente:
        raise ApiError(400, "cliente es obligatorio para emitir comprobante SUNAT")
    if not items:
        raise ApiError(400, "items es obligatorio para emitir comprobante SUNAT")

    normalized_items: list[dict[str, Any]] = []
    calculated_subtotal = 0.0
    for item in items:
        descripcion = item.get("descripcion") or item.get("nombre") or item.get("producto")
        cantidad = _round2(item.get("cantidad"))
        precio_unitario = _round2(item.get("precio_unitario") or item.get("precio") or item.get("valor_unitario"))
        if not descripcion or cantidad <= 0:
            raise ApiError(400, "Cada item requiere descripcion/nombre y cantidad mayor a cero")
        valor_venta = _round2(item.get("subtotal") if item.get("subtotal") is not None else cantidad * precio_unitario)
        calculated_subtotal = _round2(calculated_subtotal + valor_venta)
        normalized_items.append({
            "codigo": item.get("codigo") or item.get("id_producto") or "SERV",
            "descripcion": descripcion,
            "cantidad": cantidad,
            "unidad_medida": item.get("unidad_medida") or "NIU",
            "valor_unitario": precio_unitario,
            "precio_unitario": precio_unitario,
            "valor_venta": valor_venta,
            "igv": _round2(item.get("igv") or 0),
        })

    subtotal_value = _round2(subtotal if subtotal is not None else calculated_subtotal)
    igv_value = _round2(igv if igv is not None else 0)
    total_value = _round2(total if total is not None else subtotal_value + igv_value)

    return {
        "ambiente": settings.environment,
        "tipo_comprobante": codigo_tipo,
        "tipo_comprobante_nombre": tipo,
        "serie": serie,
        "numero": numero,
        "fecha_emision": datetime.now(timezone.utc).date().isoformat(),
        "hora_emision": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "moneda": "PEN",
        "id_pedido": id_pedido,
        "cliente": {
            "tipo_documento": cliente.get("tipo_documento") or cliente.get("tipoDoc") or ("6" if tipo == "factura" else "1"),
            "numero_documento": cliente.get("numero_documento") or cliente.get("documento") or cliente.get("ruc") or cliente.get("dni"),
            "nombre": cliente.get("nombre") or cliente.get("razon_social") or cliente.get("nombres") or "Cliente varios",
            "direccion": cliente.get("direccion") or "-",
            "email": cliente.get("email"),
        },
        "items": normalized_items,
        "totales": {
            "subtotal": subtotal_value,
            "igv": igv_value,
            "descuento": 0,
            "total": total_value,
        },
        "observacion": observacion or "Emitido desde Estación de Pedidos",
    }


def _simulated_response(payload: dict[str, Any], action: str = "emitir") -> dict[str, Any]:
    if action == "anular":
        estado = "ANULADO_SIMULADO"
        mensaje = "Comprobante anulado en modo desarrollo."
    elif action == "consultar":
        estado = "ACEPTADO_SIMULADO"
        mensaje = "Comprobante consultado en modo desarrollo."
    else:
        estado = "ACEPTADO_SIMULADO"
        mensaje = "Comprobante aceptado en modo desarrollo. Configure SUNAT_API_REAL=true para consumir la API externa."
    return {
        "success": True,
        "simulado": True,
        "estado_sunat": estado,
        "codigo_sunat": "0",
        "mensaje_sunat": mensaje,
        "external_id": f"SIM-{payload.get('serie', 'S')}-{payload.get('numero', random.randint(1, 999999))}",
        "pdf_url": None,
        "xml_url": None,
        "cdr_url": None,
        "respuesta_original": {
            "ambiente": payload.get("ambiente"),
            "tipo_comprobante": payload.get("tipo_comprobante"),
            "serie": payload.get("serie"),
            "numero": payload.get("numero"),
            "total": (payload.get("totales") or {}).get("total"),
        },
    }


def _post_external(path: str, payload: dict[str, Any], action: str) -> dict[str, Any]:
    settings = get_sunat_settings()
    if not settings.real_mode:
        return _simulated_response(payload, action=action)

    try:
        response = requests.post(
            _url(settings, path),
            headers=_headers(settings),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=settings.timeout_seconds,
        )
    except requests.RequestException as exc:
        log_event("ERROR", "SUNAT_API_CONNECTION_ERROR", "comprobantes_electronicos", "No se pudo conectar con API SUNAT", {"error": str(exc)})
        raise ApiError(502, f"No se pudo conectar con la API SUNAT: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code >= 400:
        log_event("ERROR", "SUNAT_API_ERROR", "comprobantes_electronicos", "API SUNAT rechazó la solicitud", {"status": response.status_code, "body": body})
        raise ApiError(response.status_code, f"API SUNAT rechazó la solicitud: {body}")

    return normalize_api_response(body)


def normalize_api_response(body: dict[str, Any]) -> dict[str, Any]:
    """Normaliza respuestas de proveedores distintos a un formato único interno."""
    success = body.get("success")
    if success is None:
        success = body.get("estado") in {"ACEPTADO", "ACEPTADO_SIMULADO", "ENVIADO"} or body.get("codigo") in {"0", 0}
    return {
        "success": bool(success),
        "simulado": False,
        "estado_sunat": body.get("estado_sunat") or body.get("estado") or body.get("status") or "ENVIADO",
        "codigo_sunat": str(body.get("codigo_sunat") or body.get("codigo") or body.get("sunatCode") or "0"),
        "mensaje_sunat": body.get("mensaje_sunat") or body.get("mensaje") or body.get("description") or "Respuesta recibida de API SUNAT",
        "external_id": body.get("external_id") or body.get("id") or body.get("documento_id") or body.get("hash"),
        "pdf_url": body.get("pdf_url") or body.get("pdf") or body.get("enlace_pdf"),
        "xml_url": body.get("xml_url") or body.get("xml") or body.get("enlace_xml"),
        "cdr_url": body.get("cdr_url") or body.get("cdr") or body.get("enlace_cdr"),
        "respuesta_original": body,
    }


class SunatAPI:
    """Fachada usada por las rutas Flask."""

    @staticmethod
    def configuracion() -> dict[str, Any]:
        return sunat_config_status()

    @staticmethod
    def consultar_ruc(ruc: str) -> dict[str, Any]:
        if ruc in EMPRESAS_DEMO:
            return {"success": True, "simulado": True, "data": EMPRESAS_DEMO[ruc]}
        return {"success": False, "simulado": True, "message": "RUC no encontrado en datos demo"}

    @staticmethod
    def consultar_dni(dni: str) -> dict[str, Any]:
        if dni in PERSONAS_DEMO:
            return {"success": True, "simulado": True, "data": PERSONAS_DEMO[dni]}
        return {"success": False, "simulado": True, "message": "DNI no encontrado en datos demo"}

    @staticmethod
    def emitir(payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_sunat_settings()
        log_event("INFO", "SUNAT_EMIT_REQUEST", "comprobantes_electronicos", "Solicitud de emisión SUNAT", {
            "modo_real": settings.real_mode,
            "ambiente": settings.environment,
            "tipo": payload.get("tipo_comprobante_nombre"),
            "serie": payload.get("serie"),
            "numero": payload.get("numero"),
        })
        return _post_external(settings.emitir_path, payload, action="emitir")

    @staticmethod
    def consultar_comprobante(payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_sunat_settings()
        return _post_external(settings.consultar_path, payload, action="consultar")

    @staticmethod
    def anular_comprobante(payload: dict[str, Any]) -> dict[str, Any]:
        settings = get_sunat_settings()
        return _post_external(settings.anular_path, payload, action="anular")

    @staticmethod
    def emitir_boleta(cliente: dict[str, Any], items: list[dict[str, Any]], total: float) -> dict[str, Any]:
        payload = build_sunat_payload(tipo_comprobante="boleta", cliente=cliente, items=items, total=total)
        return SunatAPI.emitir(payload)

    @staticmethod
    def emitir_factura(cliente: dict[str, Any], items: list[dict[str, Any]], total: float) -> dict[str, Any]:
        payload = build_sunat_payload(tipo_comprobante="factura", cliente=cliente, items=items, total=total)
        return SunatAPI.emitir(payload)
