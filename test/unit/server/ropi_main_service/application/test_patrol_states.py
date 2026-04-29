from server.ropi_main_service.application.patrol_states import (
    PATROL_STATUS_WAITING_FALL_RESPONSE,
    PHASE_WAIT_FALL_RESPONSE,
    is_waiting_fall_response,
)


def test_is_waiting_fall_response_accepts_phase_aliases():
    assert is_waiting_fall_response(phase=PHASE_WAIT_FALL_RESPONSE) is True
    assert is_waiting_fall_response(phase="waiting_fall_response") is True


def test_is_waiting_fall_response_accepts_patrol_status_alias():
    assert (
        is_waiting_fall_response(
            phase="FOLLOW_PATROL_PATH",
            patrol_status=PATROL_STATUS_WAITING_FALL_RESPONSE,
        )
        is True
    )


def test_is_waiting_fall_response_rejects_non_waiting_state():
    assert (
        is_waiting_fall_response(
            phase="FOLLOW_PATROL_PATH",
            patrol_status="MOVING",
        )
        is False
    )
