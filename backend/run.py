"""Punto de entrada local para el backend Flask.

Uso:
    cd backend
    python -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # editar con datos de Supabase + Keycloak
    python run.py

En producción (Vercel) no se usa este archivo: Vercel invoca
`app.api.create_app()` a través de `api/index.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def ensure_local_data_dir() -> None:
    """Garantiza que exista la carpeta data/ para logs JSONL en desarrollo."""
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_local_data_dir()
    from app import create_app

    app = create_app()
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "true").lower() == "true")
else:
    # Permite `gunicorn run:app` y `vercel dev`.
    from app import create_app

    app = create_app()
