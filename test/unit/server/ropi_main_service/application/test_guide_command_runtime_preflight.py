import asyncio


class FakeReadinessService:
    def __init__(self, *, response):
        self.response = response

    def get_status(self):
        return self.response

    async def async_get_status(self):
        return self.response


def test_guide_command_runtime_preflight_checks_only_guide_command_endpoint():
    from server.ropi_main_service.application.guide_command_runtime_preflight import (
        GuideCommandRuntimePreflight,
    )

    calls = []

    def readiness_service_factory(**kwargs):
        calls.append(kwargs)
        return FakeReadinessService(
            response={
                "ready": True,
                "checks": [
                    {
                        "ready": True,
                        "service_name": "/ropi/control/pinky1/guide_command",
                    }
                ],
            }
        )

    preflight = GuideCommandRuntimePreflight(
        readiness_service_factory=readiness_service_factory,
        default_pinky_id="pinky1",
    )

    response = preflight.check(task_id=3001, pinky_id="pinky1")

    assert response["result_code"] == "ACCEPTED"
    assert response["pinky_id"] == "pinky1"
    assert response["guide_command_endpoint"] == "/ropi/control/pinky1/guide_command"
    assert calls[0]["include_navigation"] is False
    assert calls[0]["include_guide"] is True
    assert calls[0]["arm_ids"] == []


def test_guide_command_runtime_preflight_rejects_when_endpoint_is_missing():
    from server.ropi_main_service.application.guide_command_runtime_preflight import (
        GuideCommandRuntimePreflight,
    )

    def readiness_service_factory(**_kwargs):
        return FakeReadinessService(
            response={
                "ready": False,
                "checks": [
                    {
                        "ready": False,
                        "service_name": "/ropi/control/pinky1/guide_command",
                    }
                ],
            }
        )

    preflight = GuideCommandRuntimePreflight(
        readiness_service_factory=readiness_service_factory,
        default_pinky_id="pinky1",
    )

    response = preflight.check(task_id=3001, pinky_id="pinky1")

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_RUNTIME_NOT_READY"
    assert response["runtime_status"]["checks"][0]["service_name"] == (
        "/ropi/control/pinky1/guide_command"
    )


def test_guide_command_runtime_preflight_async_handles_transport_error():
    from server.ropi_main_service.application.guide_command_runtime_preflight import (
        GuideCommandRuntimePreflight,
    )

    def readiness_service_factory(**_kwargs):
        raise FileNotFoundError("socket missing")

    preflight = GuideCommandRuntimePreflight(
        readiness_service_factory=readiness_service_factory,
        default_pinky_id="pinky1",
    )

    response = asyncio.run(preflight.async_check(task_id=3001, pinky_id="pinky1"))

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_RUNTIME_NOT_READY"
    assert response["runtime_status"]["error"] == "socket missing"
