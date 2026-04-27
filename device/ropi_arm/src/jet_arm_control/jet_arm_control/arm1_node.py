#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
arm1_node.py

[역할]
- 관제로부터 arm 작업 명령을 Action으로 받는다.
- 현재는 적재 작업 1회 수행 기준으로 동작한다.
- transfer_direction, item_id, robot_slot_id는 현재 단계에서는 수신만 하고
  실제 동작 분기에는 사용하지 않는다.
- quantity는 현재 1개 테스트 기준이라, 0이면 1로 간주하고
  성공 시 processed_quantity를 1로 반환한다.

[통신]
- 관제 -> Arm
  /ropi/arm/{arm_id}/execute_manipulation   (ArmManipulation Action)

- Arm -> 관제
  Action Result(result_code / processed_quantity)

- 보조 상태 토픽
  /{arm_id}/status
"""

import sys
sys.path.append('/home/jetcobot/venv/vcobot/lib/python3.12/site-packages')

import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String

from pymycobot.mycobot280 import MyCobot280

from ropi_interface.action import ArmManipulation


class Arm1Node(Node):
    def __init__(self):
        super().__init__("jet_arm_node")

        self.declare_parameter("arm_id", "arm1")
        self.declare_parameter("port", "/dev/ttyJETCOBOT")
        self.declare_parameter("baud", 1000000)

        self.arm_id = str(self.get_parameter("arm_id").value).strip() or "arm1"
        self.port = str(self.get_parameter("port").value).strip() or "/dev/ttyJETCOBOT"
        self.baud = int(self.get_parameter("baud").value)
        self.action_name = f"/ropi/arm/{self.arm_id}/execute_manipulation"
        self.status_topic = f"/{self.arm_id}/status"

        self.is_busy = False
        self.lock = threading.Lock()
        self.cb_group = ReentrantCallbackGroup()

        # 상태 토픽
        self.status_pub = self.create_publisher(
            String,
            self.status_topic,
            10
        )

        # 로봇 연결
        self.mc = MyCobot280(self.port, self.baud)
        self.mc.thread_lock = True

        self.get_logger().info(f"{self.arm_id} connected.")
        self.get_logger().info(f"Port: {self.port}")

        # 액션 서버
        self.action_server = ActionServer(
            self,
            ArmManipulation,
            self.action_name,
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        self.get_logger().info(f"{self.arm_id} manipulation action server READY: {self.action_name}")

    # ==================================================
    # 상태 발행
    # ==================================================
    def publish_status(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(f"[{self.arm_id.upper()} STATUS] {text}")

    # ==================================================
    # goal 수락 여부
    # ==================================================
    def goal_callback(self, goal_request):
        self.get_logger().info(
            f"[{self.arm_id.upper()} GOAL RECEIVED] "
            f"task_id={goal_request.task_id}, "
            f"transfer_direction={goal_request.transfer_direction}, "
            f"item_id={goal_request.item_id}, "
            f"quantity={goal_request.quantity}, "
            f"robot_slot_id={goal_request.robot_slot_id}"
        )

        with self.lock:
            if self.is_busy:
                self.get_logger().warn(f"{self.arm_id} is busy.")
                return GoalResponse.REJECT

            self.is_busy = True

        return GoalResponse.ACCEPT

    # ==================================================
    # cancel 처리
    # ==================================================
    def cancel_callback(self, goal_handle):
        self.get_logger().warn("Cancel accepted.")
        return CancelResponse.ACCEPT

    # ==================================================
    # 실제 작업 수행
    # ==================================================
    def execute_callback(self, goal_handle):
        result = ArmManipulation.Result()
        feedback = ArmManipulation.Feedback()

        try:
            request = goal_handle.request

            # 현재 단계에서는 quantity가 0이어도 1개로 처리
            target_quantity = request.quantity if request.quantity > 0 else 1
            processed_quantity = 0

            self.publish_status(f"{self.arm_id.upper()}_WORKING")

            speed = 50
            speed_slow = 20

            # -----------------------------
            # 1단계
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [1.23, 120.76, -145.28, 140.0, 7.82, 4.21]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            # -----------------------------
            # 2단계
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [0, 0, 0, 0, 0, 0]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            # -----------------------------
            # 3단계
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [-104.85, -10.89, -9.93, -24.96, -0.43, 66.79]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            # -----------------------------
            # 집기 접근
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [-109.59, -57.21, -9.75, -10.01, 1.58, 68.37]
            self.mc.send_angles(angles, speed_slow)
            time.sleep(1)

            # -----------------------------
            # 그리퍼 닫기
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            self.mc.set_gripper_value(30, speed_slow)
            time.sleep(1)

            # -----------------------------
            # 물체 들어올리기
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [-111.35, 6.59, -17.66, -10.81, 8.34, 75.93]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            # -----------------------------
            # 배치 위치 이동
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [-77.6, -31.9, -18.1, -29.44, 1.93, 95.71]
            self.mc.send_angles(angles, speed_slow)
            time.sleep(1)

            # -----------------------------
            # 그리퍼 열기
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            self.mc.set_gripper_value(100, speed_slow)
            time.sleep(1)

            # -----------------------------
            # 원위치 복귀
            # -----------------------------
            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            angles = [0, 0, 0, 0, 0, 0]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            angles = [1.23, 120.76, -145.28, 140.0, 7.82, 4.21]
            self.mc.send_angles(angles, speed)
            time.sleep(1)

            # 현재는 1개 처리 완료로 간주
            processed_quantity = min(1, target_quantity)

            feedback.processed_quantity = processed_quantity
            goal_handle.publish_feedback(feedback)

            self.publish_status(f"{self.arm_id.upper()}_DONE")

            result.result_code = "SUCCESS"
            result.result_message = ""
            result.processed_quantity = processed_quantity
            goal_handle.succeed()
            return result

        except Exception as e:
            self.get_logger().error(f"{self.arm_id} task failed: {e}")
            self.publish_status(f"{self.arm_id.upper()}_FAILED")

            result.result_code = "FAILED"
            result.result_message = str(e)
            result.processed_quantity = 0
            goal_handle.abort()
            return result

        finally:
            with self.lock:
                self.is_busy = False

    # ==================================================
    # 종료 처리
    # ==================================================
    def destroy_node(self):
        self.get_logger().info("Destroying Jet arm node...")
        self.action_server.destroy()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = Arm1Node()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().warn("KeyboardInterrupt detected.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
