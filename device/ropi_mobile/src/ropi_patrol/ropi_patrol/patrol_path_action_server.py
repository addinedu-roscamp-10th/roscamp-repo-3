#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from threading import Lock

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from ropi_interface.action import ExecutePatrolPath


class PatrolPathActionServer(Node):
    def __init__(self):
        super().__init__("patrol_path_action_server")

        self.declare_parameter("robot_id", "pinky3")
        self.declare_parameter("action_name", "")
        self.declare_parameter("nav_check_interval_sec", 0.2)

        self.robot_id = str(self.get_parameter("robot_id").value).strip() or "pinky3"
        configured_action_name = str(self.get_parameter("action_name").value).strip()
        self.action_name = configured_action_name or f"/ropi/control/{self.robot_id}/execute_patrol_path"
        self.nav_check_interval_sec = float(self.get_parameter("nav_check_interval_sec").value)

        self.callback_group = ReentrantCallbackGroup()
        self.lock = Lock()
        self.is_busy = False

        self.navigator = BasicNavigator()
        self.get_logger().info("Waiting Nav2...")
        self.navigator.waitUntilNav2Active()
        self.get_logger().info("Nav2 ACTIVE")

        self.action_server = ActionServer(
            self,
            ExecutePatrolPath,
            self.action_name,
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.callback_group,
        )
        self.get_logger().info(f"READY robot_id={self.robot_id} action={self.action_name}")

    def goal_callback(self, goal_request):
        waypoint_count = len(getattr(goal_request.path, "poses", []) or [])
        with self.lock:
            if self.is_busy:
                return GoalResponse.REJECT
            if waypoint_count <= 0:
                self.get_logger().warning(
                    f"PATROL GOAL REJECTED task_id={goal_request.task_id}, waypoints=0"
                )
                return GoalResponse.REJECT
            self.is_busy = True

        self.get_logger().info(
            f"PATROL GOAL RECEIVED task_id={goal_request.task_id}, waypoints={waypoint_count}"
        )
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle):
        result = ExecutePatrolPath.Result()
        feedback = ExecutePatrolPath.Feedback()
        completed_count = 0
        final_pose = PoseStamped()

        try:
            path = goal_handle.request.path
            poses = list(path.poses or [])
            if not poses:
                goal_handle.abort()
                result.result_code = "REJECTED"
                result.result_message = "patrol path has no waypoint."
                result.completed_waypoint_count = 0
                result.final_pose = final_pose
                result.finished_at = self.get_clock().now().to_msg()
                return result

            total = len(poses)
            for index, target_pose in enumerate(poses):
                if not target_pose.header.frame_id:
                    target_pose.header.frame_id = path.header.frame_id or "map"
                target_pose.header.stamp = self.get_clock().now().to_msg()

                final_pose = target_pose
                self.navigator.goToPose(target_pose)

                while rclpy.ok() and not self.navigator.isTaskComplete():
                    if goal_handle.is_cancel_requested:
                        self.navigator.cancelTask()
                        goal_handle.canceled()
                        result.result_code = "CANCELED"
                        result.result_message = "patrol path canceled."
                        result.completed_waypoint_count = completed_count
                        result.final_pose = final_pose
                        result.finished_at = self.get_clock().now().to_msg()
                        return result

                    nav_feedback = self.navigator.getFeedback()
                    feedback.patrol_status = "MOVING"
                    feedback.current_waypoint_index = index
                    feedback.total_waypoints = total
                    feedback.current_pose = target_pose
                    feedback.distance_remaining_m = 0.0
                    if nav_feedback is not None:
                        feedback.distance_remaining_m = float(
                            getattr(nav_feedback, "distance_remaining", 0.0)
                        )
                    goal_handle.publish_feedback(feedback)
                    time.sleep(self.nav_check_interval_sec)

                nav_result = self.navigator.getResult()
                if nav_result == TaskResult.SUCCEEDED:
                    completed_count += 1
                    continue

                goal_handle.abort()
                result.result_code = "FAILED"
                result.result_message = f"patrol waypoint {index + 1} failed."
                result.completed_waypoint_count = completed_count
                result.final_pose = final_pose
                result.finished_at = self.get_clock().now().to_msg()
                return result

            goal_handle.succeed()
            result.result_code = "SUCCEEDED"
            result.result_message = "patrol path completed."
            result.completed_waypoint_count = completed_count
            result.final_pose = final_pose
            result.finished_at = self.get_clock().now().to_msg()
            return result

        except Exception as exc:
            goal_handle.abort()
            result.result_code = "FAILED"
            result.result_message = str(exc)
            result.completed_waypoint_count = completed_count
            result.final_pose = final_pose
            result.finished_at = self.get_clock().now().to_msg()
            return result
        finally:
            with self.lock:
                self.is_busy = False

    def destroy_node(self):
        try:
            self.navigator.cancelTask()
        except Exception:
            pass
        self.action_server.destroy()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PatrolPathActionServer()
    executor = MultiThreadedExecutor(num_threads=4)
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
