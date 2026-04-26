from server.ropi_main_service.ipc.config import get_ros_service_ipc_config
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def send_goal(self, *, action_name, goal):
        return {
            "action_name": action_name,
            "goal": goal,
        }


def test_ros_service_ipc_config_reads_socket_values_from_env(monkeypatch):
    monkeypatch.setenv("ROPI_ROS_SERVICE_SOCKET_PATH", "/tmp/test-ropi.sock")
    monkeypatch.setenv("ROPI_ROS_SERVICE_SOCKET_TIMEOUT", "2.5")

    config = get_ros_service_ipc_config()

    assert config == {
        "socket_path": "/tmp/test-ropi.sock",
        "timeout": 2.5,
    }


def test_unix_domain_socket_command_client_uses_env_defaults(monkeypatch):
    monkeypatch.setenv("ROPI_ROS_SERVICE_SOCKET_PATH", "/tmp/test-ropi.sock")
    monkeypatch.setenv("ROPI_ROS_SERVICE_SOCKET_TIMEOUT", "2.5")

    client = UnixDomainSocketCommandClient()

    assert client.socket_path == "/tmp/test-ropi.sock"
    assert client.timeout == 2.5


def test_ros_service_uds_server_uses_env_socket_path(monkeypatch):
    monkeypatch.setenv("ROPI_ROS_SERVICE_SOCKET_PATH", "/tmp/test-ropi.sock")

    server = RosServiceUdsServer(goal_pose_action_client=FakeGoalPoseActionClient())

    assert server.socket_path == "/tmp/test-ropi.sock"
