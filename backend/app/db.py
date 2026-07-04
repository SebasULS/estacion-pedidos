from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from flask import current_app

from app.errors import ApiError

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


# ------------------------------------------------------------------
# Pool de conexiones PostgreSQL (Supabase)
# ------------------------------------------------------------------
_pg_pool = None


def _normalize_db_url(url: str) -> str:
    """psycopg2 acepta postgresql:// pero Supabase a veces entrega postgres://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    try:
        from psycopg2 import pool as pg_pool
    except ImportError as exc:
        raise RuntimeError(
            "psycopg2 no está instalado. Ejecuta: pip install psycopg2-binary"
        ) from exc
    db_url = os.getenv("DATABASE_URL") or (current_app.config.get("DATABASE_URL") if current_app else None)
    if not db_url:
        raise ApiError(
            503,
            "DATABASE_URL (Supabase PostgreSQL) no configurada. "
            "Copia backend/.env.example a .env y completa DATABASE_URL. "
            "Ver docs/GUIA_SUPABASE.md.",
        )
    db_url = _normalize_db_url(db_url)
    _pg_pool = pg_pool.ThreadedConnectionPool(1, 8, db_url)
    return _pg_pool


def _close_pg_pool() -> None:
    global _pg_pool
    if _pg_pool is not None:
        try:
            _pg_pool.closeall()
        except Exception:
            pass
        _pg_pool = None


class _PgRow:
    """Wrapper que emula sqlite3.Row (acceso por clave) sobre una tupla psycopg2."""

    def __init__(self, row, colnames):
        self._row = row
        self._colnames = colnames

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._row[self._colnames.index(key)]
        return self._row[key]

    def keys(self):
        return list(self._colnames)

    def __iter__(self):
        return iter(self._row)

    def __len__(self):
        return len(self._row)


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------
def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, _PgRow):
        return dict(zip(row.keys(), list(row)))
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def rows_to_dicts(rows: list) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows]


def _get_pg_connection():
    pool = _get_pg_pool()
    return pool.getconn()


def _put_pg_connection(conn):
    pool = _get_pg_pool()
    pool.putconn(conn)


def get_connection():
    """Devuelve una conexión abierta PostgreSQL del pool."""
    return _get_pg_connection()


def init_db() -> None:
    """Crea las tablas si no existen (idempotente)."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = _get_pg_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
    finally:
        _put_pg_connection(conn)


def reset_db() -> None:
    """Aplica de nuevo el esquema (idempotente).

    Para un reset completo (DROP + CREATE) usa la consola de Supabase o
    ejecuta DROP TABLE manualmente.
    """
    init_db()


@contextmanager
def transaction():
    """Context manager que devuelve una conexión del pool y hace commit/rollback."""
    conn = _get_pg_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_pg_connection(conn)


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    conn = _get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            if row is None:
                return None
            colnames = [desc[0] for desc in cur.description]
            return row_to_dict(_PgRow(row, colnames))
    finally:
        _put_pg_connection(conn)


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = _get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            if not rows:
                return []
            colnames = [desc[0] for desc in cur.description]
            return [row_to_dict(_PgRow(r, colnames)) for r in rows]
    finally:
        _put_pg_connection(conn)
