from collections.abc import Callable
from typing import Any
from uuid import uuid4


class PayloadValidationError(ValueError):
    """Raised when current UI state cannot produce a valid task payload."""


def _uuid_value(prefix: str) -> str:
    return f"{prefix}{uuid4().hex}"


def _user_id(current_user: Any) -> str:
    return str(getattr(current_user, "user_id", "") or "").strip()


def _require_decimal(value: Any, message: str) -> int:
    normalized = str(value or "").strip()
    if not normalized or not normalized.isdecimal():
        raise PayloadValidationError(message)
    return int(normalized)


def build_delivery_create_payload(
    *,
    current_user: Any,
    item: Any,
    quantity: int,
    destination_id: Any,
    priority: str,
    notes: str | None,
    request_id_factory: Callable[[], str] | None = None,
    idempotency_key_factory: Callable[[], str] | None = None,
) -> dict:
    if not isinstance(item, dict):
        raise PayloadValidationError("유효한 물품을 선택하세요.")

    item_id = _require_decimal(
        item.get("item_id"),
        "물품 식별자를 확인할 수 없습니다.",
    )
    caregiver_id = _require_decimal(
        _user_id(current_user),
        "caregiver_id를 확인할 수 없습니다.",
    )
    normalized_destination_id = str(destination_id or "").strip()
    if not normalized_destination_id:
        raise PayloadValidationError("목적지를 선택하세요.")

    request_id = (
        request_id_factory() if request_id_factory is not None else _uuid_value("req_")
    )
    idempotency_key = (
        idempotency_key_factory()
        if idempotency_key_factory is not None
        else _uuid_value("idem_")
    )

    return {
        "request_id": request_id,
        "caregiver_id": caregiver_id,
        "item_id": item_id,
        "quantity": quantity,
        "destination_id": normalized_destination_id,
        "priority": priority,
        "notes": str(notes or "").strip() or None,
        "idempotency_key": idempotency_key,
    }


def build_delivery_preview(
    *,
    current_user: Any,
    item: Any,
    quantity: int,
    destination_id: Any,
    priority: str,
) -> dict:
    if isinstance(item, dict):
        item_id = str(item.get("item_id") or "-")
        item_name = str(item.get("item_name") or "-")
    else:
        item_id = "-"
        item_name = "-"

    caregiver_id = _user_id(current_user) if current_user is not None else "-"

    return {
        "caregiver_id": caregiver_id or "-",
        "item_id": item_id,
        "item_name": item_name,
        "quantity": quantity,
        "destination_id": str(destination_id or "-"),
        "priority": priority,
    }


def normalize_delivery_response(success: bool, response: Any) -> dict:
    if isinstance(response, dict):
        payload = dict(response)
    else:
        payload = {
            "result_code": "ACCEPTED" if success else "REJECTED",
            "result_message": str(response or ""),
        }

    payload.setdefault("result_code", "ACCEPTED" if success else "REJECTED")
    payload.setdefault("result_message", None)
    payload.setdefault("reason_code", None)
    payload.setdefault("task_id", None)
    payload.setdefault("task_status", None)
    payload.setdefault("assigned_robot_id", None)
    return payload


def build_patrol_create_payload(
    *,
    current_user: Any,
    area: dict,
    priority: str,
    request_id_factory: Callable[[], str] | None = None,
    idempotency_key_factory: Callable[[], str] | None = None,
) -> dict:
    if current_user is None:
        raise PayloadValidationError("로그인 사용자가 없습니다.")

    patrol_area_id = str(area.get("patrol_area_id") or "").strip()
    if not patrol_area_id:
        raise PayloadValidationError("순찰 구역을 선택하세요.")

    request_id = (
        request_id_factory()
        if request_id_factory is not None
        else _uuid_value("req_patrol_")
    )
    idempotency_key = (
        idempotency_key_factory()
        if idempotency_key_factory is not None
        else _uuid_value("idem_patrol_")
    )

    return {
        "request_id": request_id,
        "caregiver_id": _require_decimal(
            _user_id(current_user),
            "caregiver_id를 확인할 수 없습니다.",
        ),
        "patrol_area_id": patrol_area_id,
        "priority": priority,
        "idempotency_key": idempotency_key,
    }


def build_patrol_preview(current_user: Any, area: dict, priority: str) -> dict:
    return {
        "task_type": "PATROL",
        "caregiver_id": _user_id(current_user) if current_user else None,
        "patrol_area_id": area.get("patrol_area_id"),
        "patrol_area_name": area.get("patrol_area_name"),
        "patrol_area_revision": area.get("patrol_area_revision"),
        "priority": priority,
        "assigned_robot_id": area.get("assigned_robot_id") or "pinky3",
    }
