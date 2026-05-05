import base64
import binascii

from PyQt6.QtCore import QObject, pyqtSignal

from ui.utils.network.service_clients import (
    CoordinateConfigRemoteService,
    FmsConfigRemoteService,
)


class CoordinateConfigLoadWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(
        self,
        *,
        service_factory=CoordinateConfigRemoteService,
        fms_service_factory=FmsConfigRemoteService,
    ):
        super().__init__()
        self.service_factory = service_factory
        self.fms_service_factory = fms_service_factory

    def run(self):
        try:
            service = self.service_factory()
            bundle = service.get_active_map_bundle(
                include_disabled=True,
                include_zone_boundaries=True,
                include_patrol_paths=True,
            )
            if not _is_ok_response(bundle):
                self.finished.emit(False, _format_result_error(bundle))
                return

            fms_bundle = self.fms_service_factory().get_active_graph_bundle(
                include_disabled=True,
                include_edges=False,
                include_routes=False,
                include_reservations=False,
            )
            if not _is_ok_response(fms_bundle):
                self.finished.emit(False, _format_result_error(fms_bundle))
                return

            bundle = {
                **bundle,
                "fms_waypoints": fms_bundle.get("waypoints") or [],
                "fms_edges": fms_bundle.get("edges") or [],
                "fms_routes": fms_bundle.get("routes") or [],
                "fms_reservations": fms_bundle.get("reservations") or [],
            }

            map_profile = bundle.get("map_profile") or {}
            map_id = map_profile.get("map_id")
            yaml_asset = service.get_map_asset(
                asset_type="YAML",
                map_id=map_id,
                encoding="TEXT",
            )
            if not _is_ok_response(yaml_asset):
                self.finished.emit(False, _format_result_error(yaml_asset))
                return

            pgm_asset = service.get_map_asset(
                asset_type="PGM",
                map_id=map_id,
                encoding="BASE64",
            )
            if not _is_ok_response(pgm_asset):
                self.finished.emit(False, _format_result_error(pgm_asset))
                return

            yaml_text = str(yaml_asset.get("content_text") or "")
            pgm_bytes = _decode_base64_asset(pgm_asset.get("content_base64"))
            if not yaml_text or not pgm_bytes:
                self.finished.emit(False, "맵 asset 응답이 비어 있습니다.")
                return

            self.finished.emit(
                True,
                {
                    "bundle": bundle,
                    "yaml_text": yaml_text,
                    "pgm_bytes": pgm_bytes,
                    "yaml_sha256": yaml_asset.get("sha256"),
                    "pgm_sha256": pgm_asset.get("sha256"),
                },
            )
        except Exception as exc:
            self.finished.emit(False, str(exc))


class GoalPoseSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            response = self.service_factory().update_goal_pose(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class OperationZoneSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, mode, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.mode = str(mode or "").strip()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            service = self.service_factory()
            if self.mode == "create":
                response = service.create_operation_zone(**self.payload)
                success_code = "CREATED"
            else:
                response = service.update_operation_zone(**self.payload)
                success_code = "UPDATED"

            if (
                isinstance(response, dict)
                and response.get("result_code") == success_code
            ):
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class OperationZoneBoundarySaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            service = self.service_factory()
            response = service.update_operation_zone_boundary(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class PatrolAreaPathSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            response = self.service_factory().update_patrol_area_path(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class FmsWaypointSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=FmsConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            response = self.service_factory().upsert_waypoint(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "OK":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


def _is_ok_response(response):
    return isinstance(response, dict) and response.get("result_code") == "OK"


def _format_result_error(response):
    if not isinstance(response, dict):
        return "좌표 설정 요청에 실패했습니다."
    reason_code = response.get("reason_code")
    message = response.get("result_message")
    result_code = response.get("result_code")
    if reason_code and message:
        return f"{reason_code}: {message}"
    if message:
        return str(message)
    if reason_code:
        return str(reason_code)
    return str(result_code or "좌표 설정 요청에 실패했습니다.")


def _decode_base64_asset(value):
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except (binascii.Error, ValueError):
        return b""


__all__ = [
    "CoordinateConfigLoadWorker",
    "FmsWaypointSaveWorker",
    "GoalPoseSaveWorker",
    "OperationZoneBoundarySaveWorker",
    "OperationZoneSaveWorker",
    "PatrolAreaPathSaveWorker",
]
