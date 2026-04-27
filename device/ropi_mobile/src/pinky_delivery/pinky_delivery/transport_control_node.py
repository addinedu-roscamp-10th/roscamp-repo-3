#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped

from ropi_interface.action import NavigateToGoal
from ropi_interface.action import ArmManipulation


class TransportControlNode(Node):

    def __init__(self):
        super().__init__("transport_control_node")

        self.cb_group = ReentrantCallbackGroup()
        self.lock = Lock()

        self.control_state = "IDLE"
        self.sequence_state = "IDLE"

        self.current_amr_target = ""

        # -----------------------------------
        # 고정 좌표
        # -----------------------------------
        self.room1_goal = self.make_pose(
            0.1665755,
            -0.4496830,
            90.0
        )

        self.room2_goal = self.make_pose(
            1.6946025,
            0.0043433,
            0.0
        )

        self.home_goal = self.make_pose(
            0.8577123,
            0.2559725,
            0.0
        )

        # -----------------------------------
        # START 명령
        # -----------------------------------
        self.manual_sub = self.create_subscription(
            String,
            "/control/manual_cmd",
            self.manual_cmd_callback,
            10
        )

        self.state_pub = self.create_publisher(
            String,
            "/control/state",
            10
        )

        self.timer = self.create_timer(
            0.5,
            self.publish_state
        )

        # -----------------------------------
        # Action Clients
        # -----------------------------------

        # AMR
        self.amr_client = ActionClient(
            self,
            NavigateToGoal,
            "/ropi/control/navigate_to_goal"
        )

        # ARM1
        self.arm1_client = ActionClient(
            self,
            ArmManipulation,
            "/ropi/arm/arm1/execute_manipulation"
        )

        # ARM2
        self.arm2_client = ActionClient(
            self,
            ArmManipulation,
            "/ropi/arm/arm2/execute_manipulation"
        )

        self.get_logger().info("Waiting servers...")

        self.amr_client.wait_for_server()
        self.arm1_client.wait_for_server()
        self.arm2_client.wait_for_server()

        self.get_logger().info("ALL ACTION SERVER CONNECTED")

    # ==================================================
    # 유틸
    # ==================================================
    def publish_state(self):
        msg = String()
        msg.data = self.control_state
        self.state_pub.publish(msg)

    def set_state(self, text):
        self.control_state = text
        self.get_logger().info(f"[STATE] {text}")

    def make_pose(self, x, y, yaw_deg):

        pose = PoseStamped()
        pose.header.frame_id = "map"

        yaw = math.radians(yaw_deg)

        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0

        pose.pose.orientation.z = math.sin(yaw/2)
        pose.pose.orientation.w = math.cos(yaw/2)

        return pose

    # ==================================================
    # START
    # ==================================================
    def manual_cmd_callback(self, msg):

        cmd = msg.data.strip().upper()

        if cmd == "START":
            self.start_sequence()

        elif cmd == "RESET":
            self.sequence_state = "IDLE"
            self.set_state("IDLE")

    def start_sequence(self):

        if self.sequence_state not in ["IDLE", "DONE"]:
            self.get_logger().warn("Already running")
            return

        self.sequence_state = "MOVING_TO_ROOM1"
        self.set_state("MOVING_TO_ROOM1")

        self.send_amr_goal(
            self.room1_goal,
            "ROOM1"
        )

    # ==================================================
    # AMR
    # ==================================================
    def send_amr_goal(self, pose, target_name):

        goal = NavigateToGoal.Goal()

        goal.task_id = ""
        goal.nav_phase = ""
        goal.goal_pose = pose
        goal.timeout_sec = 0

        self.current_amr_target = target_name

        future = self.amr_client.send_goal_async(
            goal,
            feedback_callback=self.amr_feedback_callback
        )

        future.add_done_callback(
            self.amr_goal_response_callback
        )

    def amr_goal_response_callback(self, future):

        goal_handle = future.result()

        if not goal_handle.accepted:
            self.set_state("AMR_REJECTED")
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            self.amr_result_callback
        )

    def amr_feedback_callback(self, feedback_msg):

        fb = feedback_msg.feedback

        self.get_logger().info(
            f"[AMR FB] "
            f"{fb.nav_status}, "
            f"remain={fb.distance_remaining_m:.2f}"
        )

    def amr_result_callback(self, future):

        wrapped = future.result()
        result = wrapped.result

        if result.result_code != "SUCCESS":
            self.set_state("AMR_FAILED")
            return

        target = self.current_amr_target

        # ROOM1 도착
        if target == "ROOM1":

            self.set_state("ARM1_WORKING")
            self.send_arm1_goal()

        # ROOM2 도착
        elif target == "ROOM2":

            self.set_state("ARM2_WORKING")
            self.send_arm2_goal()

        # HOME 도착
        elif target == "HOME":

            self.sequence_state = "DONE"
            self.set_state("DONE")

    # ==================================================
    # ARM1
    # ==================================================
    def send_arm1_goal(self):

        goal = ArmManipulation.Goal()

        goal.task_id = ""
        goal.transfer_direction = ""
        goal.item_id = ""
        goal.quantity = 1
        goal.robot_slot_id = ""

        future = self.arm1_client.send_goal_async(
            goal,
            feedback_callback=self.arm1_feedback_callback
        )

        future.add_done_callback(
            self.arm1_goal_response_callback
        )

    def arm1_goal_response_callback(self, future):

        gh = future.result()

        if not gh.accepted:
            self.set_state("ARM1_REJECTED")
            return

        result_future = gh.get_result_async()
        result_future.add_done_callback(
            self.arm1_result_callback
        )

    def arm1_feedback_callback(self, feedback_msg):

        fb = feedback_msg.feedback

        self.get_logger().info(
            f"[ARM1 FB] processed={fb.processed_quantity}"
        )

    def arm1_result_callback(self, future):

        wrapped = future.result()
        result = wrapped.result

        if result.result_code != "SUCCESS":
            self.set_state("ARM1_FAILED")
            return

        self.set_state("MOVING_TO_ROOM2")

        self.send_amr_goal(
            self.room2_goal,
            "ROOM2"
        )

    # ==================================================
    # ARM2
    # ==================================================
    def send_arm2_goal(self):

        goal = ArmManipulation.Goal()

        goal.task_id = ""
        goal.transfer_direction = ""
        goal.item_id = ""
        goal.quantity = 1
        goal.robot_slot_id = ""

        future = self.arm2_client.send_goal_async(
            goal,
            feedback_callback=self.arm2_feedback_callback
        )

        future.add_done_callback(
            self.arm2_goal_response_callback
        )

    def arm2_goal_response_callback(self, future):

        gh = future.result()

        if not gh.accepted:
            self.set_state("ARM2_REJECTED")
            return

        result_future = gh.get_result_async()
        result_future.add_done_callback(
            self.arm2_result_callback
        )

    def arm2_feedback_callback(self, feedback_msg):

        fb = feedback_msg.feedback

        self.get_logger().info(
            f"[ARM2 FB] processed={fb.processed_quantity}"
        )

    def arm2_result_callback(self, future):

        wrapped = future.result()
        result = wrapped.result

        if result.result_code != "SUCCESS":
            self.set_state("ARM2_FAILED")
            return

        self.set_state("RETURNING_HOME")

        self.send_amr_goal(
            self.home_goal,
            "HOME"
        )


def main(args=None):

    rclpy.init(args=args)

    node = TransportControlNode()

    executor = MultiThreadedExecutor(
        num_threads=4
    )

    executor.add_node(node)

    try:
        executor.spin()

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()