from PyQt6.QtCore import QObject, pyqtSignal

from ui.utils.network.service_clients import DeliveryRequestRemoteService


class TaskRequestOptionsLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            self.finished.emit(
                True,
                {
                    "items": service.get_delivery_items(),
                    "destinations": service.get_delivery_destinations(),
                    "patrol_areas": service.get_patrol_areas(),
                },
            )
        except Exception as exc:
            self.finished.emit(False, str(exc))


class DeliverySubmitWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.create_delivery_task(**self.payload) or {}
            result_code = str(response.get("result_code", "")).upper()
            self.finished.emit(result_code == "ACCEPTED", response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"물품 요청 처리 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": None,
                    "task_status": None,
                    "assigned_robot_id": None,
                },
            )


class PatrolSubmitWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.create_patrol_task(**self.payload) or {}
            result_code = str(response.get("result_code", "")).upper()
            self.finished.emit(result_code == "ACCEPTED", response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"순찰 요청 처리 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": None,
                    "task_status": None,
                    "assigned_robot_id": None,
                },
            )


class PatrolResumeWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.resume_patrol_task(**self.payload) or {}
            result_code = str(response.get("result_code", "")).upper()
            self.finished.emit(result_code == "ACCEPTED", response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"순찰 재개 요청 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": self.payload.get("task_id"),
                    "task_status": None,
                    "assigned_robot_id": None,
                },
            )


class DeliveryCancelWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, task_id):
        super().__init__()
        self.task_id = task_id

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.cancel_delivery_task(self.task_id) or {}
            result_code = str(response.get("result_code", "")).upper()
            success = bool(response.get("cancel_requested")) or result_code in {
                "CANCEL_REQUESTED",
                "CANCELLED",
            }
            self.finished.emit(success, response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"작업 취소 요청 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": self.task_id,
                    "task_status": None,
                    "assigned_robot_id": None,
                    "cancel_requested": False,
                },
            )


__all__ = [
    "DeliveryCancelWorker",
    "DeliverySubmitWorker",
    "PatrolResumeWorker",
    "PatrolSubmitWorker",
    "TaskRequestOptionsLoadWorker",
]
