from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_GUIDE_CREATE_TASK,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
    MESSAGE_CODE_PATROL_CREATE_TASK,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
    MESSAGE_CODE_TASK_STATUS_QUERY,
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
        raise RemoteServiceError(
            str(response.get("error", "서버 요청 처리에 실패했습니다."))
        )

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

    def get_robot_status_bundle(self):
        return _rpc("caregiver", "get_robot_status_bundle")

    def get_alert_log_bundle(
        self,
        *,
        period="LAST_24_HOURS",
        severity=None,
        source_component=None,
        task_id=None,
        robot_id=None,
        event_type=None,
        limit=100,
    ):
        return _rpc(
            "caregiver",
            "get_alert_log_bundle",
            period=period,
            severity=severity,
            source_component=source_component,
            task_id=task_id,
            robot_id=robot_id,
            event_type=event_type,
            limit=limit,
        )


class PatientRemoteService:
    def search_patient_candidates(
        self, name: str = "", room_no: str = "", limit: int = 10
    ):
        return _rpc(
            "patient",
            "search_patient_candidates",
            name=name,
            room_no=room_no,
            limit=limit,
        )

    def get_patient_info(self, member_id):
        return _rpc("patient", "get_patient_info", member_id=member_id)

    def search_patient_info(self, name: str, room_no: str):
        return _rpc("patient", "search_patient_info", name=name, room_no=room_no)


class InventoryRemoteService:
    def get_inventory_rows(self):
        return _rpc("inventory", "get_inventory_rows")

    def get_inventory_bundle(self):
        return _rpc("inventory", "get_inventory_bundle")

    def add_inventory(self, item_name, quantity):
        return _rpc(
            "inventory", "add_inventory", item_name=item_name, quantity=quantity
        )

    def add_item_quantity(self, *, item_id, quantity_delta):
        return _rpc(
            "inventory",
            "add_item_quantity",
            item_id=item_id,
            quantity_delta=quantity_delta,
        )

    def set_item_quantity(self, *, item_id, quantity):
        return _rpc(
            "inventory",
            "set_item_quantity",
            item_id=item_id,
            quantity=quantity,
        )


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
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")

    def create_patrol_task(self, **payload):
        response = send_request(MESSAGE_CODE_PATROL_CREATE_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")

    def resume_patrol_task(self, **payload):
        response = send_request(MESSAGE_CODE_PATROL_RESUME_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

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
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        return self._rpc(
            "get_active_map_bundle",
            include_disabled=include_disabled,
            include_zone_boundaries=include_zone_boundaries,
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

    def update_operation_zone_boundary(
        self,
        *,
        zone_id,
        expected_revision,
        boundary_json,
    ):
        return self._rpc(
            "update_operation_zone_boundary",
            zone_id=zone_id,
            expected_revision=expected_revision,
            boundary_json=boundary_json,
        )

    def update_goal_pose(
        self,
        *,
        goal_pose_id,
        expected_updated_at=None,
        zone_id=None,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        return self._rpc(
            "update_goal_pose",
            goal_pose_id=goal_pose_id,
            expected_updated_at=expected_updated_at,
            zone_id=zone_id,
            purpose=purpose,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            is_enabled=is_enabled,
        )

    def update_patrol_area_path(
        self,
        *,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        return self._rpc(
            "update_patrol_area_path",
            patrol_area_id=patrol_area_id,
            expected_revision=expected_revision,
            path_json=path_json,
        )

    def get_map_asset(
        self,
        *,
        asset_type,
        map_id=None,
        encoding=None,
    ):
        return self._rpc(
            "get_map_asset",
            asset_type=asset_type,
            map_id=map_id,
            encoding=encoding,
        )


class FmsConfigRemoteService:
    _SERVICE_NAME = "fms_config"

    def _rpc(self, method: str, **kwargs):
        return _rpc(self._SERVICE_NAME, method, **kwargs)

    def get_active_graph_bundle(
        self,
        *,
        include_disabled=True,
        include_edges=True,
        include_routes=True,
        include_reservations=False,
    ):
        return self._rpc(
            "get_active_graph_bundle",
            include_disabled=include_disabled,
            include_edges=include_edges,
            include_routes=include_routes,
            include_reservations=include_reservations,
        )

    def upsert_waypoint(
        self,
        *,
        waypoint_id,
        expected_updated_at=None,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group=None,
        is_enabled,
    ):
        return self._rpc(
            "upsert_waypoint",
            waypoint_id=waypoint_id,
            expected_updated_at=expected_updated_at,
            display_name=display_name,
            waypoint_type=waypoint_type,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            snap_group=snap_group,
            is_enabled=is_enabled,
        )

    def upsert_edge(
        self,
        *,
        edge_id,
        expected_updated_at=None,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        traversal_cost=None,
        priority=None,
        is_enabled,
    ):
        return self._rpc(
            "upsert_edge",
            edge_id=edge_id,
            expected_updated_at=expected_updated_at,
            from_waypoint_id=from_waypoint_id,
            to_waypoint_id=to_waypoint_id,
            is_bidirectional=is_bidirectional,
            traversal_cost=traversal_cost,
            priority=priority,
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

    def get_task_status(self, *, task_id):
        payload = {
            "task_id": str(task_id).strip(),
        }
        response = send_request(MESSAGE_CODE_TASK_STATUS_QUERY, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")

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
    def create_guide_task(self, *, request_id, visitor_id, idempotency_key):
        payload = {
            "request_id": request_id,
            "visitor_id": visitor_id,
            "idempotency_key": idempotency_key,
        }
        response = send_request(MESSAGE_CODE_GUIDE_CREATE_TASK, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")

    def search_patient(self, keyword: str):
        return _rpc("visit_guide", "search_patient", keyword=keyword)

    def start_robot_guide(self, patient: dict, member_id=None):
        return _rpc(
            "visit_guide", "start_robot_guide", patient=patient, member_id=member_id
        )

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

    def start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
        navigation_timeout_sec=None,
    ):
        kwargs = {
            "task_id": task_id,
            "target_track_id": target_track_id,
        }
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        if navigation_timeout_sec is not None:
            kwargs["navigation_timeout_sec"] = navigation_timeout_sec
        return _rpc("visit_guide", "start_guide_driving", **kwargs)

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

    def get_tracking_status(self, *, task_id=None, pinky_id=None):
        kwargs = {}
        if task_id is not None:
            kwargs["task_id"] = task_id
        if pinky_id is not None:
            kwargs["pinky_id"] = pinky_id
        return _rpc("visit_guide", "get_tracking_status", **kwargs)

    def get_task_status(self, *, task_id):
        payload = {
            "task_id": str(task_id).strip(),
        }
        response = send_request(MESSAGE_CODE_TASK_STATUS_QUERY, payload)

        if not response.get("ok"):
            raise RemoteServiceError(
                str(response.get("error", "서버 요청 처리에 실패했습니다."))
            )

        return response.get("payload")


class VisitorInfoRemoteService:
    def get_patient_visit_info(self, keyword: str):
        return _rpc("visitor_info", "get_patient_visit_info", keyword=keyword)


class VisitorRegisterRemoteService:
    def submit_registration(self, **payload):
        return _rpc("visitor_register", "submit_registration", **payload)


class KioskVisitorRemoteService:
    def lookup_residents(self, *, keyword: str, limit: int = 10):
        return _rpc(
            "kiosk_visitor",
            "lookup_residents",
            keyword=keyword,
            limit=limit,
        )

    def register_visit(
        self,
        *,
        visitor_name: str,
        phone_no: str,
        relationship: str,
        visit_purpose: str,
        target_member_id,
        privacy_agreed: bool,
        kiosk_id=None,
    ):
        return _rpc(
            "kiosk_visitor",
            "register_visit",
            visitor_name=visitor_name,
            phone_no=phone_no,
            relationship=relationship,
            visit_purpose=visit_purpose,
            target_member_id=target_member_id,
            privacy_agreed=privacy_agreed,
            kiosk_id=kiosk_id,
        )

    def get_care_history(self, *, visitor_id):
        return _rpc(
            "kiosk_visitor",
            "get_care_history",
            visitor_id=visitor_id,
        )


class StaffCallRemoteService:
    def submit_staff_call(
        self,
        *,
        call_type,
        idempotency_key,
        description=None,
        detail=None,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        kwargs = {
            "call_type": call_type,
            "idempotency_key": idempotency_key,
            "visitor_id": visitor_id,
            "member_id": member_id,
            "kiosk_id": kiosk_id,
        }
        if description is not None:
            kwargs["description"] = description
        if detail is not None:
            kwargs["detail"] = detail
        return _rpc("staff_call", "submit_staff_call", **kwargs)
