#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.executors import MultiThreadedExecutor

from ropi_interface.action import ExecutePatrolPath
from ropi_interface.srv import FallResponseControl


class FallenDetectionClient(Node):
    COMMAND_START_FALL_ALERT = "START_FALL_ALERT"
    COMMAND_CLEAR_AND_RESTART = "CLEAR_AND_RESTART"

    def __init__(self):
        super().__init__("fallen_detection_client")

        self._declare_and_load_parameters()

        self.alarm_pub = self.create_publisher(Bool, self.alarm_topic, 10)

        self.stop_event = threading.Event()

        # Nav2 제어용 객체
        self.navigator = BasicNavigator()

        self.segment_paths = []

        # 현재 추종해야 하는 path 구간 번호
        # 예: 2번째 구간 추종 중 낙상이 발생하면 current_segment_index는 유지됨
        self.current_segment_index = 0

        # 현재 path 구간의 재시도 횟수
        self.current_segment_retry_count = 0

        # 현재 Nav2에 path 추종 작업을 보낸 상태인지 여부
        self.navigation_running = False

        # 낙상 때문에 주행이 중지된 상태인지 여부
        self.navigation_paused_by_alarm = False

        # 현재 alarm 상태
        self.alarm_active = False

        # TCP thread와 ROS timer가 navigation 상태를 동시에 바꿀 수 있으므로 lock 사용
        self.nav_lock = threading.Lock()
        self.action_busy = False
        self.active_task_id = ""
        self.active_patrol_snapshot = None
        self.stop_requested_by_fall_response = False
        self.cb_group = ReentrantCallbackGroup()

        self.nav_timer = None

        self.patrol_action_server = ActionServer(
            self,
            ExecutePatrolPath,
            self.patrol_action_name,
            execute_callback=self.execute_patrol_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group,
        )

        self.fall_response_service = self.create_service(
            FallResponseControl,
            self.fall_response_service_name,
            self.handle_fall_response_control,
            callback_group=self.cb_group,
        )

        self.get_logger().info("Fallen detection client started.")
        self.get_logger().info(f"PAT-003 action server: {self.patrol_action_name}")
        self.get_logger().info(f"PAT-004 service: {self.fall_response_service_name}")

    def _declare_and_load_parameters(self):
        self.declare_parameter("alarm_topic", "/fall_alarm")
        self.declare_parameter("pinky_id", "pinky3")
        self.declare_parameter("patrol_action_name", "")
        self.declare_parameter("fall_response_service_name", "")
        self.declare_parameter("nav_check_interval_sec", 0.2)
        self.declare_parameter("path_interpolation_step_m", 0.1)
        self.declare_parameter("segment_retry_count", 3)
        self.declare_parameter("segment_retry_delay_sec", 0.5)
        self.declare_parameter("waypoints", [""])

        self.alarm_topic = str(self.get_parameter("alarm_topic").value).strip()
        self.pinky_id = str(self.get_parameter("pinky_id").value).strip()
        configured_patrol_action_name = str(self.get_parameter("patrol_action_name").value).strip()
        self.patrol_action_name = (
            configured_patrol_action_name
            or f"/ropi/control/{self.pinky_id}/execute_patrol_path"
        )
        configured_fall_response_service_name = str(
            self.get_parameter("fall_response_service_name").value
        ).strip()
        self.fall_response_service_name = (
            configured_fall_response_service_name
            or f"/ropi/control/{self.pinky_id}/fall_response_control"
        )
        self.nav_check_interval_sec = float(self.get_parameter("nav_check_interval_sec").value)
        self.path_interpolation_step_m = float(self.get_parameter("path_interpolation_step_m").value)
        self.segment_retry_count = int(self.get_parameter("segment_retry_count").value)
        self.segment_retry_delay_sec = float(self.get_parameter("segment_retry_delay_sec").value)
        self.waypoints = [
            str(waypoint).strip()
            for waypoint in list(self.get_parameter("waypoints").value)
            if str(waypoint).strip()
        ]

        if not self.alarm_topic:
            raise ValueError("alarm_topic parameter is required.")
        if not self.pinky_id:
            raise ValueError("pinky_id parameter is required.")
        if not self.patrol_action_name:
            raise ValueError("patrol_action_name parameter is required.")
        if not self.fall_response_service_name:
            raise ValueError("fall_response_service_name parameter is required.")
        if self.nav_check_interval_sec <= 0:
            raise ValueError("nav_check_interval_sec must be greater than 0.")
        if self.path_interpolation_step_m <= 0:
            raise ValueError("path_interpolation_step_m must be greater than 0.")
        if self.segment_retry_count < 0:
            raise ValueError("segment_retry_count must be 0 or greater.")
        if self.segment_retry_delay_sec < 0:
            raise ValueError("segment_retry_delay_sec must be 0 or greater.")

    def goal_callback(self, goal_request):
        """
        IF-PAT-003 goal 수락 여부를 결정한다.

        순찰 경로의 source of truth는 서버가 보낸 nav_msgs/Path이므로,
        로컬 patrol.yaml의 waypoints는 더 이상 실행 조건으로 사용하지 않는다.
        """
        with self.nav_lock:
            if self.action_busy:
                self.get_logger().warn("Reject patrol goal because another patrol is running.")
                return GoalResponse.REJECT

            self.action_busy = True

        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    def handle_fall_response_control(self, request, response):
        """
        IF-PAT-004 낙상 대응 제어 서비스.

        START_FALL_ALERT는 현재 Nav2 goal을 cancel하고 /fall_alarm=True를 발행한다.
        CLEAR_AND_RESTART는 /fall_alarm=False를 발행하고 PAT-003 action이 저장한
        active_patrol_snapshot의 current_waypoint_index부터 다시 시도하게 한다.
        """
        command_type = str(request.command_type).strip()
        task_id = str(request.task_id).strip()

        with self.nav_lock:
            if self.active_task_id and task_id and task_id != self.active_task_id:
                response.accepted = False
                response.message = (
                    f"task_id mismatch: active={self.active_task_id}, request={task_id}"
                )
                return response

            if command_type == self.COMMAND_START_FALL_ALERT:
                self.alarm_active = True
                self.stop_requested_by_fall_response = False
                if self.navigation_running:
                    self.navigator.cancelTask()
                self.navigation_running = False
                self.navigation_paused_by_alarm = True
                self._publish_alarm(True)
                response.accepted = True
                response.message = ""
                return response

            if command_type == self.COMMAND_CLEAR_AND_RESTART:
                if self.active_patrol_snapshot is None:
                    response.accepted = False
                    response.message = "active_patrol_snapshot is not available."
                    return response

                self.alarm_active = False
                self.stop_requested_by_fall_response = False
                self._publish_alarm(False)
                response.accepted = True
                response.message = ""
                return response

        response.accepted = False
        response.message = f"unsupported command_type: {command_type}"
        return response

    def _publish_alarm(self, alarm):
        msg = Bool()
        msg.data = bool(alarm)
        self.alarm_pub.publish(msg)

    def execute_patrol_callback(self, goal_handle):
        """
        IF-PAT-003 ExecutePatrolPath action 실행부.

        path.poses는 dense trajectory가 아니라 waypoint sequence로 해석한다.
        각 waypoint를 Nav2 goToPose goal로 순차 실행하면서 feedback/result를 만든다.
        """
        request = goal_handle.request
        feedback = ExecutePatrolPath.Feedback()

        if not str(request.task_id).strip():
            goal_handle.abort()
            with self.nav_lock:
                self.action_busy = False
            return self._build_patrol_result("REJECTED", "task_id is required.", 0, PoseStamped())

        if len(request.path.poses) == 0:
            goal_handle.abort()
            with self.nav_lock:
                self.action_busy = False
            return self._build_patrol_result("REJECTED", "path.poses must not be empty.", 0, PoseStamped())

        path = self._normalize_goal_path(request.path)
        total_waypoints = len(path.poses)
        completed_count = 0
        started_at = time.monotonic()

        self.active_task_id = str(request.task_id)
        self.active_patrol_snapshot = {
            "task_id": self.active_task_id,
            "path": path,
            "current_waypoint_index": 0,
        }
        self.stop_requested_by_fall_response = False

        try:
            self._publish_patrol_feedback(
                goal_handle,
                feedback,
                "ACCEPTED",
                0,
                total_waypoints,
                path.poses[0],
                -1.0,
            )

            for waypoint_index, goal_pose in enumerate(path.poses):
                with self.nav_lock:
                    self.current_segment_index = waypoint_index
                    self.active_patrol_snapshot["current_waypoint_index"] = waypoint_index

                while rclpy.ok():
                    goal_pose.header.stamp = self.get_clock().now().to_msg()
                    self.navigator.goToPose(goal_pose)
                    with self.nav_lock:
                        self.navigation_running = True

                    status = self._wait_for_waypoint(
                        goal_handle,
                        feedback,
                        goal_pose,
                        waypoint_index,
                        total_waypoints,
                        started_at,
                        int(request.timeout_sec),
                    )

                    if status == "FALL_ALERT":
                        wait_status = self._wait_for_fall_clear(
                            goal_handle,
                            feedback,
                            goal_pose,
                            waypoint_index,
                            total_waypoints,
                            started_at,
                            int(request.timeout_sec),
                        )
                        if wait_status == "RESTART":
                            continue
                        status = wait_status

                    break

                if status == "CANCELED":
                    goal_handle.canceled()
                    return self._build_patrol_result(
                        "CANCELED",
                        "Patrol goal was canceled.",
                        completed_count,
                        goal_pose,
                    )

                if status == "TIMEOUT":
                    goal_handle.abort()
                    return self._build_patrol_result(
                        "TIMEOUT",
                        "Patrol action timeout reached.",
                        completed_count,
                        goal_pose,
                    )

                if status == "STOPPED":
                    goal_handle.canceled()
                    return self._build_patrol_result(
                        "CANCELED",
                        "Patrol stopped by fall response control.",
                        completed_count,
                        goal_pose,
                    )

                nav_result = self.navigator.getResult()
                if nav_result != TaskResult.SUCCEEDED:
                    goal_handle.abort()
                    return self._build_patrol_result(
                        "FAILED",
                        f"Nav2 failed at waypoint {waypoint_index}.",
                        completed_count,
                        goal_pose,
                    )

                completed_count += 1

            goal_handle.succeed()
            return self._build_patrol_result(
                "SUCCEEDED",
                "",
                completed_count,
                path.poses[-1],
            )

        except Exception as e:
            goal_handle.abort()
            final_pose = path.poses[min(completed_count, total_waypoints - 1)]
            return self._build_patrol_result("FAILED", str(e), completed_count, final_pose)

        finally:
            with self.nav_lock:
                self.action_busy = False
                self.navigation_running = False

    def _normalize_goal_path(self, path):
        frame_id = path.header.frame_id.strip() or "map"
        path.header.frame_id = frame_id
        path.header.stamp = self.get_clock().now().to_msg()

        for pose in path.poses:
            if not pose.header.frame_id:
                pose.header.frame_id = frame_id
            pose.header.stamp = path.header.stamp

        return path

    def _wait_for_waypoint(
        self,
        goal_handle,
        feedback,
        goal_pose,
        waypoint_index,
        total_waypoints,
        started_at,
        timeout_sec,
    ):
        if self.alarm_active or self.navigation_paused_by_alarm:
            self.navigator.cancelTask()
            return "FALL_ALERT"

        while rclpy.ok() and not self.navigator.isTaskComplete():
            if goal_handle.is_cancel_requested:
                self.navigator.cancelTask()
                return "CANCELED"

            if self.alarm_active:
                self.navigator.cancelTask()
                return "FALL_ALERT"

            if timeout_sec > 0 and time.monotonic() - started_at >= timeout_sec:
                self.navigator.cancelTask()
                return "TIMEOUT"

            distance_remaining = -1.0
            nav_feedback = self.navigator.getFeedback()
            if nav_feedback is not None and hasattr(nav_feedback, "distance_remaining"):
                distance_remaining = float(nav_feedback.distance_remaining)

            patrol_status = "WAITING_FALL_RESPONSE" if self.alarm_active else "MOVING"
            self._publish_patrol_feedback(
                goal_handle,
                feedback,
                patrol_status,
                waypoint_index,
                total_waypoints,
                goal_pose,
                distance_remaining,
            )
            time.sleep(self.nav_check_interval_sec)

        if self.alarm_active or self.navigation_paused_by_alarm:
            return "FALL_ALERT"

        return "DONE"

    def _wait_for_fall_clear(
        self,
        goal_handle,
        feedback,
        goal_pose,
        waypoint_index,
        total_waypoints,
        started_at,
        timeout_sec,
    ):
        """
        START_FALL_ALERT 이후 CLEAR_AND_RESTART가 올 때까지 action을 유지한다.
        """
        with self.nav_lock:
            self.navigation_running = False
            self.navigation_paused_by_alarm = True

        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                return "CANCELED"

            if self.stop_requested_by_fall_response:
                return "STOPPED"

            if timeout_sec > 0 and time.monotonic() - started_at >= timeout_sec:
                return "TIMEOUT"

            self._publish_patrol_feedback(
                goal_handle,
                feedback,
                "WAITING_FALL_RESPONSE",
                waypoint_index,
                total_waypoints,
                goal_pose,
                -1.0,
            )

            if not self.alarm_active:
                with self.nav_lock:
                    self.navigation_paused_by_alarm = False
                return "RESTART"

            time.sleep(self.nav_check_interval_sec)

        return "CANCELED"

    def _publish_patrol_feedback(
        self,
        goal_handle,
        feedback,
        patrol_status,
        current_waypoint_index,
        total_waypoints,
        current_pose,
        distance_remaining_m,
    ):
        feedback.patrol_status = patrol_status
        feedback.current_waypoint_index = int(current_waypoint_index)
        feedback.total_waypoints = int(total_waypoints)
        feedback.current_pose = current_pose
        feedback.distance_remaining_m = float(distance_remaining_m)
        goal_handle.publish_feedback(feedback)

    def _build_patrol_result(
        self,
        result_code,
        result_message,
        completed_waypoint_count,
        final_pose,
    ):
        result = ExecutePatrolPath.Result()
        result.result_code = result_code
        result.result_message = result_message
        result.completed_waypoint_count = int(completed_waypoint_count)
        result.final_pose = final_pose
        result.finished_at = self.get_clock().now().to_msg()
        return result

    def _build_segment_paths(self, waypoints):
        parsed_waypoints = [self._parse_waypoint(waypoint) for waypoint in waypoints]
        segment_paths = []

        for index in range(len(parsed_waypoints) - 1):
            start = parsed_waypoints[index]
            end = parsed_waypoints[index + 1]
            segment_paths.append(self._build_straight_path_segment(start, end))

        return segment_paths

    @staticmethod
    def _parse_waypoint(waypoint):
        if isinstance(waypoint, str):
            parts = [part.strip() for part in waypoint.split(",")]
        else:
            parts = list(waypoint)

        if len(parts) != 3:
            raise ValueError(f"Waypoint must have x,y,yaw_deg: {waypoint}")

        return float(parts[0]), float(parts[1]), float(parts[2])

    def make_pose(self, x, y, yaw_deg):
        """
        x, y, yaw_deg 값을 PoseStamped로 변환함.

        Nav2의 goal/path pose는 PoseStamped를 사용하므로
        사용자가 입력한 좌표를 PoseStamped 형태로 만들어줌.
        """
        pose = PoseStamped()

        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()

        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0

        yaw_rad = math.radians(yaw_deg)

        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = math.sin(yaw_rad / 2.0)
        pose.pose.orientation.w = math.cos(yaw_rad / 2.0)

        return pose

    def _build_straight_path_segment(self, start, end):
        start_x, start_y, _ = start
        end_x, end_y, end_yaw_deg = end

        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.hypot(dx, dy)
        segment_yaw_deg = math.degrees(math.atan2(dy, dx)) if distance > 0.0 else end_yaw_deg

        path = Path()
        path.header.frame_id = "map"
        path.header.stamp = self.get_clock().now().to_msg()

        steps = max(1, int(math.ceil(distance / self.path_interpolation_step_m)))

        for step_index in range(steps + 1):
            ratio = step_index / steps
            x = start_x + dx * ratio
            y = start_y + dy * ratio
            yaw_deg = end_yaw_deg if step_index == steps else segment_yaw_deg

            pose = self.make_pose(x, y, yaw_deg)
            pose.header.stamp = path.header.stamp
            path.poses.append(pose)

        return path

    def start_current_segment(self):
        """
        현재 current_segment_index에 해당하는 직선 path 구간 추종 시작.
        """
        if self.alarm_active:
            self.get_logger().warn("Alarm is active. Navigation will not start.")
            return

        if len(self.segment_paths) == 0:
            self.get_logger().warn("No path segments are defined.")
            return

        path = self.segment_paths[self.current_segment_index]
        path.header.stamp = self.get_clock().now().to_msg()
        for pose in path.poses:
            pose.header.stamp = path.header.stamp

        self.navigator.followPath(path)
        self.navigation_running = True
        self.navigation_paused_by_alarm = False

        self.get_logger().info(
            f"Path following started: segment {self.current_segment_index + 1}/{len(self.segment_paths)}"
        )

    def retry_current_segment(self):
        """
        현재 path 구간을 재시도함.
        """
        self.current_segment_retry_count += 1

        self.get_logger().warn(
            f"Retrying path segment {self.current_segment_index + 1} "
            f"({self.current_segment_retry_count}/{self.segment_retry_count})."
        )

        if self.segment_retry_delay_sec > 0:
            time.sleep(self.segment_retry_delay_sec)

        self.start_current_segment()

    def check_navigation(self):
        """
        Nav2 주행 상태를 주기적으로 확인함.

        동작:
        1. alarm 중이면 아무것도 하지 않음
        2. 주행 중이 아니면 아무것도 하지 않음
        3. 현재 path 구간 추종이 끝나면 다음 구간으로 이동
        4. 마지막 구간까지 완료하면 순찰 종료
        """
        with self.nav_lock:
            if self.alarm_active:
                return

            if not self.navigation_running:
                return

            # 아직 path 구간 추종 중이면 그대로 둠
            if not self.navigator.isTaskComplete():
                return

            result = self.navigator.getResult()

            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(
                    f"Path segment {self.current_segment_index + 1} completed."
                )
                self.current_segment_retry_count = 0
                self.navigation_running = False
                self.current_segment_index += 1

                if self.current_segment_index < len(self.segment_paths):
                    self.start_current_segment()
                    return
            elif result == TaskResult.CANCELED:
                self.get_logger().warn(
                    f"Path segment {self.current_segment_index + 1} was canceled."
                )
                self.navigation_running = False
                return
            elif result == TaskResult.FAILED:
                self.get_logger().warn(
                    f"Path segment {self.current_segment_index + 1} failed."
                )
                self.navigation_running = False

                if self.current_segment_retry_count < self.segment_retry_count:
                    self.retry_current_segment()
                    return

                self.get_logger().warn(
                    "Stopping patrol because the current path segment exceeded the retry limit."
                )
                return
            else:
                self.get_logger().warn(
                    f"Path segment {self.current_segment_index + 1} finished with unknown result."
                )
                self.navigation_running = False
                return

        if self.current_segment_index >= len(self.segment_paths):
            self.get_logger().info("All patrol path segments completed. Patrol finished.")

            # 더 이상 navigation을 재시작하지 않음
            self.navigation_running = False
            self.navigation_paused_by_alarm = False

            # alarm 상태도 False로 발행해서 부저가 꺼지도록 함
            self.alarm_active = False

            alarm_msg = Bool()
            alarm_msg.data = False
            self.alarm_pub.publish(alarm_msg)

            # 카메라/UDP/TCP까지 모두 종료하고 싶으면 stop_event를 True로 설정
            # 그러면 main loop가 종료 단계로 들어감
            self.stop_event.set()

            # ROS timer들도 정지
            try:
                self.timer.cancel()
            except Exception:
                pass

            try:
                self.nav_timer.cancel()
            except Exception:
                pass

            return

    def close(self):
        """
        navigation/action/service 자원 반환
        """
        self.stop_event.set()

        try:
            if self.nav_timer is not None:
                self.nav_timer.cancel()
        except Exception:
            pass

        try:
            self.patrol_action_server.destroy()
        except Exception:
            pass

        try:
            self.destroy_service(self.fall_response_service)
        except Exception:
            pass

        # 종료 시 주행 중이면 Nav2 작업 취소
        try:
            if self.navigation_running:
                self.navigator.cancelTask()
        except Exception:
            pass

        self.get_logger().info("Fallen detection client closed.")


def main(args=None):
    rclpy.init(args=args)

    node = FallenDetectionClient()

    # Action execute callback과 UDP timer가 함께 돌아야 하므로 MultiThreadedExecutor를 사용한다.
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()

    except KeyboardInterrupt:
        pass

    finally:
        node.close()

        try:
            executor.remove_node(node)
        except Exception:
            pass

        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
