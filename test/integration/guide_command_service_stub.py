#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from ropi_interface.srv import GuideCommand


class GuideCommandServiceStub(Node):
    """Device-side stub for IF-GUI-004 integration testing."""

    def __init__(self):
        super().__init__("guide_command_service_stub")

        self.declare_parameter("pinky_id", "pinky1")
        self.declare_parameter("service_name", "")
        self.declare_parameter("accepted", True)
        self.declare_parameter("reason_code", "")
        self.declare_parameter("message", "guide command accepted")

        pinky_id = str(self.get_parameter("pinky_id").value).strip() or "pinky1"
        service_name = str(self.get_parameter("service_name").value).strip()
        if not service_name:
            service_name = f"/ropi/control/{pinky_id}/guide_command"

        self._accepted = bool(self.get_parameter("accepted").value)
        self._reason_code = str(self.get_parameter("reason_code").value).strip()
        self._message = str(self.get_parameter("message").value).strip() or "guide command accepted"

        self.create_service(GuideCommand, service_name, self._handle_request)
        self.get_logger().info(f"GuideCommand stub ready on {service_name}")

    def _handle_request(self, request, response):
        response.accepted = self._accepted
        response.reason_code = self._reason_code
        response.message = self._message

        self.get_logger().info(
            "IF-GUI-004 request received: "
            f"task_id={request.task_id}, command_type={request.command_type}, "
            f"target_track_id={request.target_track_id or '-'}, "
            f"wait_timeout_sec={request.wait_timeout_sec}, "
            f"finish_reason={request.finish_reason or '-'}"
        )
        return response


def main(args=None):
    rclpy.init(args=args)
    node = GuideCommandServiceStub()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
