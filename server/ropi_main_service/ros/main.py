import argparse
import asyncio
import signal
import threading
from contextlib import suppress

from server.ropi_main_service.observability import configure_logging
from server.ropi_main_service.ros.goal_pose_action_client import RclpyGoalPoseActionClient
from server.ropi_main_service.ros.manipulation_action_client import RclpyManipulationActionClient
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
    uds_server = RosServiceUdsServer(
        goal_pose_action_client=goal_pose_action_client,
        manipulation_action_client=manipulation_action_client,
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


def main():
    args = parse_args()
    configure_logging()
    asyncio.run(_run_ros_service(args.node_name))


if __name__ == "__main__":
    main()
