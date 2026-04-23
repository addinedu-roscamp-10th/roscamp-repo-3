import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from ui.utils.network.service_clients import DeliveryRequestRemoteService
from ui.utils.network import tcp_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOST = "127.0.0.1"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return sock.getsockname()[1]


def _wait_for_server_ready(server_process, server_port: int, timeout: float = 10.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate(timeout=1)
            raise RuntimeError(
                "Control server exited during startup.\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            )

        try:
            with socket.create_connection((SERVER_HOST, server_port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)

    raise TimeoutError("Control server did not become ready in time.")


def test_if_del_001_runtime_wires_delivery_pickup_to_ros_service(tmp_path, monkeypatch):
    socket_path = tmp_path / "ropi_ros_service.sock"
    server_port = _find_free_port()
    received = {}
    ready = threading.Event()
    finished = threading.Event()

    def run_ros_service_stub():
        if socket_path.exists():
            socket_path.unlink()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server_sock:
            server_sock.bind(str(socket_path))
            server_sock.listen(1)
            ready.set()

            conn, _ = server_sock.accept()
            with conn:
                received["request"] = decode_message_bytes(conn.recv(4096))
                conn.sendall(
                    encode_message(
                        {
                            "ok": True,
                            "payload": {
                                "accepted": True,
                                "goal_handle_id": "goal_handle_001",
                            },
                        }
                    )
                )
        finished.set()

    ros_service_thread = threading.Thread(target=run_ros_service_stub, daemon=True)
    ros_service_thread.start()
    ready.wait(timeout=2)

    pickup_goal_pose = {
        "header": {
            "stamp": {"sec": 0, "nanosec": 0},
            "frame_id": "map",
        },
        "pose": {
            "position": {"x": 1.5, "y": 2.5, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }

    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "server.ropi_main_service.transport.tcp_server",
            "--host",
            SERVER_HOST,
            "--port",
            str(server_port),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "ROPI_ROS_SERVICE_SOCKET_PATH": str(socket_path),
            "ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON": json.dumps(pickup_goal_pose),
        },
    )

    _wait_for_server_ready(server_process, server_port)

    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_HOST", SERVER_HOST)
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_PORT", server_port)
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_TIMEOUT", 5.0)

    try:
        response = DeliveryRequestRemoteService().create_delivery_task(
            request_id="req_001",
            caregiver_id="cg_001",
            item_id="supply_001",
            quantity=1,
            destination_id="room_301",
            priority="NORMAL",
            notes="runtime pickup wire-up test",
            idempotency_key="idem_001",
        )
    finally:
        if server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=5)

        if server_process.stdout:
            server_process.stdout.close()
        if server_process.stderr:
            server_process.stderr.close()

    finished.wait(timeout=2)
    ros_service_thread.join(timeout=2)

    assert response["result_code"] == "ACCEPTED"
    assert received["request"] == {
        "command": "navigate_to_goal",
        "payload": {
            "pinky_id": "pinky2",
            "goal": {
                "task_id": "task_delivery_idem_001",
                "nav_phase": "DELIVERY_PICKUP",
                "goal_pose": pickup_goal_pose,
                "timeout_sec": 120,
            },
        },
    }
