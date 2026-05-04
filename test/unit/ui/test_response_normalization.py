from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_MONITOR_PAGE = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_monitor_page.py"
)
TASK_REQUEST_PAGE = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_request_page.py"
)


def test_normalize_ui_response_wraps_non_dict_response_with_defaults():
    from ui.utils.core.responses import normalize_ui_response

    response = normalize_ui_response(
        "broken payload",
        success=False,
        default_fields={"cancel_requested": False},
    )

    assert response == {
        "result_code": "CLIENT_ERROR",
        "result_message": "broken payload",
        "reason_code": "CLIENT_RESPONSE_INVALID",
        "cancel_requested": False,
    }


def test_normalize_ui_response_fills_failed_missing_result_code_and_preserves_fields():
    from ui.utils.core.responses import normalize_ui_response

    response = normalize_ui_response(
        {
            "task_id": "1001",
            "result_message": "취소 실패",
        },
        success=False,
        default_fields={"cancel_requested": False},
    )

    assert response == {
        "task_id": "1001",
        "result_message": "취소 실패",
        "result_code": "CLIENT_ERROR",
        "reason_code": "CLIENT_ERROR",
    }


def test_normalize_ui_response_can_require_result_code_even_on_success():
    from ui.utils.core.responses import normalize_ui_response

    response = normalize_ui_response(
        {"result_message": "증거사진 응답 형식 오류"},
        success=True,
        require_result_code=True,
    )

    assert response == {
        "result_message": "증거사진 응답 형식 오류",
        "result_code": "CLIENT_ERROR",
        "reason_code": "CLIENT_ERROR",
    }


def test_normalize_ui_response_preserves_existing_reason_code():
    from ui.utils.core.responses import normalize_ui_response

    response = normalize_ui_response(
        {
            "result_message": "서버 응답 형식 오류",
            "reason_code": "UPSTREAM_RESPONSE_INVALID",
        },
        success=False,
    )

    assert response == {
        "result_message": "서버 응답 형식 오류",
        "reason_code": "UPSTREAM_RESPONSE_INVALID",
        "result_code": "CLIENT_ERROR",
    }


def test_response_handlers_use_shared_normalizer():
    monitor_source = TASK_MONITOR_PAGE.read_text(encoding="utf-8")
    request_source = TASK_REQUEST_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.responses import normalize_ui_response" in monitor_source
    assert "from ui.utils.core.responses import normalize_ui_response" in request_source
    assert "CLIENT_RESPONSE_INVALID" not in monitor_source
    assert "CLIENT_RESPONSE_INVALID" not in request_source
