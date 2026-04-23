import pymysql
from pymysql.connections import Connection

from server.ropi_db.config.db_config import DB_CONFIG


def get_connection() -> Connection:
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        autocommit=True,
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _validate_select_query(query: str) -> str:
    normalized = " ".join(query.strip().split())

    if not normalized:
        raise ValueError("SQL query is empty.")

    if not normalized.upper().startswith(("SELECT", "SHOW", "DESCRIBE", "EXPLAIN")):
        raise ValueError("Read-only mode only allows SELECT-like queries.")

    return query


def fetch_one(query: str, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            validated_query = _validate_select_query(query)
            if params is None:
                cursor.execute(validated_query)
            else:
                cursor.execute(validated_query, params)
            return cursor.fetchone()
    finally:
        conn.close()


def fetch_all(query: str, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            validated_query = _validate_select_query(query)
            if params is None:
                cursor.execute(validated_query)
            else:
                cursor.execute(validated_query, params)
            return cursor.fetchall()
    finally:
        conn.close()


def test_connection():
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            return True, cursor.fetchone()
    except Exception as exc:
        return False, str(exc)
    finally:
        if conn:
            conn.close()


__all__ = ["fetch_all", "fetch_one", "get_connection", "test_connection"]
