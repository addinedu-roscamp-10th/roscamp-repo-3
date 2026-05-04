from server.ropi_main_service.ros.guide_command_client import RclpyGuideCommandClient


def test_guide_command_client_default_deadlines_fit_ui_tcp_timeout():
    client = RclpyGuideCommandClient(node=object())

    assert client.server_wait_timeout_sec == 1.0
    assert client.response_wait_timeout_sec == 1.0
