from contextlib import asynccontextmanager

import aiomysql

from server.ropi_main_service.persistence.config import get_db_config
from server.ropi_main_service.persistence.connection import _validate_select_query


_pool = None


async def get_pool():
    global _pool

    if _pool is not None:
        return _pool

    db_config = get_db_config()
    _pool = await aiomysql.create_pool(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        db=db_config["database"],
        charset=db_config["charset"],
        autocommit=True,
        connect_timeout=db_config["connect_timeout"],
        cursorclass=aiomysql.DictCursor,
    )
    return _pool


async def close_pool():
    global _pool

    if _pool is None:
        return

    pool = _pool
    _pool = None
    pool.close()
    await pool.wait_closed()


async def async_fetch_one(query: str, params=None):
    validated_query = _validate_select_query(query)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(validated_query, params)
            return await cursor.fetchone()


async def async_fetch_all(query: str, params=None):
    validated_query = _validate_select_query(query)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(validated_query, params)
            return await cursor.fetchall()


async def async_execute(query: str, params=None):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            return cursor.rowcount


async def async_execute_many(query: str, params_seq):
    params_seq = list(params_seq or [])
    if not params_seq:
        return 0

    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(query, params_seq)
            return cursor.rowcount


@asynccontextmanager
async def async_transaction():
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cursor:
                yield cursor
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def async_test_connection():
    try:
        row = await async_fetch_one("SELECT 1 AS ok")
        return True, row
    except Exception as exc:
        return False, str(exc)


__all__ = [
    "async_execute",
    "async_execute_many",
    "async_fetch_all",
    "async_fetch_one",
    "async_test_connection",
    "async_transaction",
    "close_pool",
    "get_pool",
]
