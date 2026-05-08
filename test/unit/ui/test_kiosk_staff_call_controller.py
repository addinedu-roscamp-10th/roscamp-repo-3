class FakeStaffCallService:
    def __init__(self, *, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = []

    def submit_staff_call(self, **kwargs):
        self.calls.append(kwargs)
        if self.exception is not None:
            raise self.exception
        return self.response


def test_staff_call_controller_submits_registered_context():
    from ui.kiosk_ui.staff_call_controller import KioskStaffCallController

    service = FakeStaffCallService(
        response={
            "result_code": "ACCEPTED",
            "result_message": "직원이 곧 도착합니다.",
        }
    )
    controller = KioskStaffCallController(
        staff_call_service=service,
        kiosk_id="lobby_kiosk_01",
        idempotency_key_factory=lambda: "kiosk_staff_call_fixed",
    )

    result = controller.submit(
        source_screen="안내 진행 화면",
        current_patient={"visitor_id": "999", "member_id": "777"},
        current_visitor_session={"visitor_id": "42", "member_id": "1"},
        selected_patient={
            "visitor_id": "42",
            "member_id": "1",
            "name": "김*수",
            "room": "301",
        },
    )

    assert result.success is True
    assert result.message == "직원이 곧 도착합니다."
    assert service.calls == [
        {
            "call_type": "직원 호출",
            "description": (
                "안내 진행 화면에서 직원 호출을 요청했습니다. "
                "대상=김*수 호실=301 visitor_id=42 member_id=1"
            ),
            "idempotency_key": "kiosk_staff_call_fixed",
            "visitor_id": 42,
            "member_id": 1,
            "kiosk_id": "lobby_kiosk_01",
        }
    ]


def test_staff_call_controller_submits_unlinked_lobby_context():
    from ui.kiosk_ui.staff_call_controller import KioskStaffCallController

    service = FakeStaffCallService(response={"result_code": "ACCEPTED"})
    controller = KioskStaffCallController(
        staff_call_service=service,
        kiosk_id="lobby_kiosk_01",
        idempotency_key_factory=lambda: "kiosk_staff_call_lobby",
    )

    result = controller.submit(
        source_screen="홈 화면",
        current_patient=None,
        current_visitor_session=None,
    )

    assert result.success is True
    assert result.message == "직원이 곧 도착합니다."
    assert service.calls[0]["visitor_id"] is None
    assert service.calls[0]["member_id"] is None
    assert service.calls[0]["description"] == "홈 화면에서 직원 호출을 요청했습니다."


def test_staff_call_controller_returns_modal_error_on_service_failure():
    from ui.kiosk_ui.staff_call_controller import KioskStaffCallController

    service = FakeStaffCallService(exception=RuntimeError("connection refused"))
    controller = KioskStaffCallController(
        staff_call_service=service,
        kiosk_id="lobby_kiosk_01",
        idempotency_key_factory=lambda: "kiosk_staff_call_error",
    )

    result = controller.submit(
        source_screen="방문자 등록 화면",
        current_patient=None,
        current_visitor_session=None,
    )

    assert result.success is False
    assert result.message == "서버 연결 중 오류가 발생했습니다: connection refused"
