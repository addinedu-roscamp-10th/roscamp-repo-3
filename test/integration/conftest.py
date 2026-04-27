import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
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


@pytest.fixture(scope="session")
def ros_service_stub(tmp_path_factory):
    socket_dir = PROJECT_ROOT / ".pytest_tmp" / "ros-runtime"
    socket_dir.mkdir(parents=True, exist_ok=True)
    socket_path = socket_dir / "ropi_ros_service.sock"
    ready = threading.Event()
    stop_requested = threading.Event()
    finished = threading.Event()

    def run_server():
        if socket_path.exists():
            socket_path.unlink()

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server_sock:
                server_sock.bind(str(socket_path))
                server_sock.listen(5)
                server_sock.settimeout(0.2)
                ready.set()

                while not stop_requested.is_set():
                    try:
                        conn, _ = server_sock.accept()
                    except TimeoutError:
                        continue
                    except OSError:
                        break

                    with conn:
                        try:
                            request = decode_message_bytes(conn.recv(4096))
                        except Exception:
                            continue

                        if request.get("command") == "get_runtime_status":
                            response = {
                                "ok": True,
                                "payload": {
                                    "ready": True,
                                    "checks": [
                                        {"name": "pinky2.navigate_to_goal", "ready": True},
                                        {"name": "arm1.execute_manipulation", "ready": True},
                                        {"name": "arm2.execute_manipulation", "ready": True},
                                    ],
                                },
                            }
                        else:
                            response = {
                                "ok": True,
                                "payload": {
                                    "accepted": True,
                                    "status": 4,
                                    "result_code": "SUCCESS",
                                    "result_message": "done",
                                },
                            }

                        try:
                            conn.sendall(encode_message(response))
                        except BrokenPipeError:
                            continue
        finally:
            finished.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    assert ready.wait(timeout=5), "fake ros service did not become ready"

    try:
        yield {"socket_path": str(socket_path)}
    finally:
        stop_requested.set()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client_sock:
                client_sock.connect(str(socket_path))
                client_sock.sendall(encode_message({"command": "shutdown_probe", "payload": {}}))
        except OSError:
            pass
        server_thread.join(timeout=5)
        if socket_path.exists():
            socket_path.unlink()
        assert finished.is_set()


@pytest.fixture(scope="session")
def control_server(ros_service_stub):
    server_port = _find_free_port()
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
            "ROPI_ROS_SERVICE_SOCKET_PATH": ros_service_stub["socket_path"],
            "ROPI_DELIVERY_PICKUP_GOAL_POSE": "1.5,2.5,1.57",
            "ROPI_DELIVERY_DESTINATION_GOAL_POSES": "room2=12.0,2.0,0.0",
            "ROPI_RETURN_TO_DOCK_GOAL_POSE": "0.5,0.5,3.14",
        },
    )

    _wait_for_server_ready(server_process, server_port)

    try:
        yield {
            "port": server_port,
            "process": server_process,
        }
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


@pytest.fixture
def patched_ui_endpoint(control_server, monkeypatch):
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_HOST", SERVER_HOST)
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_PORT", control_server["port"])
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_TIMEOUT", 5.0)
    return control_server
