import asyncio

from server.ropi_main_service.application.caregiver_rpc_facade import (
    CaregiverRpcFacade,
)


class FakeCaregiverService:
    def get_dashboard_summary(self):
        return {"available_robot_count": 1, "waiting_job_count": 0, "running_job_count": 1}

    async def async_get_dashboard_summary(self):
        return self.get_dashboard_summary()

    def get_robot_board_data(self):
        return []

    async def async_get_robot_board_data(self):
        return self.get_robot_board_data()

    def get_flow_board_data(self):
        return {
            "WAITING": [],
            "ASSIGNED": [],
            "IN_PROGRESS": [
                {
                    "task_id": 101,
                    "task_status": "RUNNING",
                    "description": "delivery task",
                }
            ],
            "CANCELING": [],
            "DONE": [],
        }

    async def async_get_flow_board_data(self):
        return self.get_flow_board_data()

    def get_timeline_data(self):
        return []

    async def async_get_timeline_data(self):
        return self.get_timeline_data()

    def get_robot_status_bundle(self):
        return {
            "summary": {"total_robot_count": 1},
            "robots": [{"robot_id": "pinky2"}],
            "delivery_composition": [],
        }

    def get_alert_log_bundle(self, **filters):
        return {
            "summary": {"total_event_count": 1},
            "events": [{"event_id": 11}],
            "filters": filters,
        }


class FakeActionFeedbackService:
    def get_latest_feedback(self, *, task_id):
        return {
            "result_code": "FOUND",
            "task_id": str(task_id),
            "feedback": [
                {
                    "client": "navigation",
                    "feedback_type": "NAVIGATION_FEEDBACK",
                    "payload": {
                        "nav_status": "MOVING",
                        "distance_remaining_m": 1.25,
                    },
                }
            ],
        }

    async def async_get_latest_feedback(self, *, task_id):
        return self.get_latest_feedback(task_id=task_id)


def test_caregiver_rpc_facade_attaches_action_feedback_to_dashboard_tasks():
    facade = CaregiverRpcFacade(
        service=FakeCaregiverService(),
        action_feedback_service=FakeActionFeedbackService(),
    )

    bundle = facade.get_dashboard_bundle()

    task = bundle["flow_data"]["IN_PROGRESS"][0]
    assert task["feedback"]["feedback_type"] == "NAVIGATION_FEEDBACK"
    assert task["feedback_summary"] == "MOVING / 남은 거리 1.25m"


def test_caregiver_rpc_facade_async_dashboard_keeps_response_shape():
    facade = CaregiverRpcFacade(
        service=FakeCaregiverService(),
        action_feedback_service=FakeActionFeedbackService(),
    )

    bundle = asyncio.run(facade.async_get_dashboard_bundle())

    assert sorted(bundle) == ["flow_data", "robots", "summary", "timeline_rows"]
    assert bundle["flow_data"]["IN_PROGRESS"][0]["feedback_summary"] == (
        "MOVING / 남은 거리 1.25m"
    )


def test_caregiver_rpc_facade_exposes_robot_and_alert_bundles():
    facade = CaregiverRpcFacade(
        service=FakeCaregiverService(),
        action_feedback_service=FakeActionFeedbackService(),
    )

    assert facade.get_robot_status_bundle()["robots"] == [{"robot_id": "pinky2"}]
    assert facade.get_alert_log_bundle(period="LAST_24_HOURS")["filters"] == {
        "period": "LAST_24_HOURS",
    }
