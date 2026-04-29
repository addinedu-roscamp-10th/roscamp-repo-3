import asyncio
import json
import math
from copy import deepcopy

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)
from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


DEFAULT_FRAME_ID = "map"
DEFAULT_IPC_TIMEOUT_BUFFER_SEC = 5.0
MINIMUM_IPC_TIMEOUT_SEC = 30.0


class PatrolPathExecutionService:
    def __init__(
        self,
        *,
        command_client=None,
        runtime_config=None,
        command_execution_recorder=None,
        ipc_timeout_buffer_sec=DEFAULT_IPC_TIMEOUT_BUFFER_SEC,
        minimum_ipc_timeout_sec=MINIMUM_IPC_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.runtime_config = runtime_config or get_patrol_runtime_config()
        self.command_execution_recorder = command_execution_recorder or CommandExecutionRecorder()
        self.ipc_timeout_buffer_sec = float(ipc_timeout_buffer_sec)
        self.minimum_ipc_timeout_sec = float(minimum_ipc_timeout_sec)

    def execute(self, *, task_id, path_snapshot_json, timeout_sec):
        command, payload, ipc_timeout = self._build_command(
            task_id=task_id,
            path_snapshot_json=path_snapshot_json,
            timeout_sec=timeout_sec,
        )
        return self.command_execution_recorder.record(
            self._build_command_execution_spec(task_id=task_id, payload=payload),
            lambda: self._get_command_client().send_command(
                command,
                payload,
                timeout=ipc_timeout,
            ),
        )

    async def async_execute(self, *, task_id, path_snapshot_json, timeout_sec):
        command, payload, ipc_timeout = self._build_command(
            task_id=task_id,
            path_snapshot_json=path_snapshot_json,
            timeout_sec=timeout_sec,
        )
        command_client = self._get_command_client()
        async_send_command = getattr(command_client, "async_send_command", None)
        spec = self._build_command_execution_spec(task_id=task_id, payload=payload)

        if async_send_command is not None:
            async def _send_async_command():
                return await async_send_command(command, payload, timeout=ipc_timeout)

            return await self.command_execution_recorder.async_record(spec, _send_async_command)

        async def _send_sync_command_in_thread():
            return await asyncio.to_thread(
                command_client.send_command,
                command,
                payload,
                timeout=ipc_timeout,
            )

        return await self.command_execution_recorder.async_record(spec, _send_sync_command_in_thread)

    def _build_command(self, *, task_id, path_snapshot_json, timeout_sec):
        self._validate_request(task_id=task_id, timeout_sec=timeout_sec)
        normalized_path = self._normalize_path_snapshot(path_snapshot_json)
        goal = {
            "task_id": str(task_id).strip(),
            "path": normalized_path,
            "timeout_sec": int(timeout_sec),
        }
        return (
            "execute_patrol_path",
            {
                "pinky_id": self.runtime_config.pinky_id,
                "goal": goal,
            },
            self._build_ipc_timeout_sec(timeout_sec),
        )

    @staticmethod
    def _build_target_endpoint(pinky_id):
        return f"/ropi/control/{pinky_id}/execute_patrol_path"

    def _build_command_execution_spec(self, *, task_id, payload):
        pinky_id = str(payload.get("pinky_id") or self.runtime_config.pinky_id).strip()
        return CommandExecutionSpec(
            task_id=str(task_id).strip(),
            transport="ROS_ACTION",
            command_type="EXECUTE_PATROL_PATH",
            command_phase="PATROL_PATH_EXECUTION",
            target_component="ros_service",
            target_robot_id=pinky_id,
            target_endpoint=self._build_target_endpoint(pinky_id),
            request_payload=payload,
        )

    @classmethod
    def _normalize_path_snapshot(cls, path_snapshot_json):
        if isinstance(path_snapshot_json, str):
            raw_path = json.loads(path_snapshot_json)
        else:
            raw_path = deepcopy(path_snapshot_json)

        if not isinstance(raw_path, dict):
            raise ValueError("순찰 경로 waypoint가 비어 있습니다.")

        header = raw_path.get("header") if isinstance(raw_path.get("header"), dict) else {}
        frame_id = str(header.get("frame_id") or DEFAULT_FRAME_ID).strip() or DEFAULT_FRAME_ID
        poses = raw_path.get("poses")
        if not isinstance(poses, list) or not poses:
            raise ValueError("순찰 경로 waypoint가 비어 있습니다.")

        return {
            "header": cls._normalize_header(header, frame_id=frame_id),
            "poses": [
                cls._normalize_pose_stamped(pose, frame_id=frame_id)
                for pose in poses
            ],
        }

    @classmethod
    def _normalize_pose_stamped(cls, waypoint, *, frame_id):
        if isinstance(waypoint, dict) and "pose" in waypoint:
            normalized = deepcopy(waypoint)
            header = normalized.get("header") if isinstance(normalized.get("header"), dict) else {}
            normalized["header"] = cls._normalize_header(header, frame_id=frame_id)
            normalized["pose"] = cls._normalize_pose(normalized.get("pose") or {})
            return normalized

        pose = cls._waypoint_to_pose(waypoint)
        return {
            "header": cls._normalize_header({}, frame_id=frame_id),
            "pose": pose,
        }

    @staticmethod
    def _normalize_header(header, *, frame_id):
        normalized = deepcopy(header)
        normalized.setdefault("stamp", {"sec": 0, "nanosec": 0})
        if not str(normalized.get("frame_id") or "").strip():
            normalized["frame_id"] = frame_id
        return normalized

    @classmethod
    def _normalize_pose(cls, pose):
        if not isinstance(pose, dict):
            pose = {}
        position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
        orientation = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {}
        return {
            "position": {
                "x": float(position.get("x", 0.0)),
                "y": float(position.get("y", 0.0)),
                "z": float(position.get("z", 0.0)),
            },
            "orientation": {
                "x": float(orientation.get("x", 0.0)),
                "y": float(orientation.get("y", 0.0)),
                "z": float(orientation.get("z", 0.0)),
                "w": float(orientation.get("w", 1.0)),
            },
        }

    @classmethod
    def _waypoint_to_pose(cls, waypoint):
        if isinstance(waypoint, dict):
            x = waypoint.get("x")
            y = waypoint.get("y")
            z = waypoint.get("z", 0.0)
            yaw = waypoint.get("yaw", waypoint.get("yaw_rad", 0.0))
        else:
            values = list(waypoint or [])
            if len(values) < 2:
                raise ValueError("순찰 경로 waypoint 형식이 올바르지 않습니다.")
            x = values[0]
            y = values[1]
            z = 0.0
            yaw = values[2] if len(values) > 2 else 0.0

        yaw = float(yaw)
        return {
            "position": {
                "x": float(x),
                "y": float(y),
                "z": float(z),
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": math.sin(yaw / 2.0),
                "w": math.cos(yaw / 2.0),
            },
        }

    @staticmethod
    def _validate_request(*, task_id, timeout_sec):
        if not str(task_id or "").strip():
            raise ValueError("task_id가 필요합니다.")
        if int(timeout_sec) <= 0:
            raise ValueError("timeout_sec는 1 이상이어야 합니다.")

    def _get_command_client(self):
        if self.command_client is None:
            raise RuntimeError("ROS service command client가 아직 구성되지 않았습니다.")
        return self.command_client

    def _build_ipc_timeout_sec(self, timeout_sec):
        return max(
            float(timeout_sec) + self.ipc_timeout_buffer_sec,
            self.minimum_ipc_timeout_sec,
        )


__all__ = ["PatrolPathExecutionService"]
