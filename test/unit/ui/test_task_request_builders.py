from pathlib import Path

from ui.utils.session.session_manager import UserSession


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_delivery_builder_creates_if_del_001_payload_with_numeric_ids():
    from ui.utils.pages.caregiver.task_request_builders import (
        build_delivery_create_payload,
    )

    payload = build_delivery_create_payload(
        current_user=UserSession(user_id="7", name="김보호", role="caregiver"),
        item={"item_id": "1", "item_name": "세면도구 세트", "quantity": 4},
        quantity=2,
        destination_id="delivery_room_301",
        priority="URGENT",
        notes="문 앞에 놓아주세요.",
        request_id_factory=lambda: "req_fixed",
        idempotency_key_factory=lambda: "idem_fixed",
    )

    assert payload == {
        "request_id": "req_fixed",
        "caregiver_id": 7,
        "item_id": 1,
        "quantity": 2,
        "destination_id": "delivery_room_301",
        "priority": "URGENT",
        "notes": "문 앞에 놓아주세요.",
        "idempotency_key": "idem_fixed",
    }


def test_delivery_builder_rejects_invalid_ui_state_with_user_message():
    from ui.utils.pages.caregiver.task_request_builders import (
        PayloadValidationError,
        build_delivery_create_payload,
    )

    try:
        build_delivery_create_payload(
            current_user=UserSession(user_id="7", name="김보호", role="caregiver"),
            item=None,
            quantity=1,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes="",
        )
    except PayloadValidationError as exc:
        assert str(exc) == "유효한 물품을 선택하세요."
    else:
        raise AssertionError("invalid item should fail")


def test_task_request_page_delegates_payload_and_preview_building():
    source = (
        PROJECT_ROOT / "ui/utils/pages/caregiver/task_request_page.py"
    ).read_text()

    assert "from uuid import uuid4" not in source
    assert "req_patrol_" not in source
    assert "idem_patrol_" not in source


def test_delivery_preview_and_response_normalizer_match_ui_contract():
    from ui.utils.pages.caregiver.task_request_builders import (
        build_delivery_preview,
        normalize_delivery_response,
    )

    preview = build_delivery_preview(
        current_user=UserSession(user_id="7", name="김보호", role="caregiver"),
        item={"item_id": 1, "item_name": "세면도구 세트"},
        quantity=2,
        destination_id="delivery_room_301",
        priority="URGENT",
    )

    assert preview == {
        "caregiver_id": "7",
        "item_id": "1",
        "item_name": "세면도구 세트",
        "quantity": 2,
        "destination_id": "delivery_room_301",
        "priority": "URGENT",
    }

    assert normalize_delivery_response(False, "서버 연결 실패") == {
        "result_code": "REJECTED",
        "result_message": "서버 연결 실패",
        "reason_code": None,
        "task_id": None,
        "task_status": None,
        "assigned_robot_id": None,
    }


def test_patrol_builder_creates_pat_001_payload_and_preview():
    from ui.utils.pages.caregiver.task_request_builders import (
        build_patrol_create_payload,
        build_patrol_preview,
    )

    current_user = UserSession(user_id="7", name="김보호", role="caregiver")
    area = {
        "patrol_area_id": "patrol_ward_night_01",
        "patrol_area_name": "야간 병동 순찰",
        "patrol_area_revision": 7,
        "map_id": "map_test11_0423",
        "waypoint_count": 3,
        "path_frame_id": None,
    }

    payload = build_patrol_create_payload(
        current_user=current_user,
        area=area,
        priority="URGENT",
        request_id_factory=lambda: "req_patrol_fixed",
        idempotency_key_factory=lambda: "idem_patrol_fixed",
    )
    preview = build_patrol_preview(current_user, area, "URGENT")

    assert payload == {
        "request_id": "req_patrol_fixed",
        "caregiver_id": 7,
        "patrol_area_id": "patrol_ward_night_01",
        "priority": "URGENT",
        "idempotency_key": "idem_patrol_fixed",
    }
    assert preview == {
        "task_type": "PATROL",
        "caregiver_id": "7",
        "patrol_area_id": "patrol_ward_night_01",
        "patrol_area_name": "야간 병동 순찰",
        "patrol_area_revision": 7,
        "priority": "URGENT",
        "map_id": "map_test11_0423",
        "waypoint_count": 3,
        "path_frame_id": None,
    }
