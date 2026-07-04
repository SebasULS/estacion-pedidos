from flask import Blueprint, jsonify, request

from app.nosql_logger import log_event, read_logs

logs_bp = Blueprint("logs", __name__, url_prefix="/api/logs")


@logs_bp.get("")
def get_logs():
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify({"tipo": "NoSQL JSONL", "total_mostrado": limit, "data": read_logs(limit)})


@logs_bp.post("")
def create_log():
    payload = request.get_json(silent=True) or {}
    doc = log_event(
        payload.get("level", "INFO"),
        payload.get("action", "MANUAL_LOG"),
        payload.get("entity", "sistema"),
        payload.get("message", "Registro manual"),
        payload.get("payload", {}),
    )
    return jsonify(doc), 201
