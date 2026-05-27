from datetime import datetime, timezone

from server.ropi_main_service.application.fms_config_formatters import (
    format_fms_reservation,
)
from server.ropi_main_service.application.formatting import generated_at, optional_int
from server.ropi_main_service.persistence.repositories.fms_reservation_repository import (
    FmsReservationRepository,
)


class FmsRuntimeService:
    DEFAULT_LEASE_SEC = 30
    WAITING_PHASE = "WAITING_FMS_RESERVATION"
    VALID_RESOURCE_TYPES = {"WAYPOINT", "EDGE"}

    def __init__(self, repository=None, clock=None):
        self.repository = repository or FmsReservationRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_reservation_snapshot(self, *, map_id=None):
        reservations = self.repository.get_reservation_snapshot(map_id=map_id)
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "reservations": [
                format_fms_reservation(row) for row in reservations or []
            ],
        }

    def request_reservation(
        self,
        *,
        task_id,
        robot_id,
        map_id,
        resources,
        lease_sec=None,
    ):
        normalized_task_id = optional_int(task_id)
        normalized_robot_id = str(robot_id or "").strip()
        normalized_map_id = str(map_id or "").strip()
        normalized_resources, resource_error = self._normalize_resources(resources)
        if (
            normalized_task_id is None
            or not normalized_robot_id
            or not normalized_map_id
            or resource_error is not None
        ):
            return self._invalid_request_response(resource_error)

        result = self.repository.request_reservation(
            task_id=normalized_task_id,
            robot_id=normalized_robot_id,
            map_id=normalized_map_id,
            resources=normalized_resources,
            lease_sec=self._normalize_lease_sec(lease_sec),
        )
        reservation_status = result.get("reservation_status") or "UNAVAILABLE"
        reason_code = result.get("reason_code")
        return {
            "result_code": reservation_status,
            "result_message": None,
            "reason_code": reason_code,
            "generated_at": generated_at(self._clock),
            "reservation_status": reservation_status,
            "task_id": normalized_task_id,
            "robot_id": normalized_robot_id,
            "map_id": normalized_map_id,
            "reservations": [
                format_fms_reservation(row)
                for row in result.get("reservations") or []
            ],
            "next_task_phase": (
                self.WAITING_PHASE if reservation_status == "WAITING" else None
            ),
        }

    def release_reservation(
        self,
        *,
        task_id,
        robot_id=None,
        reason_code=None,
        resources=None,
    ):
        normalized_task_id = optional_int(task_id)
        if normalized_task_id is None:
            return self._invalid_request_response("TASK_ID_INVALID")

        normalized_resources = None
        if resources is not None:
            normalized_resources, resource_error = self._normalize_resources(resources)
            if resource_error is not None:
                return self._invalid_request_response(resource_error)

        normalized_robot_id = str(robot_id or "").strip() or None
        released_count = self.repository.release_reservation(
            task_id=normalized_task_id,
            robot_id=normalized_robot_id,
            reason_code=reason_code,
            resources=normalized_resources,
        )
        return {
            "result_code": "RELEASED" if released_count else "NOT_FOUND",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "released_count": released_count,
            "task_id": normalized_task_id,
        }

    def renew_reservation(self, *, task_id, robot_id=None, lease_sec=None):
        normalized_task_id = optional_int(task_id)
        if normalized_task_id is None:
            return {
                "result_code": "INVALID_REQUEST",
                "result_message": None,
                "reason_code": "TASK_ID_INVALID",
                "generated_at": generated_at(self._clock),
                "renewed_count": 0,
                "task_id": None,
            }

        normalized_robot_id = str(robot_id or "").strip() or None
        renewed_count = self.repository.renew_reservation(
            task_id=normalized_task_id,
            robot_id=normalized_robot_id,
            lease_sec=self._normalize_lease_sec(lease_sec),
        )
        return {
            "result_code": "RENEWED" if renewed_count else "NOT_FOUND",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "renewed_count": renewed_count,
            "task_id": normalized_task_id,
        }

    def _normalize_resources(self, resources):
        if not isinstance(resources, list) or not resources:
            return [], "FMS_RESOURCE_INVALID"

        normalized = []
        for resource in resources:
            if not isinstance(resource, dict):
                return [], "FMS_RESOURCE_INVALID"
            resource_type = str(resource.get("resource_type") or "").strip().upper()
            resource_id = str(resource.get("resource_id") or "").strip()
            if resource_type not in self.VALID_RESOURCE_TYPES or not resource_id:
                return [], "FMS_RESOURCE_INVALID"
            normalized.append(
                {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                }
            )
        return normalized, None

    def _normalize_lease_sec(self, lease_sec):
        if lease_sec is None:
            return self.DEFAULT_LEASE_SEC
        try:
            return max(1, int(lease_sec))
        except (TypeError, ValueError):
            return self.DEFAULT_LEASE_SEC

    def _invalid_request_response(self, reason_code):
        return {
            "result_code": "INVALID_REQUEST",
            "result_message": None,
            "reason_code": reason_code or "FMS_REQUEST_INVALID",
            "generated_at": generated_at(self._clock),
            "reservation_status": None,
            "task_id": None,
            "robot_id": None,
            "map_id": None,
            "reservations": [],
            "next_task_phase": None,
        }


__all__ = ["FmsRuntimeService"]
