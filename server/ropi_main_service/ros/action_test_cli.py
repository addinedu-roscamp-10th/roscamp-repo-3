import argparse
import json
import sys

from server.ropi_main_service.application.goal_pose import (
    normalize_goal_pose_spec,
    parse_goal_pose_string,
)
from server.ropi_main_service.ipc.uds_client import (
    RosServiceCommandError,
    UnixDomainSocketCommandClient,
)


DEFAULT_NAVIGATION_TIMEOUT_SEC = 120
DEFAULT_NAVIGATION_IPC_TIMEOUT_BUFFER_SEC = 2.0
DEFAULT_ARM_IPC_TIMEOUT_SEC = 30.0
DEFAULT_STATUS_IPC_TIMEOUT_SEC = 2.0
ALLOWED_NAV_PHASES = (
    "DELIVERY_PICKUP",
    "DELIVERY_DESTINATION",
    "GUIDE_START_POSE",
    "GUIDE_DESTINATION",
    "RETURN_TO_DOCK",
)
ALLOWED_TRANSFER_DIRECTIONS = ("TO_ROBOT", "FROM_ROBOT")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send individual ROPI ROS actions through ropi-ros-service."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status",
        help="Check only the requested navigation or manipulation action endpoints.",
    )
    status_parser.add_argument("--pinky-id")
    status_parser.add_argument("--arm-id", action="append", dest="arm_ids", default=[])
    status_parser.add_argument(
        "--ipc-timeout-sec",
        type=float,
        default=DEFAULT_STATUS_IPC_TIMEOUT_SEC,
    )
    status_parser.set_defaults(handler=_run_status)

    nav_parser = subparsers.add_parser(
        "nav",
        help="Send one IF-COM-007 NavigateToGoal action.",
    )
    nav_parser.add_argument("--pinky-id", required=True)
    nav_parser.add_argument("--task-id", required=True)
    nav_parser.add_argument("--nav-phase", required=True, choices=ALLOWED_NAV_PHASES)
    pose_group = nav_parser.add_mutually_exclusive_group(required=True)
    pose_group.add_argument(
        "--pose",
        help="Simple pose string: x,y,yaw[,frame_id] or x=...,y=...,yaw_deg=...",
    )
    pose_group.add_argument("--pose-json", help="PoseStamped or {x,y,yaw} JSON object.")
    nav_parser.add_argument(
        "--timeout-sec",
        type=int,
        default=DEFAULT_NAVIGATION_TIMEOUT_SEC,
    )
    nav_parser.add_argument("--ipc-timeout-sec", type=float)
    nav_parser.set_defaults(handler=_run_nav)

    arm_parser = subparsers.add_parser(
        "arm",
        help="Send one IF-DEL-003 ArmManipulation action.",
    )
    arm_parser.add_argument("--arm-id", required=True)
    arm_parser.add_argument("--task-id", required=True)
    arm_parser.add_argument(
        "--transfer-direction",
        required=True,
        choices=ALLOWED_TRANSFER_DIRECTIONS,
    )
    arm_parser.add_argument("--item-id", required=True)
    arm_parser.add_argument("--quantity", required=True, type=int)
    arm_parser.add_argument("--robot-slot-id", required=True)
    arm_parser.add_argument(
        "--ipc-timeout-sec",
        type=float,
        default=DEFAULT_ARM_IPC_TIMEOUT_SEC,
    )
    arm_parser.set_defaults(handler=_run_arm)

    return parser


def run(argv=None, *, command_client=None, stdout=None, stderr=None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    client = command_client or UnixDomainSocketCommandClient()

    try:
        response = args.handler(args, client)
    except (ValueError, RuntimeError, RosServiceCommandError, json.JSONDecodeError) as exc:
        _write_json(
            {
                "result_code": "FAILED",
                "reason_code": "ROS_ACTION_TEST_ERROR",
                "result_message": str(exc),
            },
            stderr,
        )
        return 1

    _write_json(response, stdout)
    return 0


def main(argv=None):
    raise SystemExit(run(argv))


def _run_status(args, command_client):
    pinky_id = _optional_text(args.pinky_id)
    arm_ids = [_require_text(arm_id, field_name="arm_id") for arm_id in args.arm_ids]
    if not pinky_id and not arm_ids:
        raise ValueError("status requires --pinky-id or at least one --arm-id.")

    payload = {"arm_ids": arm_ids}
    if pinky_id:
        payload["pinky_id"] = pinky_id
        payload["include_navigation"] = True
    else:
        payload["include_navigation"] = False

    return command_client.send_command(
        "get_runtime_status",
        payload,
        timeout=args.ipc_timeout_sec,
    )


def _run_nav(args, command_client):
    timeout_sec = int(args.timeout_sec)
    if timeout_sec <= 0:
        raise ValueError("--timeout-sec must be greater than 0.")

    goal = {
        "task_id": _require_text(args.task_id, field_name="task_id"),
        "nav_phase": _require_text(args.nav_phase, field_name="nav_phase"),
        "goal_pose": _load_goal_pose(args),
        "timeout_sec": timeout_sec,
    }
    ipc_timeout_sec = (
        float(args.ipc_timeout_sec)
        if args.ipc_timeout_sec is not None
        else timeout_sec + DEFAULT_NAVIGATION_IPC_TIMEOUT_BUFFER_SEC
    )

    return command_client.send_command(
        "navigate_to_goal",
        {
            "pinky_id": _require_text(args.pinky_id, field_name="pinky_id"),
            "goal": goal,
        },
        timeout=ipc_timeout_sec,
    )


def _run_arm(args, command_client):
    quantity = int(args.quantity)
    if quantity <= 0:
        raise ValueError("--quantity must be greater than 0.")

    return command_client.send_command(
        "execute_manipulation",
        {
            "arm_id": _require_text(args.arm_id, field_name="arm_id"),
            "goal": {
                "task_id": _require_text(args.task_id, field_name="task_id"),
                "transfer_direction": _require_text(
                    args.transfer_direction,
                    field_name="transfer_direction",
                ),
                "item_id": _require_text(args.item_id, field_name="item_id"),
                "quantity": quantity,
                "robot_slot_id": _require_text(args.robot_slot_id, field_name="robot_slot_id"),
            },
        },
        timeout=args.ipc_timeout_sec,
    )


def _load_goal_pose(args) -> dict:
    if args.pose_json:
        return normalize_goal_pose_spec(
            json.loads(args.pose_json),
            env_name="--pose-json",
        )
    return parse_goal_pose_string(args.pose, env_name="--pose")


def _require_text(value, *, field_name: str) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _optional_text(value) -> str:
    return str(value or "").strip()


def _write_json(payload, stream) -> None:
    json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
    stream.write("\n")


if __name__ == "__main__":
    main()
