MESSAGE_CODE_GUIDE_CREATE_TASK = 0x4001


def build_if_gui_001_request():
    return {
        "request_id": "req_guide_001",
        "visitor_id": "visitor_001",
        "idempotency_key": "idem_guide_001",
    }


def build_if_gui_001_success_response():
    return {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": "task_guide_001",
        "task_status": "WAITING_DISPATCH",
        "resident_name": "김OO",
        "room_no": "301",
        "destination_id": "room_301",
    }


def build_if_gui_001_rejected_response():
    return {
        "result_code": "REJECTED",
        "result_message": "안내 목적지 정의가 비어 있습니다.",
        "reason_code": "GUIDE_DESTINATION_NOT_CONFIGURED",
    }


def test_if_gui_001_message_code_matches_interface_spec():
    assert MESSAGE_CODE_GUIDE_CREATE_TASK == 0x4001


def test_if_gui_001_request_matches_interface_spec_fields():
    payload = build_if_gui_001_request()

    assert payload == {
        "request_id": "req_guide_001",
        "visitor_id": "visitor_001",
        "idempotency_key": "idem_guide_001",
    }


def test_if_gui_001_success_response_matches_interface_spec_fields():
    response = build_if_gui_001_success_response()

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["resident_name"] == "김OO"
    assert response["room_no"] == "301"
    assert response["destination_id"] == "room_301"


def test_if_gui_001_rejected_response_uses_reason_code_from_interface_spec():
    response = build_if_gui_001_rejected_response()

    assert response == {
        "result_code": "REJECTED",
        "result_message": "안내 목적지 정의가 비어 있습니다.",
        "reason_code": "GUIDE_DESTINATION_NOT_CONFIGURED",
    }
