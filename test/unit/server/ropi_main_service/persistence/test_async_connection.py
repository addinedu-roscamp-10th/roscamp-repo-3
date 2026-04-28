import asyncio

import pytest

from server.ropi_main_service.persistence import async_connection


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, params=None):
        self.connection.executed.append((query, params))

    async def fetchone(self):
        return {"ok": 1}

    async def fetchall(self):
        return [{"ok": 1}]


class FakeConnection:
    def __init__(self):
        self.executed = []

    def cursor(self):
        return FakeCursor(self)


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()
        self.closed = False
        self.waited = False

    def acquire(self):
        return FakeAcquire(self.connection)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


@pytest.fixture(autouse=True)
def reset_pool():
    asyncio.run(async_connection.close_pool())
    yield
    asyncio.run(async_connection.close_pool())


def test_async_fetch_one_uses_cached_aiomysql_pool(monkeypatch):
    created_kwargs = []
    fake_pool = FakePool()

    async def fake_create_pool(**kwargs):
        created_kwargs.append(kwargs)
        return fake_pool

    monkeypatch.setattr(async_connection.aiomysql, "create_pool", fake_create_pool)
    monkeypatch.setattr(
        async_connection,
        "get_db_config",
        lambda: {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "user",
            "password": "pw",
            "database": "care_service",
            "charset": "utf8mb4",
            "connect_timeout": 3,
            "read_timeout": 3,
            "write_timeout": 3,
        },
    )

    async def scenario():
        first = await async_connection.async_fetch_one("SELECT 1 AS ok", ("param",))
        second = await async_connection.async_fetch_all("SELECT 1 AS ok")
        return first, second

    first, second = asyncio.run(scenario())

    assert first == {"ok": 1}
    assert second == [{"ok": 1}]
    assert len(created_kwargs) == 1
    assert created_kwargs[0]["db"] == "care_service"
    assert fake_pool.connection.executed == [
        ("SELECT 1 AS ok", ("param",)),
        ("SELECT 1 AS ok", None),
    ]


def test_async_fetch_rejects_write_query():
    async def scenario():
        await async_connection.async_fetch_one("UPDATE item SET quantity = 1")

    with pytest.raises(ValueError):
        asyncio.run(scenario())


def test_close_pool_closes_cached_pool(monkeypatch):
    fake_pool = FakePool()

    async def fake_create_pool(**kwargs):
        return fake_pool

    monkeypatch.setattr(async_connection.aiomysql, "create_pool", fake_create_pool)

    async def scenario():
        await async_connection.get_pool()
        await async_connection.close_pool()

    asyncio.run(scenario())

    assert fake_pool.closed is True
    assert fake_pool.waited is True
