import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
    build_frame,
    encode_frame,
    read_frame_from_socket,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOST = "127.0.0.1"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return sock.getsockname()[1]


def wait_for_server_ready(server_process, server_port: int, app, timeout: float = 10.0):
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
            app.processEvents()
            time.sleep(0.1)

    raise TimeoutError("Control server did not become ready in time.")


@pytest.fixture(scope="session")
def ros_service_stub(tmp_path_factory):
    socket_path = tmp_path_factory.mktemp("ros-runtime") / "ropi_ros_service.sock"
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
                        elif request.get("command") == "cancel_action":
                            payload = request.get("payload") or {}
                            response = {
                                "ok": True,
                                "payload": {
                                    "result_code": "CANCEL_REQUESTED",
                                    "result_message": "action cancel request was accepted.",
                                    "task_id": payload.get("task_id"),
                                    "action_name": payload.get("action_name"),
                                    "cancel_requested": True,
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


@pytest.fixture
def ai_fall_stream_server():
    server_port = find_free_port()
    ready = threading.Event()
    subscribed = threading.Event()
    push_requested = threading.Event()
    stop_requested = threading.Event()
    finished = threading.Event()
    requests = []
    request_lock = threading.Lock()

    def run_server():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.bind((SERVER_HOST, server_port))
                server_sock.listen(1)
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
                            request_frame = read_frame_from_socket(conn)
                        except Exception:
                            continue

                        payload = (
                            request_frame.payload
                            if isinstance(request_frame.payload, dict)
                            else {}
                        )
                        with request_lock:
                            requests.append(payload)

                        ack_frame = build_frame(
                            MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
                            request_frame.sequence_no,
                            {
                                "result_code": "ACCEPTED",
                                "result_message": None,
                                "accepted_consumer_id": payload.get("consumer_id"),
                                "subscribed_pinky_id": payload.get("pinky_id"),
                            },
                            is_response=True,
                        )
                        try:
                            conn.sendall(encode_frame(ack_frame))
                        except BrokenPipeError:
                            continue

                        subscribed.set()
                        while not stop_requested.is_set():
                            if push_requested.wait(timeout=0.1):
                                break

                        if stop_requested.is_set():
                            break

                        push_frame = build_frame(
                            MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
                            541,
                            {
                                "batch_end_seq": 541,
                                "results": [
                                    {
                                        "result_seq": 541,
                                        "pinky_id": "pinky3",
                                        "frame_id": "541",
                                        "frame_ts": "2026-04-30T06:09:38Z",
                                        "fall_detected": True,
                                        "confidence": 0.94,
                                        "fall_streak_ms": 1000,
                                        "alert_candidate": True,
                                        "evidence_image_id": "it-pat-005-evidence-541",
                                        "evidence_image_available": True,
                                    }
                                ],
                            },
                            is_push=True,
                        )
                        try:
                            conn.sendall(encode_frame(push_frame))
                        except BrokenPipeError:
                            continue

                        while not stop_requested.wait(timeout=0.1):
                            pass
        finally:
            finished.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    assert ready.wait(timeout=5), "fake AI fall stream server did not become ready"

    try:
        yield {
            "host": SERVER_HOST,
            "port": server_port,
            "requests": requests,
            "request_lock": request_lock,
            "subscribed": subscribed,
            "push_requested": push_requested,
        }
    finally:
        stop_requested.set()
        push_requested.set()
        try:
            with socket.create_connection((SERVER_HOST, server_port), timeout=0.2):
                pass
        except OSError:
            pass
        server_thread.join(timeout=5)
        assert finished.is_set()


@pytest.fixture(scope="session")
def ai_evidence_server():
    server_port = find_free_port()
    ready = threading.Event()
    stop_requested = threading.Event()
    finished = threading.Event()
    requests = []
    request_lock = threading.Lock()

    def run_server():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.bind((SERVER_HOST, server_port))
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
                            request_frame = read_frame_from_socket(conn)
                        except Exception:
                            continue

                        payload = (
                            request_frame.payload
                            if isinstance(request_frame.payload, dict)
                            else {}
                        )
                        with request_lock:
                            requests.append(payload)

                        response_frame = build_frame(
                            MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
                            request_frame.sequence_no,
                            {
                                "result_code": "OK",
                                "result_message": None,
                                "evidence_image_id": payload.get("evidence_image_id"),
                                "result_seq": payload.get("result_seq"),
                                "frame_id": "front_cam_frame_541",
                                "frame_ts": "2026-04-30T06:09:38Z",
                                "image_format": "jpeg",
                                "image_encoding": "base64",
                                "image_data": "/9j/AA==",
                                "image_width_px": 640,
                                "image_height_px": 480,
                                "detections": [
                                    {
                                        "class_name": "fall",
                                        "confidence": 0.87,
                                        "bbox_xyxy": [120, 88, 430, 360],
                                    }
                                ],
                            },
                            is_response=True,
                        )
                        try:
                            conn.sendall(encode_frame(response_frame))
                        except BrokenPipeError:
                            continue
        finally:
            finished.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    assert ready.wait(timeout=5), "fake AI evidence server did not become ready"

    try:
        yield {
            "host": SERVER_HOST,
            "port": server_port,
            "requests": requests,
            "request_lock": request_lock,
        }
    finally:
        stop_requested.set()
        try:
            with socket.create_connection((SERVER_HOST, server_port), timeout=0.2):
                pass
        except OSError:
            pass
        server_thread.join(timeout=5)
        assert finished.is_set()


@pytest.fixture
def control_server_with_ai_fall_stream(qapp, ros_service_stub, ai_fall_stream_server):
    server_port = find_free_port()
    server_process = _start_control_server(
        server_port=server_port,
        ros_socket_path=ros_service_stub["socket_path"],
        extra_env={
            "AI_FALL_STREAM_ENABLED": "true",
            "AI_FALL_STREAM_HOST": ai_fall_stream_server["host"],
            "AI_FALL_STREAM_PORT": str(ai_fall_stream_server["port"]),
            "AI_FALL_STREAM_CONSUMER_ID": "control_service_ai_fall",
            "AI_FALL_STREAM_LAST_SEQ": "0",
            "AI_FALL_STREAM_CONNECT_TIMEOUT_SEC": "5.0",
            "AI_FALL_STREAM_RECONNECT_DELAY_SEC": "0.2",
        },
    )

    wait_for_server_ready(server_process, server_port, qapp)
    yield from _yield_control_server(server_process, server_port)


@pytest.fixture(scope="session")
def control_server(qapp, ros_service_stub, ai_evidence_server):
    server_port = find_free_port()
    server_process = _start_control_server(
        server_port=server_port,
        ros_socket_path=ros_service_stub["socket_path"],
        extra_env={
            "AI_FALL_EVIDENCE_HOST": ai_evidence_server["host"],
            "AI_FALL_EVIDENCE_PORT": str(ai_evidence_server["port"]),
            "AI_FALL_EVIDENCE_CONNECT_TIMEOUT_SEC": "5.0",
        },
    )

    wait_for_server_ready(server_process, server_port, qapp)
    yield from _yield_control_server(server_process, server_port)


def _start_control_server(*, server_port, ros_socket_path, extra_env):
    return subprocess.Popen(
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
            "ROPI_ROS_SERVICE_SOCKET_PATH": ros_socket_path,
            "ROPI_DELIVERY_GOAL_POSE_SOURCE": "db",
            **extra_env,
        },
    )


def _yield_control_server(server_process, server_port):
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
