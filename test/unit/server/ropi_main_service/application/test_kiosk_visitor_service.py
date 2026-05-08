import asyncio

from server.ropi_main_service.application.kiosk_visitor import KioskVisitorService


class FakeKioskVisitorRepository:
    def __init__(self):
        self.lookup_calls = []
        self.registered = None
        self.care_history_calls = []
        self.care_history_result = {
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
                    "event_name": "오전 케어 완료",
                    "summary": "오전 케어가 완료되었습니다.",
                }
            ],
        }

    async def async_find_resident_candidates(self, *, keyword, limit):
        self.lookup_calls.append({"keyword": keyword, "limit": limit})
        return [
            {
                "member_id": 1,
                "display_name": "김*수",
                "birth_date": "1942-03-14",
                "room_no": "301",
                "visit_available": True,
                "guide_available": True,
            }
        ]

    async def async_register_visit(
        self,
        *,
        visitor_name,
        phone_no,
        relationship,
        visit_purpose,
        target_member_id,
        kiosk_id=None,
    ):
        self.registered = {
            "visitor_name": visitor_name,
            "phone_no": phone_no,
            "relationship": relationship,
            "visit_purpose": visit_purpose,
            "target_member_id": target_member_id,
            "kiosk_id": kiosk_id,
        }
        return {
            "visitor_id": 42,
            "member_id": 1,
            "resident_name": "김영수",
            "room_no": "301",
            "visit_status": "면회 가능",
        }

    async def async_get_visitor_care_history(self, *, visitor_id):
        self.care_history_calls.append(visitor_id)
        return self.care_history_result


def test_lookup_residents_returns_if_gui_008_shape():
    repository = FakeKioskVisitorRepository()
    service = KioskVisitorService(repository=repository)

    result = asyncio.run(service.async_lookup_residents(keyword="301", limit=20))

    assert result == {
        "result_code": "FOUND",
        "result_message": "어르신 정보를 확인했습니다.",
        "reason_code": None,
        "matches": [
            {
                "member_id": 1,
                "display_name": "김*수",
                "birth_date": "1942-03-14",
                "room_no": "301",
                "visit_available": True,
                "guide_available": True,
            }
        ],
    }
    assert repository.lookup_calls == [{"keyword": "301", "limit": 10}]


def test_lookup_residents_rejects_empty_keyword():
    service = KioskVisitorService(repository=FakeKioskVisitorRepository())

    result = asyncio.run(service.async_lookup_residents(keyword=" "))

    assert result["result_code"] == "INVALID_REQUEST"
    assert result["reason_code"] == "KEYWORD_EMPTY"
    assert result["matches"] == []


def test_register_visit_returns_memory_session_payload_without_server_session_id():
    repository = FakeKioskVisitorRepository()
    service = KioskVisitorService(repository=repository)

    result = asyncio.run(
        service.async_register_visit(
            visitor_name="김민수",
            phone_no="010-1111-2222",
            relationship="아들",
            visit_purpose="정기 면회",
            target_member_id=1,
            privacy_agreed=True,
            kiosk_id="lobby_kiosk_01",
        )
    )

    assert result == {
        "result_code": "REGISTERED",
        "result_message": "방문 등록이 완료되었습니다.",
        "reason_code": None,
        "visitor_id": 42,
        "member_id": 1,
        "resident_name": "김영수",
        "room_no": "301",
        "visit_status": "면회 가능",
    }
    assert "kiosk_session_id" not in result
    assert "session_expires_at" not in result
    assert repository.registered["target_member_id"] == 1


def test_register_visit_requires_privacy_consent():
    service = KioskVisitorService(repository=FakeKioskVisitorRepository())

    result = asyncio.run(
        service.async_register_visit(
            visitor_name="김민수",
            phone_no="010-1111-2222",
            relationship="아들",
            visit_purpose="정기 면회",
            target_member_id=1,
            privacy_agreed=False,
        )
    )

    assert result["result_code"] == "INVALID_REQUEST"
    assert result["reason_code"] == "PRIVACY_CONSENT_REQUIRED"
    assert "visitor_id" not in result


def test_get_care_history_returns_if_gui_010_visitor_safe_payload():
    repository = FakeKioskVisitorRepository()
    service = KioskVisitorService(repository=repository)

    result = asyncio.run(service.async_get_care_history(visitor_id=42))

    assert result == {
        "result_code": "OK",
        "result_message": "케어 이력을 조회했습니다.",
        "reason_code": None,
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
                "event_name": "오전 케어 완료",
                "summary": "오전 케어가 완료되었습니다.",
            }
        ],
    }
    assert repository.care_history_calls == [42]


def test_get_care_history_rejects_invalid_visitor_id():
    service = KioskVisitorService(repository=FakeKioskVisitorRepository())

    result = asyncio.run(service.async_get_care_history(visitor_id=""))

    assert result["result_code"] == "INVALID_REQUEST"
    assert result["reason_code"] == "VISITOR_ID_INVALID"
    assert "resident_summary" not in result


def test_get_care_history_returns_not_found_when_visitor_is_missing():
    repository = FakeKioskVisitorRepository()
    repository.care_history_result = None
    service = KioskVisitorService(repository=repository)

    result = asyncio.run(service.async_get_care_history(visitor_id=999))

    assert result["result_code"] == "NOT_FOUND"
    assert result["reason_code"] == "VISITOR_NOT_FOUND"
    assert repository.care_history_calls == [999]
