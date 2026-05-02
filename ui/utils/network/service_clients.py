from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
    MESSAGE_CODE_PATROL_CREATE_TASK,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
)
from ui.utils.network.tcp_client import send_request


class RemoteServiceError(RuntimeError):
    """Raised when the control server returns an application error."""


def _rpc(service: str, method: str, **kwargs):
    response = send_request(
        MESSAGE_CODE_INTERNAL_RPC,
        {
            "service": service,
            "method": method,
            "kwargs": kwargs,
        },
    )

    if not response.get("ok"):
        raise RemoteServiceError(str(response.get("error", "서버 요청 처리에 실패했습니다.")))

    return response.get("payload")


class LoginClient:
    def authenticate(self, login_id: str, password: str, role: str):
        response = send_request(
            MESSAGE_CODE_LOGIN,
            {
                "login_id": login_id,
                "password": password,
                "role": role,
            },
        )

        if response.get("ok"):
            return True, response.get("payload", {})

        return False, str(response.get("error", "로그인에 실패했습니다."))


class CaregiverRemoteService:
    def get_dashboard_bundle(self):
        return _rpc("caregiver", "get_dashboard_bundle")


class PatientRemoteService:
    def search_patient_info(self, name: str, room_no: str):
        return _rpc("patient", "search_patient_info", name=name, room_no=room_no)


class InventoryRemoteService:
    def get_inventory_rows(self):
        return _rpc("inventory", "get_inventory_rows")

    def add_inventory(self, item_name, quantity):
        return _rpc("inventory", "add_inventory", item_name=item_name, quantity=quantity)


class DeliveryRequestRemoteService:
    _SERVICE_NAME = "task_request"

    def _rpc(self, method: str, **kwargs):
        return _rpc(self._SERVICE_NAME, method, **kwargs)

    def get_delivery_items(self):
        return self._rpc("get_delivery_items")

    def get_delivery_destinations(self):
        return self._rpc("get_delivery_destinations")

    def get_patrol_areas(self):
        return self._rpc("get_patrol_areas")

    def get_product_names(self):
        return self._rpc("get_product_names")

    def create_delivery_task(self, **payload):
        response = send_request(MESSAGE_CODE_DELIVERY_CREATE_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(str(response.get("error", "서버 요청 처리에 실패했습니다.")))

        return response.get("payload")

    def create_patrol_task(self, **payload):
        response = send_request(MESSAGE_CODE_PATROL_CREATE_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(str(response.get("error", "서버 요청 처리에 실패했습니다.")))

        return response.get("payload")

    def resume_patrol_task(self, **payload):
        response = send_request(MESSAGE_CODE_PATROL_RESUME_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(str(response.get("error", "서버 요청 처리에 실패했습니다.")))

        return response.get("payload")

    def submit_delivery_request(self, **payload):
        return self._rpc("submit_delivery_request", **payload)

    def cancel_delivery_task(self, task_id, action_name=None):
        kwargs = {
            "task_id": str(task_id).strip(),
        }
        if action_name is not None:
            kwargs["action_name"] = str(action_name).strip()
        return self._rpc("cancel_delivery_task", **kwargs)


class CoordinateConfigRemoteService:
    _SERVICE_NAME = "coordinate_config"

    def _rpc(self, method: str, **kwargs):
        return _rpc(self._SERVICE_NAME, method, **kwargs)

    def get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_patrol_paths=True,
    ):
        return self._rpc(
            "get_active_map_bundle",
            include_disabled=include_disabled,
            include_patrol_paths=include_patrol_paths,
        )

    def create_operation_zone(
        self,
        *,
        zone_id,
        zone_name,
        zone_type,
        map_id=None,
        is_enabled=True,
    ):
        return self._rpc(
            "create_operation_zone",
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            map_id=map_id,
            is_enabled=is_enabled,
        )

    def update_operation_zone(
        self,
        *,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        return self._rpc(
            "update_operation_zone",
            zone_id=zone_id,
            expected_revision=expected_revision,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )


class TaskMonitorRemoteService:
    _SERVICE_NAME = "task_monitor"

    def _rpc(self, method: str, **kwargs):
        return _rpc(self._SERVICE_NAME, method, **kwargs)

    def get_task_monitor_snapshot(
        self,
        *,
        consumer_id="ui-admin-task-monitor",
        task_types=None,
        statuses=None,
        include_recent_terminal=True,
        recent_terminal_limit=20,
        limit=100,
    ):
        return self._rpc(
            "get_task_monitor_snapshot",
            consumer_id=consumer_id,
            task_types=task_types,
            statuses=statuses,
            include_recent_terminal=include_recent_terminal,
            recent_terminal_limit=recent_terminal_limit,
            limit=limit,
        )

    def cancel_task(
        self,
        *,
        task_id,
        caregiver_id,
        reason="operator_cancel",
    ):
        return _rpc(
            "task_request",
            "cancel_task",
            task_id=str(task_id).strip(),
            caregiver_id=caregiver_id,
            reason=reason,
        )

    def get_fall_evidence_image(
        self,
        *,
        consumer_id="ui-admin-task-monitor",
        task_id,
        alert_id=None,
        evidence_image_id,
        result_seq=None,
    ):
        payload = {
            "consumer_id": consumer_id,
            "task_id": task_id,
            "alert_id": alert_id,
            "evidence_image_id": evidence_image_id,
            "result_seq": result_seq,
        }
        response = send_request(MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")


class VisitGuideRemoteService:
    def search_patient(self, keyword: str):
        return _rpc("visit_guide", "search_patient", keyword=keyword)

    def start_robot_guide(self, patient: dict, member_id=None):
        return _rpc("visit_guide", "start_robot_guide", patient=patient, member_id=member_id)

    def begin_guide_session(
        self,
        *,
        patient: dict,
        member_id=None,
        pinky_id=None,
        command_type="WAIT_TARGET_TRACKING",
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        kwargs = {
            "patient": patient,
            "member_id": member_id,
            "command_type": command_type,
            "target_track_id": target_track_id,
            "wait_timeout_sec": wait_timeout_sec,
            "finish_reason": finish_reason,
        }
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        return _rpc("visit_guide", "begin_guide_session", **kwargs)

    def finish_guide_session(
        self,
        *,
        task_id,
        pinky_id=None,
        target_track_id="",
        finish_reason="",
    ):
        kwargs = {
            "task_id": task_id,
            "target_track_id": target_track_id,
            "finish_reason": finish_reason,
        }
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        return _rpc("visit_guide", "finish_guide_session", **kwargs)

    def send_guide_command(
        self,
        *,
        task_id,
        command_type,
        pinky_id=None,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        kwargs = {
            "task_id": task_id,
            "command_type": command_type,
            "target_track_id": target_track_id,
            "wait_timeout_sec": wait_timeout_sec,
            "finish_reason": finish_reason,
        }
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        return _rpc("visit_guide", "send_guide_command", **kwargs)

    def get_guide_runtime_status(self, pinky_id=None):
        kwargs = {}
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        return _rpc("visit_guide", "get_guide_runtime_status", **kwargs)


class VisitorInfoRemoteService:
    def get_patient_visit_info(self, keyword: str):
        return _rpc("visitor_info", "get_patient_visit_info", keyword=keyword)


class VisitorRegisterRemoteService:
    def submit_registration(self, **payload):
        return _rpc("visitor_register", "submit_registration", **payload)


class StaffCallRemoteService:
    def submit_staff_call(self, **payload):
        return _rpc("staff_call", "submit_staff_call", **payload)
