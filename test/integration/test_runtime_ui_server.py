import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from server.ropi_main_service.persistence.connection import fetch_one
from server.ropi_main_service.persistence.repositories.task_request_repository import DeliveryRequestRepository
from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from ui.utils.network import tcp_client
from ui.utils.network.service_clients import DeliveryRequestRemoteService
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


@pytest.fixture(scope="session")
def control_server(qapp, ros_service_stub):
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
            "ROPI_DELIVERY_DESTINATION_GOAL_POSES": (
                "delivery_room_301=12.0,2.0,0.0"
            ),
            "ROPI_RETURN_TO_DOCK_GOAL_POSE": "0.5,0.5,3.14",
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


def test_server_process_heartbeat_reports_db_status(patched_ui_endpoint):
    response = send_request("HEARTBEAT", {"check_db": True}, timeout=5.0)

    assert response["ok"] is True
    assert response["payload"]["message"] == "메인 서버 연결 정상"
    assert response["payload"]["db"]["ok"] is True


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
            lambda: page.delivery_form.submit_thread is None,
            timeout=10.0,
        )
        assert submitted is True, "Delivery submit worker did not finish."
        assert page.delivery_form.status_label.isVisible() is True
        assert "접수되었습니다" in page.delivery_form.status_label.text()
    finally:
        page.close()
        SessionManager.logout()
        wait_for_qt(qapp, lambda: True, timeout=0.1)
