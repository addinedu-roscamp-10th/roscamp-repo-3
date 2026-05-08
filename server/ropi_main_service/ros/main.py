import argparse
import asyncio
import signal
import threading
from contextlib import suppress

from server.ropi_main_service.observability import configure_logging
from server.ropi_main_service.ros.guide_command_client import RclpyGuideCommandClient
from server.ropi_main_service.ros.goal_pose_action_client import RclpyGoalPoseActionClient
from server.ropi_main_service.ros.fall_response_control_client import RclpyFallResponseControlClient
from server.ropi_main_service.ros.manipulation_action_client import RclpyManipulationActionClient
from server.ropi_main_service.ros.patrol_path_action_client import RclpyPatrolPathActionClient
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer
from server.ropi_main_service.persistence.background_db_writer import (
    get_default_background_db_writer,
)


def parse_args():
    parser = argparse.ArgumentParser(description="ROPI ROS service UDS adapter")
    parser.add_argument("--node-name", default="ropi_ros_service")
    return parser.parse_args()


async def _run_ros_service(node_name: str):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init()
    node = rclpy.create_node(node_name)
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    goal_pose_action_client = RclpyGoalPoseActionClient(node=node)
    manipulation_action_client = RclpyManipulationActionClient(node=node)
    patrol_path_action_client = RclpyPatrolPathActionClient(node=node)
    fall_response_control_client = RclpyFallResponseControlClient(node=node)
    guide_command_client = RclpyGuideCommandClient(node=node)
    guide_runtime_subscriber = _build_guide_runtime_subscriber(node)
    db_writer = get_default_background_db_writer()
    db_writer.start()
    status_runtime_subscriber = _build_status_runtime_subscriber(
        node,
        loop=asyncio.get_running_loop(),
        db_writer=db_writer,
    )
    uds_server = RosServiceUdsServer(
        goal_pose_action_client=goal_pose_action_client,
        manipulation_action_client=manipulation_action_client,
        patrol_path_action_client=patrol_path_action_client,
        fall_response_control_client=fall_response_control_client,
        guide_command_client=guide_command_client,
        guide_runtime_subscriber=guide_runtime_subscriber,
    )
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_shutdown():
        shutdown_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, _request_shutdown)

    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    await uds_server.start()
    print(f"ROPI ROS Service listening on {uds_server.socket_path}", flush=True)

    try:
        await shutdown_event.wait()
    finally:
        await uds_server.close()
        executor.shutdown()
        await db_writer.stop()
        node.destroy_node()
        rclpy.shutdown()
        spin_thread.join(timeout=5)


def _build_guide_runtime_subscriber(node):
    try:
        from server.ropi_main_service.ros.guide_runtime_subscriber import (
            GuideRuntimeSubscriber,
        )
    except ImportError as exc:
        node.get_logger().warning(
            "Guide runtime subscriber disabled because GuidePhaseSnapshot "
            f"interface is unavailable: {exc}"
        )
        return None
    return GuideRuntimeSubscriber(node=node)


def _build_status_runtime_subscriber(node, *, loop, db_writer):
    try:
        from server.ropi_main_service.ros.status_runtime_subscriber import (
            StatusRuntimeSubscriber,
        )
    except ImportError as exc:
        node.get_logger().warning(
            f"Status runtime subscriber disabled because interface is unavailable: {exc}"
        )
        return None
    return StatusRuntimeSubscriber(node=node, loop=loop, db_writer=db_writer)


def main():
    args = parse_args()
    configure_logging()
    asyncio.run(_run_ros_service(args.node_name))


if __name__ == "__main__":
    main()
