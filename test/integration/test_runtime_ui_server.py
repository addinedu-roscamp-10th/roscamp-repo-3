import os
import socket
import subprocess
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from server.ropi_db.connection import fetch_one
from server.ropi_db.repositories.task_request_repository import DeliveryRequestRepository
from ui.utils.network.service_clients import DeliveryRequestRemoteService
from ui.utils.session.session_manager import SessionManager, UserSession
from ui.utils.network.tcp_client import send_request
from ui.utils.pages.caregiver.task_request_page import TaskRequestPage


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOST = "127.0.0.1"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return sock.getsockname()[1]


class RuntimeUIServerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.server_port = _find_free_port()
        cls.server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "server.ropi_main_service.tcp_server",
                "--host",
                SERVER_HOST,
                "--port",
                str(cls.server_port),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        cls._wait_for_server_ready()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "server_process", None) is None:
            return

        if cls.server_process.poll() is None:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()
                cls.server_process.wait(timeout=5)

        if cls.server_process.stdout:
            cls.server_process.stdout.close()
        if cls.server_process.stderr:
            cls.server_process.stderr.close()

    @classmethod
    def _wait_for_server_ready(cls, timeout: float = 10.0):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if cls.server_process.poll() is not None:
                stdout, stderr = cls.server_process.communicate(timeout=1)
                raise RuntimeError(
                    "Control server exited during startup.\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )

            try:
                with socket.create_connection((SERVER_HOST, cls.server_port), timeout=0.2):
                    return
            except OSError:
                cls.app.processEvents()
                time.sleep(0.1)

        raise TimeoutError("Control server did not become ready in time.")

    @contextmanager
    def patched_ui_endpoint(self):
        with (
            patch("ui.utils.network.tcp_client.CONTROL_SERVER_HOST", SERVER_HOST),
            patch("ui.utils.network.tcp_client.CONTROL_SERVER_PORT", self.server_port),
            patch("ui.utils.network.tcp_client.CONTROL_SERVER_TIMEOUT", 5.0),
        ):
            yield

    def wait_for_qt(self, predicate, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.05)

        self.app.processEvents()
        return predicate()

    def build_if_del_001_payload(self) -> dict:
        products = DeliveryRequestRepository().get_all_products()
        if not products:
            self.fail("The remote DB has no supply rows for IF-DEL-001 integration testing.")

        product = products[0]

        caregiver_row = self._safe_fetch_one(
            "SELECT CAST(caregiver_id AS CHAR) AS caregiver_id FROM caregiver LIMIT 1"
        )
        destination_row = self._safe_fetch_one(
            "SELECT CAST(location_id AS CHAR) AS destination_id FROM map_table LIMIT 1"
        )

        return {
            "request_id": "runtime-if-del-001",
            "caregiver_id": (
                caregiver_row["caregiver_id"] if caregiver_row else "cg_runtime_test"
            ),
            "item_id": product.get("item_id") or f"supply_{product['product_id']}",
            "quantity": 1,
            "destination_id": (
                destination_row["destination_id"] if destination_row else "destination_runtime_test"
            ),
            "priority": "NORMAL",
            "notes": "runtime integration test",
            "idempotency_key": "runtime-if-del-001-idem",
        }

    def build_runtime_caregiver_session(self) -> UserSession:
        payload = self.build_if_del_001_payload()
        return UserSession(
            user_id=payload["caregiver_id"],
            name="runtime-caregiver",
            role="caregiver",
        )

    def _safe_fetch_one(self, query: str):
        try:
            return fetch_one(query)
        except Exception:
            return None

    def test_server_process_heartbeat_reports_db_status(self):
        with self.patched_ui_endpoint():
            response = send_request("HEARTBEAT", {"check_db": True}, timeout=5.0)

        self.assertTrue(response["ok"])
        self.assertEqual(response["payload"]["message"], "메인 서버 연결 정상")
        self.assertTrue(response["payload"]["db"]["ok"])

    def test_ui_client_create_delivery_task_hits_real_server(self):
        payload = self.build_if_del_001_payload()

        with self.patched_ui_endpoint():
            response = DeliveryRequestRemoteService().create_delivery_task(**payload)

        self.assertEqual(response["result_code"], "ACCEPTED")
        self.assertTrue(response["task_id"].startswith("task_delivery_"))
        self.assertEqual(response["task_status"], "WAITING_DISPATCH")
        self.assertIsNone(response["assigned_pinky_id"])

    def test_task_request_page_loads_items_from_real_server(self):
        with self.patched_ui_endpoint():
            page = TaskRequestPage()
            page.show()

            try:
                loaded = self.wait_for_qt(
                    lambda: (
                        page.delivery_form.load_thread is None
                        and page.delivery_form.item_combo.count() > 0
                    ),
                    timeout=10.0,
                )

                self.assertTrue(loaded, "TaskRequestPage did not finish loading items.")
                self.assertTrue(page.delivery_form.item_combo.isEnabled())
                self.assertTrue(page.delivery_form.submit_btn.isEnabled())
                self.assertNotEqual(
                    page.delivery_form.item_combo.itemText(0),
                    "물품 목록 불러오기 실패",
                )
                self.assertNotEqual(
                    page.delivery_form.item_combo.itemText(0),
                    "등록된 물품 없음",
                )
            finally:
                page.close()
                self.wait_for_qt(lambda: True, timeout=0.1)

    def test_task_request_page_submit_request_hits_if_del_001(self):
        with self.patched_ui_endpoint():
            SessionManager.login(self.build_runtime_caregiver_session())
            page = TaskRequestPage()
            page.show()

            try:
                loaded = self.wait_for_qt(
                    lambda: (
                        page.delivery_form.load_thread is None
                        and page.delivery_form.item_combo.count() > 0
                        and page.delivery_form.item_combo.isEnabled()
                    ),
                    timeout=10.0,
                )
                self.assertTrue(loaded, "TaskRequestPage did not finish loading items.")

                page.delivery_form.quantity_input.setValue(2)
                page.delivery_form.priority_combo.setCurrentText("긴급")
                page.delivery_form.destination_combo.setCurrentIndex(0)
                page.delivery_form.detail_input.setPlainText("runtime submit test")
                page.delivery_form.submit_request()

                submitted = self.wait_for_qt(
                    lambda: page.delivery_form.submit_thread is None,
                    timeout=10.0,
                )
                self.assertTrue(submitted, "Delivery submit worker did not finish.")
                self.assertTrue(page.delivery_form.status_label.isVisible())
                self.assertIn("접수되었습니다", page.delivery_form.status_label.text())
            finally:
                page.close()
                SessionManager.logout()
                self.wait_for_qt(lambda: True, timeout=0.1)


if __name__ == "__main__":
    unittest.main()
