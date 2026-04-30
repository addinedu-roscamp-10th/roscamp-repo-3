import os
import json
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.repositories.task_request_repository import DeliveryRequestRepository
from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
    build_frame,
    encode_frame,
    read_frame_from_socket,
)
from ui.utils.network import tcp_client
from ui.utils.network.service_clients import (
    DeliveryRequestRemoteService,
    TaskMonitorRemoteService,
)
from ui.utils.network.tcp_client import send_request
from ui.utils.pages.caregiver.task_request_page import TaskRequestPage
from ui.utils.session.session_manager import SessionManager, UserSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOST = "127.0.0.1"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return sock.getsockname()[1]


def _wait_for_server_ready(server_process, server_port: int, app: QApplication, timeout: float = 10.0):
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


def wait_for_qt(app: QApplication, predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)

    app.processEvents()
    return predicate()


def wait_for_condition(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)

    return predicate()


def _safe_fetch_one(query: str):
    try:
        return fetch_one(query)
    except Exception:
        return None


def build_if_del_001_payload() -> dict:
    products = DeliveryRequestRepository().get_all_products()
    assert products, "The remote DB has no item rows for IF-DEL-001 integration testing."

    product = products[0]

    caregiver_row = _safe_fetch_one(
        "SELECT CAST(caregiver_id AS CHAR) AS caregiver_id FROM caregiver LIMIT 1"
    )
    return {
        "request_id": "runtime-if-del-001",
        "caregiver_id": (
            caregiver_row["caregiver_id"] if caregiver_row else "1"
        ),
        "item_id": product["item_id"],
        "quantity": 1,
        "destination_id": "delivery_room_301",
        "priority": "NORMAL",
        "notes": "runtime integration test",
        "idempotency_key": "runtime-if-del-001-idem",
    }


def build_runtime_caregiver_session() -> UserSession:
    payload = build_if_del_001_payload()
    return UserSession(
        user_id=payload["caregiver_id"],
        name="runtime-caregiver",
        role="caregiver",
    )


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


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
    server_port = _find_free_port()
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
    server_port = _find_free_port()
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
            "ROPI_DELIVERY_GOAL_POSE_SOURCE": "db",
            "AI_FALL_STREAM_ENABLED": "true",
            "AI_FALL_STREAM_HOST": ai_fall_stream_server["host"],
            "AI_FALL_STREAM_PORT": str(ai_fall_stream_server["port"]),
            "AI_FALL_STREAM_CONSUMER_ID": "control_service_ai_fall",
            "AI_FALL_STREAM_LAST_SEQ": "0",
            "AI_FALL_STREAM_CONNECT_TIMEOUT_SEC": "5.0",
            "AI_FALL_STREAM_RECONNECT_DELAY_SEC": "0.2",
        },
    )

    _wait_for_server_ready(server_process, server_port, qapp)

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


@pytest.fixture(scope="session")
def control_server(qapp, ros_service_stub, ai_evidence_server):
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
            "ROPI_DELIVERY_GOAL_POSE_SOURCE": "db",
            "AI_FALL_EVIDENCE_HOST": ai_evidence_server["host"],
            "AI_FALL_EVIDENCE_PORT": str(ai_evidence_server["port"]),
            "AI_FALL_EVIDENCE_CONNECT_TIMEOUT_SEC": "5.0",
        },
    )

    _wait_for_server_ready(server_process, server_port, qapp)

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


@pytest.fixture
def fall_evidence_seed():
    robot_row = _safe_fetch_one("SELECT robot_id FROM robot WHERE robot_id = 'pinky3'")
    if robot_row is None:
        robot_row = _safe_fetch_one("SELECT robot_id FROM robot LIMIT 1")

    robot_id = robot_row["robot_id"] if robot_row else None
    evidence_image_id = f"it-fall-evidence-{uuid.uuid4().hex}"
    request_id = f"runtime-pat-007-{uuid.uuid4().hex}"
    result_seq = 541
    task_id = None

    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task
                (task_type, request_id, idempotency_key, requester_type, requester_id,
                 priority, task_status, phase, assigned_robot_id, latest_reason_code,
                 created_at, updated_at, started_at)
                VALUES
                ('PATROL', %s, %s, 'CAREGIVER', 'integration-test',
                 'NORMAL', 'RUNNING', 'WAIT_FALL_RESPONSE', %s, 'FALL_DETECTED',
                 NOW(3), NOW(3), NOW(3))
                """,
                (request_id, request_id, robot_id),
            )
            task_id = cursor.lastrowid
            payload = {
                "trigger_result": {
                    "result_seq": result_seq,
                    "frame_id": "front_cam_frame_541",
                    "fall_streak_ms": 1200,
                    "evidence_image_id": evidence_image_id,
                    "evidence_image_available": True,
                    "pinky_id": robot_id,
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                }
            }
            cursor.execute(
                """
                INSERT INTO task_event_log
                (task_id, event_name, severity, component, robot_id, correlation_id,
                 result_code, reason_code, message, payload_json, occurred_at, created_at)
                VALUES
                (%s, 'FALL_ALERT_CREATED', 'WARN', 'ai_fall_detector', %s, NULL,
                 'FALL_DETECTED', 'FALL_DETECTED', 'integration fall alert',
                 %s, NOW(3), NOW(3))
                """,
                (task_id, robot_id, json.dumps(payload, ensure_ascii=False)),
            )
            alert_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {
            "task_id": task_id,
            "alert_id": str(alert_id),
            "evidence_image_id": evidence_image_id,
            "result_seq": result_seq,
            "robot_id": robot_id,
        }
    finally:
        if task_id is not None:
            cleanup_conn = get_connection()
            try:
                with cleanup_conn.cursor() as cursor:
                    cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
            finally:
                cleanup_conn.close()


@pytest.fixture
def active_patrol_task_seed():
    robot_row = _safe_fetch_one("SELECT robot_id FROM robot WHERE robot_id = 'pinky3'")
    assert robot_row is not None, "The remote DB has no pinky3 robot row."

    patrol_area = _safe_fetch_one(
        "SELECT patrol_area_id, revision FROM patrol_area WHERE is_enabled = TRUE LIMIT 1"
    )
    assert patrol_area is not None, "The remote DB has no enabled patrol_area row."

    request_id = f"runtime-pat-005-{uuid.uuid4().hex}"
    task_id = None
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task
                (task_type, request_id, idempotency_key, requester_type, requester_id,
                 priority, task_status, phase, assigned_robot_id, latest_reason_code,
                 created_at, updated_at, started_at)
                VALUES
                ('PATROL', %s, %s, 'CAREGIVER', 'integration-test',
                 'NORMAL', 'RUNNING', 'FOLLOW_PATROL_PATH', 'pinky3', NULL,
                 NOW(3), NOW(3), NOW(3))
                """,
                (request_id, request_id),
            )
            task_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO patrol_task_detail
                (task_id, patrol_area_id, patrol_area_revision, patrol_status,
                 frame_id, waypoint_count, current_waypoint_index, path_snapshot_json, notes)
                VALUES
                (%s, %s, %s, 'MOVING', 'map', 1, 0,
                 '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0}]}',
                 'runtime PAT-005 integration test')
                """,
                (task_id, patrol_area["patrol_area_id"], patrol_area["revision"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {"task_id": task_id}
    finally:
        if task_id is not None:
            cleanup_conn = get_connection()
            try:
                with cleanup_conn.cursor() as cursor:
                    cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
            finally:
                cleanup_conn.close()


def test_server_process_heartbeat_reports_db_status(patched_ui_endpoint):
    response = send_request("HEARTBEAT", {"check_db": True}, timeout=5.0)

    assert response["ok"] is True
    assert response["payload"]["message"] == "메인 서버 연결 정상"
    assert response["payload"]["db"]["ok"] is True


def test_control_server_subscribes_ai_fall_stream_and_starts_fall_alert(
    control_server_with_ai_fall_stream,
    ai_fall_stream_server,
    active_patrol_task_seed,
):
    assert control_server_with_ai_fall_stream["port"] > 0
    assert ai_fall_stream_server["subscribed"].wait(timeout=10)

    with ai_fall_stream_server["request_lock"]:
        requests = list(ai_fall_stream_server["requests"])

    assert requests
    assert requests[0]["consumer_id"] == "control_service_ai_fall"
    assert "pinky_id" not in requests[0]
    assert requests[0]["last_seq"] == 0

    ai_fall_stream_server["push_requested"].set()
    task_id = active_patrol_task_seed["task_id"]

    updated = wait_for_condition(
        lambda: (
            _safe_fetch_one(
                "SELECT phase FROM task "
                f"WHERE task_id = {int(task_id)}"
            )
            or {}
        ).get("phase")
        == "WAIT_FALL_RESPONSE",
        timeout=10.0,
    )
    if not updated:
        process = control_server_with_ai_fall_stream["process"]
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        pytest.fail(
            "Control Service did not process the PAT-005 push.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    task_row = _safe_fetch_one(
        "SELECT phase, latest_reason_code FROM task "
        f"WHERE task_id = {int(task_id)}"
    )
    patrol_row = _safe_fetch_one(
        "SELECT patrol_status FROM patrol_task_detail "
        f"WHERE task_id = {int(task_id)}"
    )
    inference_row = _safe_fetch_one(
        "SELECT robot_id, result_json FROM ai_inference_log "
        f"WHERE task_id = {int(task_id)} ORDER BY ai_inference_log_id DESC LIMIT 1"
    )

    assert task_row["phase"] == "WAIT_FALL_RESPONSE"
    assert task_row["latest_reason_code"] == "FALL_DETECTED"
    assert patrol_row["patrol_status"] == "WAITING_FALL_RESPONSE"
    assert inference_row["robot_id"] == "pinky3"
    assert json.loads(inference_row["result_json"])["pinky_id"] == "pinky3"


def test_ui_client_fall_evidence_query_hits_real_server_and_ai_mock(
    patched_ui_endpoint,
    fall_evidence_seed,
    ai_evidence_server,
):
    with ai_evidence_server["request_lock"]:
        request_count_before = len(ai_evidence_server["requests"])

    response = TaskMonitorRemoteService().get_fall_evidence_image(
        consumer_id="ui-integration-task-monitor",
        task_id=fall_evidence_seed["task_id"],
        alert_id=fall_evidence_seed["alert_id"],
        evidence_image_id=fall_evidence_seed["evidence_image_id"],
        result_seq=fall_evidence_seed["result_seq"],
    )

    assert response["result_code"] == "OK"
    assert response["task_id"] == fall_evidence_seed["task_id"]
    assert response["alert_id"] == fall_evidence_seed["alert_id"]
    assert response["evidence_image_id"] == fall_evidence_seed["evidence_image_id"]
    assert response["image_width_px"] == 640
    assert response["detections"][0]["class_name"] == "fall"

    with ai_evidence_server["request_lock"]:
        ai_requests = ai_evidence_server["requests"][request_count_before:]

    assert ai_requests == [
        {
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": fall_evidence_seed["evidence_image_id"],
            "result_seq": fall_evidence_seed["result_seq"],
            **(
                {"pinky_id": fall_evidence_seed["robot_id"]}
                if fall_evidence_seed["robot_id"]
                else {}
            ),
        }
    ]


def test_ui_client_create_delivery_task_hits_real_server(patched_ui_endpoint, runtime_delivery_schema):
    payload = build_if_del_001_payload()

    response = DeliveryRequestRemoteService().create_delivery_task(**payload)

    assert response["result_code"] == "ACCEPTED"
    assert isinstance(response["task_id"], int)
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["assigned_robot_id"] == "pinky2"


def test_task_request_page_loads_items_from_real_server(patched_ui_endpoint, qapp, runtime_delivery_schema):
    page = TaskRequestPage()
    page.show()

    try:
        loaded = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.load_thread is None
                and page.delivery_form.item_combo.count() > 0
            ),
            timeout=10.0,
        )

        assert loaded is True, "TaskRequestPage did not finish loading items."
        assert page.delivery_form.item_combo.isEnabled() is True
        assert page.delivery_form.submit_btn.isEnabled() is True
        assert page.delivery_form.item_combo.itemText(0) != "물품 목록 불러오기 실패"
        assert page.delivery_form.item_combo.itemText(0) != "등록된 물품 없음"
    finally:
        page.close()
        wait_for_qt(qapp, lambda: True, timeout=0.1)


def test_task_request_page_submit_request_hits_if_del_001(patched_ui_endpoint, qapp, runtime_delivery_schema):
    SessionManager.login(build_runtime_caregiver_session())
    page = TaskRequestPage()
    page.show()

    try:
        loaded = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.load_thread is None
                and page.delivery_form.item_combo.count() > 0
                and page.delivery_form.item_combo.isEnabled()
            ),
            timeout=10.0,
        )
        assert loaded is True, "TaskRequestPage did not finish loading items."

        page.delivery_form.quantity_input.setValue(2)
        page.delivery_form.priority_combo.setCurrentText("긴급")
        page.delivery_form.destination_combo.setCurrentIndex(0)
        page.delivery_form.detail_input.setPlainText("runtime submit test")
        page.delivery_form.submit_request()

        submitted = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.submit_thread is None
                and page.delivery_form.load_thread is None
            ),
            timeout=10.0,
        )
        assert submitted is True, "Delivery submit or refresh worker did not finish."
        assert page.delivery_form.status_label.isVisible() is True
        assert "접수되었습니다" in page.delivery_form.status_label.text()
    finally:
        page.close()
        SessionManager.logout()
        wait_for_qt(qapp, lambda: True, timeout=0.1)
