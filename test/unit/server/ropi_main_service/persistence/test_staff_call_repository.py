import asyncio
import json

from server.ropi_main_service.persistence.repositories import staff_call_repository


def test_staff_call_repository_links_visitor_to_member_event(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.lastrowid = 9102
            self._last_query = ""

        async def execute(self, query, params=None):
            self.calls.append((query, params))
            self._last_query = query

        async def fetchone(self):
            if "FROM idempotency_record" in self._last_query:
                return None
            if "FROM visitor" in self._last_query:
                return {
                    "visitor_id": 42,
                    "member_id": 1,
                    "visitor_name": "김민수",
                    "member_name": "김영수",
                    "room_no": "301",
                }
            return None

    class FakeTransaction:
        def __init__(self):
            self.cursor = FakeCursor()

        async def __aenter__(self):
            return self.cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_transaction = FakeTransaction()
    monkeypatch.setattr(
        staff_call_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        staff_call_repository.StaffCallRepository().async_submit_staff_call(
            call_type="방문 등록 도움",
            description="대상 어르신을 찾는 데 도움이 필요합니다.",
            idempotency_key="idem_staff_001",
            visitor_id=42,
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result == {
        "result_code": "ACCEPTED",
        "result_message": "직원이 곧 도착합니다.",
        "reason_code": None,
        "call_id": "member_event_9102",
        "linked_visitor_id": 42,
        "linked_member_id": 1,
    }
    assert any("FROM visitor" in query for query, _ in fake_transaction.cursor.calls)
    assert any("INSERT INTO member_event" in query for query, _ in fake_transaction.cursor.calls)
    assert not any(
        "INSERT INTO kiosk_staff_call_log" in query
        for query, _ in fake_transaction.cursor.calls
    )
    event_params = next(
        params
        for query, params in fake_transaction.cursor.calls
        if "INSERT INTO member_event" in query
    )
    assert event_params[0] == 1
    assert event_params[1] == "STAFF_CALL"
    assert "visitor_id=42" in event_params[-1]
    assert "kiosk_id=lobby_kiosk_01" in event_params[-1]


def test_staff_call_repository_stores_kiosk_log_without_resident_context(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.lastrowid = 77
            self._last_query = ""

        async def execute(self, query, params=None):
            self.calls.append((query, params))
            self._last_query = query

        async def fetchone(self):
            if "FROM idempotency_record" in self._last_query:
                return None
            return None

    class FakeTransaction:
        def __init__(self):
            self.cursor = FakeCursor()

        async def __aenter__(self):
            return self.cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_transaction = FakeTransaction()
    monkeypatch.setattr(
        staff_call_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        staff_call_repository.StaffCallRepository().async_submit_staff_call(
            call_type="기타 문의",
            description="로비에서 도움이 필요합니다.",
            idempotency_key="idem_staff_002",
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result["result_code"] == "ACCEPTED"
    assert result["call_id"] == "kiosk_call_77"
    assert result["linked_visitor_id"] is None
    assert result["linked_member_id"] is None
    assert any(
        "INSERT INTO kiosk_staff_call_log" in query
        for query, _ in fake_transaction.cursor.calls
    )
    assert not any("INSERT INTO member_event" in query for query, _ in fake_transaction.cursor.calls)
    log_params = next(
        params
        for query, params in fake_transaction.cursor.calls
        if "INSERT INTO kiosk_staff_call_log" in query
    )
    assert log_params[0] == "idem_staff_002"
    assert log_params[2] == "기타 문의"
    assert log_params[6] == "lobby_kiosk_01"


def test_staff_call_repository_replays_existing_idempotent_response(monkeypatch):
    expected_response = {
        "result_code": "ACCEPTED",
        "result_message": "직원이 곧 도착합니다.",
        "reason_code": None,
        "call_id": "kiosk_call_77",
        "linked_visitor_id": None,
        "linked_member_id": None,
    }
    request_hash = staff_call_repository.StaffCallRepository()._build_request_hash(
        call_type="기타 문의",
        description="로비에서 도움이 필요합니다.",
        visitor_id=None,
        member_id=None,
        kiosk_id="lobby_kiosk_01",
    )

    class FakeCursor:
        def __init__(self):
            self.calls = []
            self._last_query = ""

        async def execute(self, query, params=None):
            self.calls.append((query, params))
            self._last_query = query

        async def fetchone(self):
            return {
                "request_hash": request_hash,
                "response_json": json.dumps(expected_response, ensure_ascii=False),
            }

    class FakeTransaction:
        def __init__(self):
            self.cursor = FakeCursor()

        async def __aenter__(self):
            return self.cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_transaction = FakeTransaction()
    monkeypatch.setattr(
        staff_call_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        staff_call_repository.StaffCallRepository().async_submit_staff_call(
            call_type="기타 문의",
            description="로비에서 도움이 필요합니다.",
            idempotency_key="idem_staff_002",
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result == expected_response
    assert len(fake_transaction.cursor.calls) == 1


def test_staff_call_repository_rejects_idempotency_conflict(monkeypatch):
    class FakeCursor:
        async def execute(self, query, params=None):
            self._last_query = query

        async def fetchone(self):
            return {
                "request_hash": "different_hash",
                "response_json": "{}",
            }

    class FakeTransaction:
        async def __aenter__(self):
            return FakeCursor()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        staff_call_repository,
        "async_transaction",
        lambda: FakeTransaction(),
    )

    result = asyncio.run(
        staff_call_repository.StaffCallRepository().async_submit_staff_call(
            call_type="기타 문의",
            description="로비에서 도움이 필요합니다.",
            idempotency_key="idem_staff_002",
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result["result_code"] == "INVALID_REQUEST"
    assert result["reason_code"] == "IDEMPOTENCY_KEY_CONFLICT"
