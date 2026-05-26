import math

import pytest

from server.ropi_main_service.ros.initial_pose_publisher import InitialPosePublisher


class FakeStamp:
    sec = 1776554120
    nanosec = 0


class FakeClockNow:
    def to_msg(self):
        return FakeStamp()


class FakeClock:
    def now(self):
        return FakeClockNow()


class FakeHeader:
    def __init__(self):
        self.stamp = None
        self.frame_id = ""


class FakePosition:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class FakeOrientation:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 1.0


class FakePose:
    def __init__(self):
        self.position = FakePosition()
        self.orientation = FakeOrientation()


class FakePoseWithCovariance:
    def __init__(self):
        self.pose = FakePose()
        self.covariance = []


class FakePoseWithCovarianceStamped:
    def __init__(self):
        self.header = FakeHeader()
        self.pose = FakePoseWithCovariance()


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class FakeNode:
    def __init__(self):
        self.publisher_calls = []
        self.publishers = {}

    def get_clock(self):
        return FakeClock()

    def create_publisher(self, message_type, topic, qos_profile):
        publisher = FakePublisher()
        self.publisher_calls.append(
            {
                "message_type": message_type,
                "topic": topic,
                "qos_profile": qos_profile,
            }
        )
        self.publishers[topic] = publisher
        return publisher


def test_initial_pose_publisher_publishes_namespaced_pose_with_covariance():
    node = FakeNode()
    publisher = InitialPosePublisher(
        node=node,
        message_type=FakePoseWithCovarianceStamped,
    )

    response = publisher.publish_initial_pose(
        robot_id="pinky1",
        frame_id="map",
        x=1.25,
        y=-0.5,
        yaw=math.pi / 2,
    )

    assert response == {
        "result_code": "ACCEPTED",
        "robot_id": "pinky1",
        "topic": "/pinky1/initialpose",
        "frame_id": "map",
        "x": 1.25,
        "y": -0.5,
        "yaw": math.pi / 2,
    }
    assert node.publisher_calls == [
        {
            "message_type": FakePoseWithCovarianceStamped,
            "topic": "/pinky1/initialpose",
            "qos_profile": 10,
        }
    ]

    message = node.publishers["/pinky1/initialpose"].messages[0]
    assert isinstance(message.header.stamp, FakeStamp)
    assert message.header.frame_id == "map"
    assert message.pose.pose.position.x == 1.25
    assert message.pose.pose.position.y == -0.5
    assert message.pose.pose.position.z == 0.0
    assert message.pose.pose.orientation.x == 0.0
    assert message.pose.pose.orientation.y == 0.0
    assert message.pose.pose.orientation.z == pytest.approx(math.sin(math.pi / 4))
    assert message.pose.pose.orientation.w == pytest.approx(math.cos(math.pi / 4))
    assert len(message.pose.covariance) == 36
    assert message.pose.covariance[0] == 0.25
    assert message.pose.covariance[7] == 0.25
    assert message.pose.covariance[35] == pytest.approx(0.0685)


def test_initial_pose_publisher_reuses_publisher_for_same_robot():
    node = FakeNode()
    publisher = InitialPosePublisher(
        node=node,
        message_type=FakePoseWithCovarianceStamped,
    )

    publisher.publish_initial_pose(robot_id="pinky1", x=0.0, y=0.0, yaw=0.0)
    publisher.publish_initial_pose(robot_id="pinky1", x=0.1, y=0.2, yaw=0.3)

    assert len(node.publisher_calls) == 1
    assert len(node.publishers["/pinky1/initialpose"].messages) == 2
