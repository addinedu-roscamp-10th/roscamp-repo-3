import asyncio
from datetime import date

from server.ropi_main_service.persistence.repositories import kiosk_visitor_repository


def test_kiosk_visitor_repository_async_lookup_formats_safe_candidates(monkeypatch):
    calls = []

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [
            {
                "member_id": 1,
                "member_name": "김영수",
                "room_no": "301",
                "birth_date": date(1942, 3, 14),
            }
        ]

    monkeypatch.setattr(kiosk_visitor_repository, "async_fetch_all", fake_async_fetch_all)

    result = asyncio.run(
        kiosk_visitor_repository.KioskVisitorRepository().async_find_resident_candidates(
            keyword="301",
            limit=50,
        )
    )

    assert result == [
        {
            "member_id": 1,
            "display_name": "김*수",
            "birth_date": "1942-03-14",
            "room_no": "301",
            "visit_available": True,
            "guide_available": True,
        }
    ]
    assert "FROM member" in calls[0][0]
    assert calls[0][1] == ("%301%", "%301%", 10)


def test_kiosk_visitor_repository_registers_visitor_and_visit_event(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.lastrowid = 42
            self._last_query = ""

        async def execute(self, query, params=None):
            self.calls.append((query, params))
            self._last_query = query

        async def fetchone(self):
            if "FROM member" in self._last_query:
                return {
                    "member_id": 1,
                    "member_name": "김영수",
                    "room_no": "301",
                }
            if "FROM visitor" in self._last_query:
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
        kiosk_visitor_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        kiosk_visitor_repository.KioskVisitorRepository().async_register_visit(
            visitor_name="김민수",
            phone_no="010-1111-2222",
            relationship="아들",
            visit_purpose="정기 면회",
            target_member_id=1,
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result["visitor_id"] == 42
    assert result["member_id"] == 1
    assert result["resident_name"] == "김영수"
    assert any("INSERT INTO visitor" in query for query, _ in fake_transaction.cursor.calls)
    assert any("INSERT INTO member_event" in query for query, _ in fake_transaction.cursor.calls)
    event_params = fake_transaction.cursor.calls[-1][1]
    assert event_params[0] == 1
    assert event_params[1] == "VISIT_CHECKIN"
    assert "방문객=김민수" in event_params[-1]


def test_kiosk_visitor_repository_gets_visitor_safe_care_history(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {
            "visitor_id": 42,
            "member_id": 1,
            "member_name": "김영수",
            "room_no": "301",
        }

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [
            {
                "event_at": "2026-04-19T09:30:00",
                "event_category": "CARE",
                "event_type_code": "MEAL_RECORDED",
                "event_name": "아침 식사 완료",
                "description": "정상적으로 식사 완료",
                "severity": "INFO",
            },
            {
                "event_at": "2026-04-19T08:00:00",
                "event_category": "HEALTH",
                "event_type_code": "MEDICATION_RECORDED",
                "event_name": "오전 복약 완료",
                "description": "혈압약 복용 완료",
                "severity": "INFO",
            },
        ]

    monkeypatch.setattr(kiosk_visitor_repository, "async_fetch_one", fake_async_fetch_one)
    monkeypatch.setattr(kiosk_visitor_repository, "async_fetch_all", fake_async_fetch_all)

    result = asyncio.run(
        kiosk_visitor_repository.KioskVisitorRepository().async_get_visitor_care_history(
            visitor_id=42,
        )
    )

    assert result == {
        "visitor_id": 42,
        "member_id": 1,
        "resident_summary": {
            "display_name": "김*수",
            "room_no": "301",
            "visit_status": "면회 가능",
        },
        "care_summary": {
            "meal_status": "아침 식사 완료",
            "medication_status": "오전 복약 완료",
            "safety_status": "최근 낙상 알림 없음",
            "last_updated_at": "2026-04-19T09:30:00",
        },
        "recent_events": [
            {
                "event_at": "2026-04-19T09:30:00",
                "event_category": "CARE",
                "event_name": "아침 식사 완료",
                "summary": "정상적으로 식사 완료",
            },
            {
                "event_at": "2026-04-19T08:00:00",
                "event_category": "HEALTH",
                "event_name": "오전 복약 완료",
                "summary": "혈압약 복용 완료",
            },
        ],
    }
    assert "FROM visitor" in calls[0][0]
    assert calls[0][1] == (42,)
    assert "FROM member_event" in calls[1][0]
    assert "MEAL_RECORDED" in calls[1][0]
    assert "MEDICATION_RECORDED" in calls[1][0]
    assert "FALL_DETECTED" in calls[1][0]
    assert calls[1][1] == (1, 5)


def test_kiosk_visitor_repository_masks_resident_name_with_first_and_last_visible():
    mask = kiosk_visitor_repository.KioskVisitorRepository._mask_display_name

    assert mask("김영수") == "김*수"
    assert mask("김수") == "김*수"
    assert mask("김") == "김"
    assert mask("  박영철수  ") == "박**수"
    assert mask("") == "-"


def test_kiosk_visitor_repository_returns_none_when_visitor_context_missing(monkeypatch):
    async def fake_async_fetch_one(query, params=None):
        return None

    async def fake_async_fetch_all(query, params=None):
        raise AssertionError("member events must not be queried without visitor context")

    monkeypatch.setattr(kiosk_visitor_repository, "async_fetch_one", fake_async_fetch_one)
    monkeypatch.setattr(kiosk_visitor_repository, "async_fetch_all", fake_async_fetch_all)

    result = asyncio.run(
        kiosk_visitor_repository.KioskVisitorRepository().async_get_visitor_care_history(
            visitor_id=999,
        )
    )

    assert result is None
