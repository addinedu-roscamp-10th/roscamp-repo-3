from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)


DEFAULT_INITIAL_POSE_IPC_TIMEOUT_SEC = 1.0
DEFAULT_INITIAL_POSE_FRAME_ID = "map"


class RobotLocalizationService:
    def __init__(
        self,
        *,
        command_client=None,
        ipc_timeout_sec=DEFAULT_INITIAL_POSE_IPC_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.ipc_timeout_sec = float(ipc_timeout_sec)

    def set_initial_pose(
        self,
        *,
        robot_id,
        x,
        y,
        yaw,
        frame_id=DEFAULT_INITIAL_POSE_FRAME_ID,
        covariance=None,
    ):
        request = self._build_initial_pose_payload(
            robot_id=robot_id,
            frame_id=frame_id,
            x=x,
            y=y,
            yaw=yaw,
            covariance=covariance,
        )
        if request.get("result_code") == "INVALID_REQUEST":
            return request

        try:
            return self.command_client.send_command(
                "set_initial_pose",
                request,
                timeout=self.ipc_timeout_sec,
            )
        except RosServiceCommandError as exc:
            return {
                "result_code": "REJECTED",
                "reason_code": "ROS_SERVICE_UNAVAILABLE",
                "result_message": str(exc),
            }

    def _build_initial_pose_payload(
        self,
        *,
        robot_id,
        frame_id,
        x,
        y,
        yaw,
        covariance,
    ):
        normalized_robot_id = self._normalize_robot_id(robot_id)
        if normalized_robot_id is None:
            return self._invalid(
                "INVALID_ROBOT_ID",
                "robot_id는 상대 robot namespace여야 합니다.",
            )

        normalized_frame_id = str(frame_id or DEFAULT_INITIAL_POSE_FRAME_ID).strip()
        if not normalized_frame_id:
            normalized_frame_id = DEFAULT_INITIAL_POSE_FRAME_ID

        numeric_pose = self._coerce_pose_numbers(x=x, y=y, yaw=yaw)
        if numeric_pose is None:
            return self._invalid(
                "INVALID_INITIAL_POSE",
                "초기 위치 x, y, yaw는 숫자여야 합니다.",
            )

        normalized_covariance = self._normalize_covariance(covariance)
        if normalized_covariance == "INVALID":
            return self._invalid(
                "INVALID_COVARIANCE",
                "covariance는 36개 숫자 배열이어야 합니다.",
            )

        return {
            "robot_id": normalized_robot_id,
            "frame_id": normalized_frame_id,
            **numeric_pose,
            "covariance": normalized_covariance,
        }

    @staticmethod
    def _normalize_robot_id(robot_id):
        value = str(robot_id or "").strip()
        if not value or value.startswith("/") or "/" in value:
            return None
        return value

    @staticmethod
    def _coerce_pose_numbers(*, x, y, yaw):
        try:
            return {
                "x": float(x),
                "y": float(y),
                "yaw": float(yaw),
            }
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_covariance(covariance):
        if covariance is None:
            return None
        if not isinstance(covariance, (list, tuple)) or len(covariance) != 36:
            return "INVALID"
        try:
            return [float(value) for value in covariance]
        except (TypeError, ValueError):
            return "INVALID"

    @staticmethod
    def _invalid(reason_code, message):
        return {
            "result_code": "INVALID_REQUEST",
            "reason_code": reason_code,
            "result_message": message,
        }


__all__ = [
    "DEFAULT_INITIAL_POSE_FRAME_ID",
    "DEFAULT_INITIAL_POSE_IPC_TIMEOUT_SEC",
    "RobotLocalizationService",
]
