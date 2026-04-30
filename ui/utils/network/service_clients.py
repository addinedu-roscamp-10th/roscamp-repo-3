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


class VisitorInfoRemoteService:
    def get_patient_visit_info(self, keyword: str):
        return _rpc("visitor_info", "get_patient_visit_info", keyword=keyword)


class VisitorRegisterRemoteService:
    def submit_registration(self, **payload):
        return _rpc("visitor_register", "submit_registration", **payload)


class StaffCallRemoteService:
    def submit_staff_call(self, **payload):
        return _rpc("staff_call", "submit_staff_call", **payload)
