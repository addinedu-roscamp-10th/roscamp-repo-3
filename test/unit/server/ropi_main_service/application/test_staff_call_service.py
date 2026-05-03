import asyncio

from server.ropi_main_service.application.staff_call import StaffCallService


class FakeStaffCallRepository:
    def __init__(self):
        self.submitted = None
        self.response = {
            "result_code": "ACCEPTED",
            "result_message": "직원이 곧 도착합니다.",
            "reason_code": None,
            "call_id": "member_event_9102",
            "linked_visitor_id": 42,
            "linked_member_id": 1,
        }

    async def async_submit_staff_call(
        self,
        *,
        call_type,
        description,
        idempotency_key,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        self.submitted = {
            "call_type": call_type,
            "description": description,
            "idempotency_key": idempotency_key,
            "visitor_id": visitor_id,
            "member_id": member_id,
            "kiosk_id": kiosk_id,
        }
        return self.response


def test_staff_call_service_returns_if_gui_010_payload():
    repository = FakeStaffCallRepository()
    service = StaffCallService(repository=repository)

    result = asyncio.run(
        service.async_submit_staff_call(
            call_type="방문 등록 도움",
            description="대상 어르신을 찾는 데 도움이 필요합니다.",
            idempotency_key="idem_staff_001",
            visitor_id="42",
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
    assert repository.submitted == {
        "call_type": "방문 등록 도움",
        "description": "대상 어르신을 찾는 데 도움이 필요합니다.",
        "idempotency_key": "idem_staff_001",
        "visitor_id": 42,
        "member_id": None,
        "kiosk_id": "lobby_kiosk_01",
    }


def test_staff_call_service_accepts_legacy_detail_alias():
    repository = FakeStaffCallRepository()
    service = StaffCallService(repository=repository)

    result = asyncio.run(
        service.async_submit_staff_call(
            call_type="긴급 호출",
            detail="도움 필요",
            idempotency_key="idem_staff_002",
            member_id="7",
        )
    )

    assert result["result_code"] == "ACCEPTED"
    assert repository.submitted["description"] == "도움 필요"
    assert repository.submitted["member_id"] == 7


def test_staff_call_service_rejects_invalid_request_fields():
    service = StaffCallService(repository=FakeStaffCallRepository())

    empty_type = asyncio.run(
        service.async_submit_staff_call(
            call_type=" ",
            description="도움 필요",
            idempotency_key="idem_staff_003",
        )
    )
    empty_key = asyncio.run(
        service.async_submit_staff_call(
            call_type="긴급 호출",
            description="도움 필요",
            idempotency_key=" ",
        )
    )
    invalid_visitor = asyncio.run(
        service.async_submit_staff_call(
            call_type="긴급 호출",
            description="도움 필요",
            idempotency_key="idem_staff_004",
            visitor_id="abc",
        )
    )
    invalid_member = asyncio.run(
        service.async_submit_staff_call(
            call_type="긴급 호출",
            description="도움 필요",
            idempotency_key="idem_staff_004_2",
            member_id=0,
        )
    )
    long_description = asyncio.run(
        service.async_submit_staff_call(
            call_type="긴급 호출",
            description="x" * 501,
            idempotency_key="idem_staff_005",
        )
    )

    assert empty_type["reason_code"] == "CALL_TYPE_EMPTY"
    assert empty_key["reason_code"] == "IDEMPOTENCY_KEY_EMPTY"
    assert invalid_visitor["reason_code"] == "VISITOR_SESSION_INVALID"
    assert invalid_member["reason_code"] == "VISITOR_SESSION_INVALID"
    assert long_description["reason_code"] == "DESCRIPTION_TOO_LONG"
