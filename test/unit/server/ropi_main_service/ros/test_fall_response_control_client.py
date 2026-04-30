import asyncio

from server.ropi_main_service.ros.fall_response_control_client import (
    RclpyFallResponseControlClient,
)


class FakeServiceType:
    class Request:
        def __init__(self):
            self.task_id = ""
            self.command_type = ""


class FakeResponse:
    def __init__(self):
        self.accepted = True
        self.message = ""

    @classmethod
    def get_fields_and_field_types(cls):
        return {
            "accepted": "bool",
            "message": "string",
        }


class ImmediateFuture:
    def __init__(self, result):
        self._result = result

    def add_done_callback(self, callback):
        callback(self)

    def result(self):
        return self._result


class FakeServiceClient:
    def __init__(self):
        self.requests = []

    def wait_for_service(self, timeout_sec=None):
        return True

    def service_is_ready(self):
        return True

    def call_async(self, request):
        self.requests.append(request)
        return ImmediateFuture(FakeResponse())


def test_fall_response_control_client_builds_request_and_reads_response():
    service_client = FakeServiceClient()
    client = RclpyFallResponseControlClient(
        node=object(),
        service_type_loader=lambda: FakeServiceType,
        service_client_factory=lambda node, service_type, service_name: service_client,
    )

    response = client.call(
        service_name="/ropi/control/pinky3/fall_response_control",
        request={
            "task_id": "2001",
            "command_type": "START_FALL_ALERT",
        },
    )

    assert response == {
        "accepted": True,
        "message": "",
    }
    assert service_client.requests[0].task_id == "2001"
    assert service_client.requests[0].command_type == "START_FALL_ALERT"


def test_fall_response_control_client_async_call_uses_ready_service():
    service_client = FakeServiceClient()
    client = RclpyFallResponseControlClient(
        node=object(),
        service_type_loader=lambda: FakeServiceType,
        service_client_factory=lambda node, service_type, service_name: service_client,
    )

    response = asyncio.run(
        client.async_call(
            service_name="/ropi/control/pinky3/fall_response_control",
            request={
                "task_id": "2001",
                "command_type": "CLEAR_AND_RESTART",
            },
        )
    )

    assert response["accepted"] is True
    assert service_client.requests[0].command_type == "CLEAR_AND_RESTART"
