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
    guide_tracking_update_publisher = _build_guide_tracking_update_publisher(node)
    uds_server = RosServiceUdsServer(
        goal_pose_action_client=goal_pose_action_client,
        manipulation_action_client=manipulation_action_client,
        patrol_path_action_client=patrol_path_action_client,
        fall_response_control_client=fall_response_control_client,
        guide_command_client=guide_command_client,
        guide_runtime_subscriber=guide_runtime_subscriber,
        guide_tracking_update_publisher=guide_tracking_update_publisher,
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


def _build_guide_tracking_update_publisher(node):
    try:
        from server.ropi_main_service.ros.guide_tracking_update_publisher import (
            RclpyGuideTrackingUpdatePublisher,
        )
        return RclpyGuideTrackingUpdatePublisher(node=node)
    except ImportError as exc:
        node.get_logger().warning(
            "Guide tracking update publisher disabled because GuideTrackingUpdate "
            f"interface is unavailable: {exc}"
        )
        return None


def main():
    args = parse_args()
    configure_logging()
    asyncio.run(_run_ros_service(args.node_name))


if __name__ == "__main__":
    main()
