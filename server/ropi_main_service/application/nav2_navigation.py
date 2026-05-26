import asyncio
from copy import deepcopy

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.application.goal_pose_navigation import (
    DEFAULT_FRAME_ID,
    DEFAULT_IPC_TIMEOUT_BUFFER_SEC,
    MINIMUM_IPC_TIMEOUT_SEC,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


class Nav2PoseNavigationService:
    def __init__(
        self,
        command_client=None,
        command_execution_recorder=None,
        ipc_timeout_buffer_sec=DEFAULT_IPC_TIMEOUT_BUFFER_SEC,
        minimum_ipc_timeout_sec=MINIMUM_IPC_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.command_execution_recorder = (
            command_execution_recorder or CommandExecutionRecorder()
        )
        self.ipc_timeout_buffer_sec = ipc_timeout_buffer_sec
        self.minimum_ipc_timeout_sec = minimum_ipc_timeout_sec

    def navigate(
        self,
        *,
        task_id,
        nav_phase,
        goal_pose,
        timeout_sec,
        robot_id=None,
        pinky_id=None,
        behavior_tree="",
    ):
        command, payload, ipc_timeout = self._build_navigation_command(
            task_id=task_id,
            nav_phase=nav_phase,
            goal_pose=goal_pose,
            timeout_sec=timeout_sec,
            robot_id=robot_id,
            pinky_id=pinky_id,
            behavior_tree=behavior_tree,
        )

        return self.command_execution_recorder.record(
            self._build_command_execution_spec(
                task_id=task_id,
                nav_phase=nav_phase,
                payload=payload,
            ),
            lambda: self._get_command_client().send_command(
                command,
                payload,
                timeout=ipc_timeout,
            ),
        )

    async def async_navigate(
        self,
        *,
        task_id,
        nav_phase,
        goal_pose,
        timeout_sec,
        robot_id=None,
        pinky_id=None,
        behavior_tree="",
    ):
        command, payload, ipc_timeout = self._build_navigation_command(
            task_id=task_id,
            nav_phase=nav_phase,
            goal_pose=goal_pose,
            timeout_sec=timeout_sec,
            robot_id=robot_id,
            pinky_id=pinky_id,
            behavior_tree=behavior_tree,
        )
        command_client = self._get_command_client()
        async_send_command = getattr(command_client, "async_send_command", None)
        spec = self._build_command_execution_spec(
            task_id=task_id,
            nav_phase=nav_phase,
            payload=payload,
        )

        if async_send_command is not None:

            async def _send_async_command():
                return await async_send_command(command, payload, timeout=ipc_timeout)

            return await self.command_execution_recorder.async_record(
                spec,
                _send_async_command,
            )

        async def _send_sync_command_in_thread():
            return await asyncio.to_thread(
                command_client.send_command,
                command,
                payload,
                timeout=ipc_timeout,
            )

        return await self.command_execution_recorder.async_record(
            spec,
            _send_sync_command_in_thread,
        )

    def _build_navigation_command(
        self,
        *,
        task_id,
        nav_phase,
        goal_pose,
        timeout_sec,
        robot_id=None,
        pinky_id=None,
        behavior_tree="",
    ):
        self._validate_request(
            task_id=task_id,
            nav_phase=nav_phase,
            goal_pose=goal_pose,
            timeout_sec=timeout_sec,
        )
        target_robot_id = self._normalize_robot_id(robot_id or pinky_id)
        normalized_timeout_sec = int(timeout_sec)
        goal = {
            "task_id": str(task_id).strip(),
            "nav_phase": str(nav_phase).strip(),
            "pose": self._normalize_goal_pose(goal_pose),
            "behavior_tree": str(behavior_tree or ""),
            "timeout_sec": normalized_timeout_sec,
        }

        return (
            "navigate_to_pose",
            {
                "robot_id": target_robot_id,
                "goal": goal,
            },
            self._build_ipc_timeout_sec(normalized_timeout_sec),
        )

    @staticmethod
    def _build_target_endpoint(robot_id):
        return f"/{robot_id}/navigate_to_pose"

    def _build_command_execution_spec(self, *, task_id, nav_phase, payload):
        robot_id = str(payload.get("robot_id") or "").strip()
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_ACTION",
            command_type="NAV2_NAVIGATE_TO_POSE",
            command_phase=str(nav_phase).strip(),
            target_component="ros_service",
            target_robot_id=robot_id,
            target_endpoint=self._build_target_endpoint(robot_id),
            request_payload=payload,
        )

    @staticmethod
    def _normalize_goal_pose(goal_pose):
        normalized_goal_pose = deepcopy(goal_pose)
        header = normalized_goal_pose.setdefault("header", {})
        header.setdefault("stamp", {"sec": 0, "nanosec": 0})

        if not str(header.get("frame_id", "")).strip():
            header["frame_id"] = DEFAULT_FRAME_ID

        return normalized_goal_pose

    @staticmethod
    def _normalize_robot_id(robot_id):
        normalized = str(robot_id or "").strip()
        if not normalized or "/" in normalized:
            raise ValueError("robot_id는 상대 namespace 형식이어야 합니다.")
        return normalized

    @staticmethod
    def _validate_request(*, task_id, nav_phase, goal_pose, timeout_sec):
        if not str(task_id or "").strip():
            raise ValueError("task_id가 필요합니다.")

        if not str(nav_phase or "").strip():
            raise ValueError("nav_phase가 필요합니다.")

        if not isinstance(goal_pose, dict) or not goal_pose:
            raise ValueError("goal_pose가 필요합니다.")

        if int(timeout_sec) <= 0:
            raise ValueError("timeout_sec는 1 이상이어야 합니다.")

    def _get_command_client(self):
        if self.command_client is None:
            raise RuntimeError("ROS service command client가 아직 구성되지 않았습니다.")

        return self.command_client

    def _build_ipc_timeout_sec(self, timeout_sec):
        return max(
            float(timeout_sec) + float(self.ipc_timeout_buffer_sec),
            float(self.minimum_ipc_timeout_sec),
        )


__all__ = ["Nav2PoseNavigationService"]
