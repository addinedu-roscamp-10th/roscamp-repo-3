import asyncio

from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


DEFAULT_DRIVE_ROBOT_READINESS_TIMEOUT_SEC = 1.0


class DriveRobotReadinessService:
    def __init__(
        self,
        *,
        command_client=None,
        readiness_timeout_sec=DEFAULT_DRIVE_ROBOT_READINESS_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.readiness_timeout_sec = float(readiness_timeout_sec)

    def available_robot_ids(self, robot_ids):
        known_result_seen = False
        available = []
        for robot_id in self._normalize_robot_ids(robot_ids):
            ready = self.is_robot_ready(robot_id)
            if ready is None:
                continue
            known_result_seen = True
            if ready:
                available.append(robot_id)
        return tuple(available) if known_result_seen else None

    async def async_available_robot_ids(self, robot_ids):
        known_result_seen = False
        available = []
        for robot_id in self._normalize_robot_ids(robot_ids):
            ready = await self.async_is_robot_ready(robot_id)
            if ready is None:
                continue
            known_result_seen = True
            if ready:
                available.append(robot_id)
        return tuple(available) if known_result_seen else None

    def is_robot_ready(self, robot_id):
        normalized_robot_id = self._normalize_robot_id(robot_id)
        if not normalized_robot_id:
            return False
        try:
            response = self.command_client.send_command(
                "get_runtime_status",
                self._build_payload(normalized_robot_id),
                timeout=self.readiness_timeout_sec,
            )
        except Exception:
            return None
        return self._nav2_action_is_ready(response, robot_id=normalized_robot_id)

    async def async_is_robot_ready(self, robot_id):
        normalized_robot_id = self._normalize_robot_id(robot_id)
        if not normalized_robot_id:
            return False
        async_send_command = getattr(self.command_client, "async_send_command", None)
        try:
            if async_send_command is not None:
                response = await async_send_command(
                    "get_runtime_status",
                    self._build_payload(normalized_robot_id),
                    timeout=self.readiness_timeout_sec,
                )
            else:
                response = await asyncio.to_thread(
                    self.command_client.send_command,
                    "get_runtime_status",
                    self._build_payload(normalized_robot_id),
                    timeout=self.readiness_timeout_sec,
                )
        except Exception:
            return None
        return self._nav2_action_is_ready(response, robot_id=normalized_robot_id)

    @staticmethod
    def _normalize_robot_ids(robot_ids):
        return tuple(
            robot_id
            for robot_id in (
                DriveRobotReadinessService._normalize_robot_id(robot_id)
                for robot_id in robot_ids or ()
            )
            if robot_id
        )

    @staticmethod
    def _normalize_robot_id(robot_id):
        return str(robot_id or "").strip().strip("/")

    @staticmethod
    def _build_payload(robot_id):
        return {
            "pinky_id": robot_id,
            "arm_ids": [],
            "include_navigation": False,
            "include_nav2_navigation": True,
            "include_nav2_lifecycle": True,
        }

    @staticmethod
    def _nav2_action_is_ready(response, *, robot_id):
        checks = (response or {}).get("checks")
        if not isinstance(checks, list):
            return False
        expected_action_name = f"/{robot_id}/navigate_to_pose"
        expected_check_name = f"{robot_id}.navigate_to_pose"
        lifecycle_check_prefix = f"{robot_id}.nav2_lifecycle."
        action_ready = False
        lifecycle_checks = []
        for check in checks:
            if not isinstance(check, dict):
                continue
            if (
                check.get("action_name") == expected_action_name
                or check.get("name") == expected_check_name
            ):
                action_ready = check.get("ready") is True
                continue
            if str(check.get("name") or "").startswith(lifecycle_check_prefix):
                lifecycle_checks.append(check)
        if not action_ready:
            return False
        return all(check.get("ready") is True for check in lifecycle_checks)


__all__ = [
    "DEFAULT_DRIVE_ROBOT_READINESS_TIMEOUT_SEC",
    "DriveRobotReadinessService",
]
