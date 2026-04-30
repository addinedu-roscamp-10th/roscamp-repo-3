#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from copy import deepcopy
from threading import Lock, Thread

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool

from ropi_interface.action import ExecutePatrolPath
from ropi_interface.srv import FallResponseControl


START_FALL_ALERT = "START_FALL_ALERT"
CLEAR_AND_RESTART = "CLEAR_AND_RESTART"
CLEAR_AND_STOP = "CLEAR_AND_STOP"
FALL_RESPONSE_COMMANDS = {START_FALL_ALERT, CLEAR_AND_RESTART, CLEAR_AND_STOP}


class PatrolPathActionServer(Node):
    def __init__(self):
        super().__init__("patrol_path_action_server")

        self.declare_parameter("robot_id", "pinky3")
        self.declare_parameter("action_name", "")
        self.declare_parameter("fall_response_service_name", "")
        self.declare_parameter("alarm_topic", "/fall_alarm")
        self.declare_parameter("nav_check_interval_sec", 0.2)

        self.robot_id = str(self.get_parameter("robot_id").value).strip() or "pinky3"
        configured_action_name = str(self.get_parameter("action_name").value).strip()
        configured_service_name = str(self.get_parameter("fall_response_service_name").value).strip()
        self.action_name = configured_action_name or f"/ropi/control/{self.robot_id}/execute_patrol_path"
        self.fall_response_service_name = (
            configured_service_name
            or f"/ropi/control/{self.robot_id}/fall_response_control"
        )
        self.alarm_topic = str(self.get_parameter("alarm_topic").value).strip() or "/fall_alarm"
        self.nav_check_interval_sec = float(self.get_parameter("nav_check_interval_sec").value)

        self.callback_group = ReentrantCallbackGroup()
        self.lock = Lock()
        self.is_busy = False
        self.active_task_id = None
        self.active_path = None
        self.active_waypoint_index = 0
        self.active_patrol_snapshot = None
        self.fall_response_active = False
        self.internal_restart_running = False
        self.stop_requested_task_id = None

        self.navigator = BasicNavigator()
        self.get_logger().info("Waiting Nav2...")
        self.navigator.waitUntilNav2Active()
        self.get_logger().info("Nav2 ACTIVE")
        self.alarm_pub = self.create_publisher(Bool, self.alarm_topic, 10)

        self.action_server = ActionServer(
            self,
            ExecutePatrolPath,
            self.action_name,
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.callback_group,
        )
        self.fall_response_service = self.create_service(
            FallResponseControl,
            self.fall_response_service_name,
            self.fall_response_callback,
            callback_group=self.callback_group,
        )
        self.get_logger().info(
            f"READY robot_id={self.robot_id} action={self.action_name} "
            f"fall_response_service={self.fall_response_service_name}"
        )

    def goal_callback(self, goal_request):
        waypoint_count = len(getattr(goal_request.path, "poses", []) or [])
        with self.lock:
            if self.is_busy or self.internal_restart_running:
                return GoalResponse.REJECT
            if waypoint_count <= 0:
                self.get_logger().warning(
                    f"PATROL GOAL REJECTED task_id={goal_request.task_id}, waypoints=0"
                )
                return GoalResponse.REJECT
            self.is_busy = True
            self.active_task_id = str(goal_request.task_id or "").strip()
            self.active_path = deepcopy(goal_request.path)
            self.active_waypoint_index = 0
            self.fall_response_active = False
            self.stop_requested_task_id = None

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
                with self.lock:
                    self.active_waypoint_index = index

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

                    if self._fall_response_requested_for(goal_handle.request.task_id):
                        self.navigator.cancelTask()
                        self._save_active_snapshot(
                            task_id=goal_handle.request.task_id,
                            path=path,
                            current_waypoint_index=index,
                        )
                        feedback.patrol_status = "WAITING_FALL_RESPONSE"
                        feedback.current_waypoint_index = index
                        feedback.total_waypoints = total
                        feedback.current_pose = target_pose
                        feedback.distance_remaining_m = -1.0
                        goal_handle.publish_feedback(feedback)
                        goal_handle.abort()
                        result.result_code = "CANCELED"
                        result.result_message = "patrol path paused for fall response."
                        result.completed_waypoint_count = completed_count
                        result.final_pose = final_pose
                        result.finished_at = self.get_clock().now().to_msg()
                        return result

                    if self._stop_requested_for(goal_handle.request.task_id):
                        self.navigator.cancelTask()
                        goal_handle.canceled()
                        result.result_code = "CANCELED"
                        result.result_message = "patrol path stopped."
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

                if self._fall_response_requested_for(goal_handle.request.task_id):
                    self._save_active_snapshot(
                        task_id=goal_handle.request.task_id,
                        path=path,
                        current_waypoint_index=index,
                    )
                    feedback.patrol_status = "WAITING_FALL_RESPONSE"
                    feedback.current_waypoint_index = index
                    feedback.total_waypoints = total
                    feedback.current_pose = target_pose
                    feedback.distance_remaining_m = -1.0
                    goal_handle.publish_feedback(feedback)
                    goal_handle.abort()
                    result.result_code = "CANCELED"
                    result.result_message = "patrol path paused for fall response."
                    result.completed_waypoint_count = completed_count
                    result.final_pose = final_pose
                    result.finished_at = self.get_clock().now().to_msg()
                    return result

                if self._stop_requested_for(goal_handle.request.task_id):
                    goal_handle.canceled()
                    result.result_code = "CANCELED"
                    result.result_message = "patrol path stopped."
                    result.completed_waypoint_count = completed_count
                    result.final_pose = final_pose
                    result.finished_at = self.get_clock().now().to_msg()
                    return result

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
                if not self.fall_response_active:
                    self.active_task_id = None
                    self.active_path = None
                    self.active_waypoint_index = 0
                    self.stop_requested_task_id = None

    def fall_response_callback(self, request, response):
        task_id = str(request.task_id or "").strip()
        command_type = str(request.command_type or "").strip().upper()

        if not task_id:
            response.accepted = False
            response.message = "task_id is required."
            return response

        if command_type not in FALL_RESPONSE_COMMANDS:
            response.accepted = False
            response.message = f"unsupported fall response command: {request.command_type}"
            return response

        if command_type == START_FALL_ALERT:
            return self._handle_start_fall_alert(task_id=task_id, response=response)

        if command_type == CLEAR_AND_RESTART:
            return self._handle_clear_and_restart(task_id=task_id, response=response)

        return self._handle_clear_and_stop(task_id=task_id, response=response)

    def _handle_start_fall_alert(self, *, task_id, response):
        with self.lock:
            active_task_id = str(self.active_task_id or "").strip()
            if active_task_id and active_task_id != task_id:
                response.accepted = False
                response.message = f"active patrol task mismatch: {active_task_id}"
                return response

            if not active_task_id and self.active_patrol_snapshot is None:
                response.accepted = False
                response.message = "active patrol snapshot does not exist."
                return response

            if self.active_path is not None:
                self._save_active_snapshot_locked(
                    task_id=task_id,
                    path=self.active_path,
                    current_waypoint_index=self.active_waypoint_index,
                )
            self.fall_response_active = True
            self.stop_requested_task_id = None

        self._publish_alarm(True)
        try:
            self.navigator.cancelTask()
        except Exception as exc:
            self.get_logger().warn(f"Failed to cancel Nav2 task for fall response: {exc}")

        response.accepted = True
        response.message = ""
        return response

    def _handle_clear_and_restart(self, *, task_id, response):
        with self.lock:
            snapshot = deepcopy(self.active_patrol_snapshot)
            if snapshot is None or snapshot.get("task_id") != task_id:
                response.accepted = False
                response.message = "active patrol snapshot does not exist."
                return response
            if self.internal_restart_running:
                response.accepted = False
                response.message = "patrol restart is already running."
                return response

            self.fall_response_active = False
            self.internal_restart_running = True
            self.stop_requested_task_id = None

        self._publish_alarm(False)
        restart_thread = Thread(
            target=self._run_internal_restart,
            args=(snapshot,),
            daemon=True,
        )
        restart_thread.start()

        response.accepted = True
        response.message = ""
        return response

    def _handle_clear_and_stop(self, *, task_id, response):
        with self.lock:
            active_task_id = str(self.active_task_id or "").strip()
            snapshot_task_id = ""
            if self.active_patrol_snapshot is not None:
                snapshot_task_id = str(
                    self.active_patrol_snapshot.get("task_id") or ""
                ).strip()

            if active_task_id and active_task_id != task_id:
                response.accepted = False
                response.message = f"active patrol task mismatch: {active_task_id}"
                return response

            if snapshot_task_id and snapshot_task_id != task_id:
                response.accepted = False
                response.message = f"active patrol task mismatch: {snapshot_task_id}"
                return response

            if (
                not active_task_id
                and not snapshot_task_id
                and not self.internal_restart_running
            ):
                response.accepted = False
                response.message = "active patrol snapshot does not exist."
                return response

            self.fall_response_active = False
            self.active_patrol_snapshot = None
            self.stop_requested_task_id = (
                task_id
                if active_task_id or self.internal_restart_running
                else None
            )
            if not active_task_id:
                self.active_task_id = None
                self.active_path = None
                self.active_waypoint_index = 0

        self._publish_alarm(False)
        try:
            self.navigator.cancelTask()
        except Exception as exc:
            self.get_logger().warn(
                f"Failed to cancel Nav2 task for fall response stop: {exc}"
            )

        response.accepted = True
        response.message = ""
        return response

    def _fall_response_requested_for(self, task_id):
        normalized_task_id = str(task_id or "").strip()
        with self.lock:
            return (
                self.fall_response_active
                and str(self.active_task_id or "").strip() == normalized_task_id
            )

    def _stop_requested_for(self, task_id):
        normalized_task_id = str(task_id or "").strip()
        with self.lock:
            return str(self.stop_requested_task_id or "").strip() == normalized_task_id

    def _save_active_snapshot(self, *, task_id, path, current_waypoint_index):
        with self.lock:
            self._save_active_snapshot_locked(
                task_id=task_id,
                path=path,
                current_waypoint_index=current_waypoint_index,
            )

    def _save_active_snapshot_locked(self, *, task_id, path, current_waypoint_index):
        self.active_patrol_snapshot = {
            "task_id": str(task_id or "").strip(),
            "path": deepcopy(path),
            "current_waypoint_index": int(current_waypoint_index),
        }

    def _run_internal_restart(self, snapshot):
        task_id = snapshot["task_id"]
        path = snapshot["path"]
        poses = list(getattr(path, "poses", []) or [])
        start_index = max(0, min(int(snapshot.get("current_waypoint_index") or 0), len(poses)))

        try:
            self.get_logger().info(
                f"Restarting patrol task_id={task_id} from waypoint={start_index}"
            )
            for index in range(start_index, len(poses)):
                if self._stop_requested_for(task_id):
                    self.navigator.cancelTask()
                    return

                if self._fall_response_requested_for(task_id):
                    self.navigator.cancelTask()
                    return

                target_pose = deepcopy(poses[index])
                if not target_pose.header.frame_id:
                    target_pose.header.frame_id = path.header.frame_id or "map"
                target_pose.header.stamp = self.get_clock().now().to_msg()
                self.navigator.goToPose(target_pose)

                while rclpy.ok() and not self.navigator.isTaskComplete():
                    if self._stop_requested_for(task_id):
                        self.navigator.cancelTask()
                        return

                    if self._fall_response_requested_for(task_id):
                        self.navigator.cancelTask()
                        return
                    time.sleep(self.nav_check_interval_sec)

                if self.navigator.getResult() != TaskResult.SUCCEEDED:
                    self.get_logger().warn(
                        f"Internal patrol restart failed at waypoint {index + 1}."
                    )
                    return

            self.get_logger().info(f"Internal patrol restart completed task_id={task_id}")
            with self.lock:
                if self.active_patrol_snapshot and self.active_patrol_snapshot.get("task_id") == task_id:
                    self.active_patrol_snapshot = None
                self.active_task_id = None
                self.active_path = None
                self.active_waypoint_index = 0
        finally:
            with self.lock:
                if str(self.stop_requested_task_id or "").strip() == task_id:
                    self.active_patrol_snapshot = None
                    self.active_task_id = None
                    self.active_path = None
                    self.active_waypoint_index = 0
                    self.stop_requested_task_id = None
                self.internal_restart_running = False

    def _publish_alarm(self, active):
        msg = Bool()
        msg.data = bool(active)
        self.alarm_pub.publish(msg)

    def destroy_node(self):
        try:
            self.navigator.cancelTask()
        except Exception:
            pass
        self.destroy_service(self.fall_response_service)
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
