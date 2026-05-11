import asyncio
import json
import logging
import os

from server.ropi_main_service.application.caregiver import CaregiverService
from server.ropi_main_service.application.delivery_config import (
    get_delivery_runtime_config,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)


logger = logging.getLogger(__name__)

DISABLED_VALUES = {"0", "false", "no", "off", "disabled"}
DEFAULT_POLL_INTERVAL_SEC = 1.0


class RobotStatusEventRuntime:
    def __init__(
        self,
        *,
        caregiver_service=None,
        task_event_publisher=None,
        runtime_config=None,
        poll_interval_sec=DEFAULT_POLL_INTERVAL_SEC,
    ):
        self.caregiver_service = caregiver_service or CaregiverService()
        self.task_event_publisher = task_event_publisher
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.poll_interval_sec = max(0.1, float(poll_interval_sec))
        self._last_signatures = {}

    async def run_forever(self):
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                logger.warning(
                    "robot status event polling failed: %s",
                    exc,
                    exc_info=True,
                )
            await asyncio.sleep(self.poll_interval_sec)

    async def poll_once(self):
        bundle = await self.caregiver_service.async_get_robot_status_bundle()
        bundle = bundle if isinstance(bundle, dict) else {}
        published_count = 0

        for robot in bundle.get("robots") or []:
            if not isinstance(robot, dict):
                continue
            event = self._build_event(robot)
            if event is None:
                continue
            event_type, payload = event
            signature_key = (
                event_type,
                payload.get("robot_id") or payload.get("pinky_id"),
            )
            signature = json.dumps(payload, sort_keys=True, default=str)
            if self._last_signatures.get(signature_key) == signature:
                continue
            self._last_signatures[signature_key] = signature
            await self._publish(event_type, payload)
            published_count += 1

        return {
            "result_code": "ACCEPTED",
            "published_count": published_count,
        }

    def _build_event(self, robot):
        robot_id = str(robot.get("robot_id") or "").strip()
        if not robot_id:
            return None

        robot_type = str(robot.get("robot_type") or "").strip().upper()
        if robot_id.lower().startswith("jetcobot") or robot_type == "ARM":
            return "ARM_UPDATED", self._build_arm_payload(robot)
        return "PINKY_UPDATED", self._build_pinky_payload(robot)

    def _build_pinky_payload(self, robot):
        robot_id = str(robot.get("robot_id") or "").strip()
        pose = (
            robot.get("current_pose")
            if isinstance(robot.get("current_pose"), dict)
            else None
        )
        zone_name = self._zone_name(robot.get("current_location"))
        return {
            "pinky_id": robot_id,
            "robot_id": robot_id,
            "pinky_state": robot.get("runtime_state") or "UNKNOWN",
            "runtime_state": robot.get("runtime_state") or "UNKNOWN",
            "connection_status": robot.get("connection_status"),
            "battery_percent": self._optional_float(robot.get("battery_percent")),
            "active_task_id": robot.get("current_task_id"),
            "current_phase": robot.get("current_phase"),
            "pose": pose,
            "current_pose": pose,
            "zone_id": None,
            "zone_name": zone_name,
            "fault_code": robot.get("fault_code"),
            "last_seen_at": robot.get("last_seen_at"),
        }

    def _build_arm_payload(self, robot):
        robot_id = str(robot.get("robot_id") or "").strip()
        return {
            "arm_id": self._arm_id_for_robot(robot_id),
            "robot_id": robot_id,
            "station_role": self._station_role(robot),
            "arm_state": robot.get("runtime_state") or "UNKNOWN",
            "runtime_state": robot.get("runtime_state") or "UNKNOWN",
            "connection_status": robot.get("connection_status"),
            "active_task_id": robot.get("current_task_id"),
            "active_transfer_direction": None,
            "active_item_id": None,
            "active_robot_slot_id": None,
            "fault_code": robot.get("fault_code"),
            "last_seen_at": robot.get("last_seen_at"),
        }

    async def _publish(self, event_type, payload):
        if self.task_event_publisher is None:
            return None
        publish = getattr(self.task_event_publisher, "publish", None)
        if publish is None:
            publish = self.task_event_publisher
        result = publish(event_type, payload)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _arm_id_for_robot(self, robot_id):
        if robot_id == self.runtime_config.pickup_arm_robot_id:
            return self.runtime_config.pickup_arm_id
        if robot_id == self.runtime_config.destination_arm_robot_id:
            return self.runtime_config.destination_arm_id
        return robot_id

    @staticmethod
    def _station_role(robot):
        for item in robot.get("station_roles") or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("station_role") or "").strip()
            if role:
                return role
        return "UNKNOWN"

    @staticmethod
    def _zone_name(value):
        text = str(value or "").strip()
        if not text or text == "-" or text.startswith("x=") or text.startswith("좌표"):
            return None
        return text

    @staticmethod
    def _optional_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def start_robot_status_event_polling_if_enabled(
    *,
    loop=None,
    workflow_task_manager=None,
    caregiver_service=None,
    task_event_publisher=None,
    poll_interval_sec=None,
):
    if not _robot_status_event_poll_enabled():
        logger.info(
            "Robot status event polling is disabled; set "
            "ROBOT_STATUS_EVENT_POLL_ENABLED=true to enable it."
        )
        return None

    interval_sec = (
        float(poll_interval_sec)
        if poll_interval_sec is not None
        else _robot_status_event_poll_interval_sec()
    )
    workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
    runtime = RobotStatusEventRuntime(
        caregiver_service=caregiver_service,
        task_event_publisher=task_event_publisher,
        poll_interval_sec=interval_sec,
    )
    logger.info("Starting robot status event poller interval_sec=%s", interval_sec)
    return workflow_task_manager.create_task(
        runtime.run_forever(),
        name="robot_status_event_poll",
        loop=loop,
        cancel_on_shutdown=True,
    )


def _robot_status_event_poll_enabled():
    raw = str(os.getenv("ROBOT_STATUS_EVENT_POLL_ENABLED", "true")).strip().lower()
    return raw not in DISABLED_VALUES


def _robot_status_event_poll_interval_sec():
    raw = str(os.getenv("ROBOT_STATUS_EVENT_POLL_INTERVAL_SEC", "")).strip()
    if not raw:
        return DEFAULT_POLL_INTERVAL_SEC
    try:
        return max(0.1, float(raw))
    except ValueError:
        return DEFAULT_POLL_INTERVAL_SEC


__all__ = [
    "RobotStatusEventRuntime",
    "start_robot_status_event_polling_if_enabled",
]
