import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = BASE_DIR / "data" / "logs_nosql.jsonl"


def get_log_path() -> Path:
    configured = None
    try:
        configured = current_app.config.get("LOG_PATH")
    except RuntimeError:
        configured = os.getenv("LOG_PATH")
    path = Path(configured) if configured else DEFAULT_LOG_PATH
    if not path.is_absolute():
        path = BASE_DIR / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # En serverless la carpeta puede ser de solo lectura: usamos /tmp.
        tmp_path = Path("/tmp") / path.name
        return tmp_path
    return path


def log_event(level: str, action: str, entity: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    document = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "action": action,
        "entity": entity,
        "message": message,
        "payload": payload or {},
    }
    try:
        path = get_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(document, ensure_ascii=False, default=str) + "\n")
    except OSError:
        # Si el FS es de solo lectura (Vercel), solo registramos en memoria
        # del proceso (efímero) para no romper el flujo.
        pass
    return document


def read_logs(limit: int = 100) -> list[dict[str, Any]]:
    path = get_log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    documents = []
    for line in lines:
        try:
            documents.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(documents))
