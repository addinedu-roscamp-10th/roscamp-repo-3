#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from threading import Lock

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

from ropi_interface.action import NavigateToGoal

#운반팀 노드 SOO
class PinkyAMRNode(Node):

    def __init__(self):
        super().__init__("pinky_amr_node")

        self.declare_parameter("robot_id", "pinky2")
        self.declare_parameter("action_name", "")
        self.declare_parameter("status_topic", "/transport/amr_status")
        self.declare_parameter("current_goal_topic", "/transport/current_goal")
        self.declare_parameter("active_task_topic", "/ropi/robots/{robot_id}/active_task_id")
        self.declare_parameter("state_publish_period_sec", 0.5)

        self.robot_id = str(self.get_parameter("robot_id").value).strip() or "pinky2"
        configured_action_name = str(self.get_parameter("action_name").value).strip()
        self.action_name = configured_action_name or f"/ropi/control/{self.robot_id}/navigate_to_goal"
        self.status_topic = str(self.get_parameter("status_topic").value).strip() or "/transport/amr_status"
        self.current_goal_topic = (
            str(self.get_parameter("current_goal_topic").value).strip()
            or "/transport/current_goal"
        )
        self.active_task_topic = self._resolve_robot_topic("active_task_topic")
        self.state_publish_period_sec = float(self.get_parameter("state_publish_period_sec").value)

        self.cb_group = ReentrantCallbackGroup()
        self.lock = Lock()

        self.is_busy = False
        self.current_state = "IDLE"

        # 상태 토픽
        self.status_pub = self.create_publisher(
            String,
            self.status_topic,
            10
        )

        # 현재 목표 토픽
        self.goal_pub = self.create_publisher(
            PoseStamped,
            self.current_goal_topic,
            10
        )
        self.active_task_pub = self.create_publisher(
            String,
            self.active_task_topic,
            10
        )

        self.timer = self.create_timer(
            self.state_publish_period_sec,
            self.publish_state
        )

        # Nav2
        self.navigator = BasicNavigator()

        self.get_logger().info("Waiting Nav2...")
        self.navigator.waitUntilNav2Active()
        self.get_logger().info("Nav2 ACTIVE")

        # 액션 서버
        self.action_server = ActionServer(
            self,
            NavigateToGoal,
            self.action_name,
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        self.get_logger().info(
            f"READY robot_id={self.robot_id} action={self.action_name} "
            f"active_task_topic={self.active_task_topic}"
        )

    # -----------------------------------
    # 상태 발행
    # -----------------------------------
    def publish_state(self):
        msg = String()
        msg.data = self.current_state
        self.status_pub.publish(msg)

    def set_state(self, state):
        self.current_state = state
        self.get_logger().info(f"[STATE] {state}")

    def publish_active_task_id(self, task_id):
        msg = String()
        msg.data = str(task_id or "").strip()
        self.active_task_pub.publish(msg)

    def _resolve_robot_topic(self, parameter_name):
        value = str(self.get_parameter(parameter_name).value).strip()
        if "{robot_id}" in value:
            return value.format(robot_id=self.robot_id)
        return value

    # -----------------------------------
    # Goal 수락 여부
    # -----------------------------------
    def goal_callback(self, goal_request):

        with self.lock:
            if self.is_busy:
                return GoalResponse.REJECT

            self.is_busy = True

        self.get_logger().info(
            f"GOAL RECEIVED "
            f"task_id={goal_request.task_id}, "
            f"nav_phase={goal_request.nav_phase}"
        )
        self.publish_active_task_id(goal_request.task_id)

        return GoalResponse.ACCEPT

    # -----------------------------------
    # Cancel
    # -----------------------------------
    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    # -----------------------------------
    # 실행
    # -----------------------------------
    def execute_callback(self, goal_handle):

        result = NavigateToGoal.Result()
        feedback = NavigateToGoal.Feedback()

        try:
            goal_pose = goal_handle.request.goal_pose

            if goal_pose.header.frame_id == "":
                goal_pose.header.frame_id = "map"

            goal_pose.header.stamp = self.get_clock().now().to_msg()

            self.goal_pub.publish(goal_pose)

            self.set_state("MOVING")

            # Nav2 시작
            self.navigator.goToPose(goal_pose)

            while rclpy.ok() and not self.navigator.isTaskComplete():

                # 취소 요청
                if goal_handle.is_cancel_requested:
                    self.navigator.cancelTask()
                    goal_handle.canceled()

                    result.result_code = "FAILED"
                    return result

                # feedback
                nav_fb = self.navigator.getFeedback()

                feedback.nav_status = "MOVING"
                feedback.current_pose = goal_pose
                feedback.distance_remaining_m = 0.0

                if nav_fb is not None:
                    dist = getattr(
                        nav_fb,
                        "distance_remaining",
                        0.0
                    )
                    feedback.distance_remaining_m = float(dist)

                goal_handle.publish_feedback(feedback)

                time.sleep(0.2)

            # 결과
            nav_result = self.navigator.getResult()

            if nav_result == TaskResult.SUCCEEDED:

                goal_handle.succeed()

                self.set_state("ARRIVED")

                result.result_code = "SUCCESS"

            else:

                goal_handle.abort()

                self.set_state("FAILED")

                result.result_code = "FAILED"

            result.result_message = ""
            result.final_pose = goal_pose
            result.finished_at = self.get_clock().now().to_msg()

            return result

        except Exception as e:

            goal_handle.abort()

            result.result_code = "FAILED"
            result.result_message = str(e)
            result.final_pose = PoseStamped()
            result.finished_at = self.get_clock().now().to_msg()

            return result

        finally:
            with self.lock:
                self.is_busy = False
            self.publish_active_task_id("")

    # -----------------------------------
    # 종료
    # -----------------------------------
    def destroy_node(self):
        try:
            self.navigator.cancelTask()
        except:
            pass

        self.action_server.destroy()
        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = PinkyAMRNode()

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
