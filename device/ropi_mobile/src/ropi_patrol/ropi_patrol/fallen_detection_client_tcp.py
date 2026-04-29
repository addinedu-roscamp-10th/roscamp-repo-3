#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import socket
import threading
import time
import math

import cv2
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.executors import SingleThreadedExecutor

from ropi_patrol.camera import Camera


class FallenDetectionClient(Node):
    def __init__(self):
        super().__init__("fallen_detection_client_tcp")

        self._declare_and_load_parameters()

        self.alarm_pub = self.create_publisher(Bool, self.alarm_topic, 10)

        self.stop_event = threading.Event()

        # UDP socket: 이미지 전송용
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Camera 초기화
        self.camera = Camera()
        self.camera.start(width=self.camera_width, height=self.camera_height)

        # Nav2 제어용 객체
        self.navigator = BasicNavigator()

        self.segment_paths = self._build_segment_paths(self.waypoints)

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

        # TCP 수신 thread: 서버에서 alarm 수신
        self.tcp_thread = threading.Thread(
            target=self.tcp_alarm_receive_loop,
            daemon=True,
        )
        self.tcp_thread.start()

        # 카메라 프레임 UDP 전송 timer
        self.timer = self.create_timer(1.0 / self.send_fps, self.send_frame_udp)

        # navigation 상태 확인 timer
        # path 구간 완료 여부를 주기적으로 확인하고 다음 구간으로 이동함
        self.nav_timer = self.create_timer(
            self.nav_check_interval_sec,
            self.check_navigation,
        )

        self.get_logger().info("Fallen detection client started.")
        self.get_logger().info(f"UDP image target: {self.server_ip}:{self.udp_port}")
        self.get_logger().info(f"TCP alarm server: {self.server_ip}:{self.tcp_port}")

        # 순찰 시작
        self.start_current_segment()

    def _declare_and_load_parameters(self):
        self.declare_parameter("server_ip", "")
        self.declare_parameter("udp_port", 0)
        self.declare_parameter("tcp_port", 0)
        self.declare_parameter("alarm_topic", "/fall_alarm")
        self.declare_parameter("max_udp_packet_size", 60000)
        self.declare_parameter("send_fps", 10.0)
        self.declare_parameter("nav_check_interval_sec", 0.2)
        self.declare_parameter("camera_width", 320)
        self.declare_parameter("camera_height", 240)
        self.declare_parameter("jpeg_quality", 70)
        self.declare_parameter("tcp_connect_timeout_sec", 5.0)
        self.declare_parameter("tcp_reconnect_delay_sec", 1.0)
        self.declare_parameter("path_interpolation_step_m", 0.1)
        self.declare_parameter("segment_retry_count", 3)
        self.declare_parameter("segment_retry_delay_sec", 0.5)
        self.declare_parameter("waypoints", [""])

        self.server_ip = str(self.get_parameter("server_ip").value).strip()
        self.udp_port = int(self.get_parameter("udp_port").value)
        self.tcp_port = int(self.get_parameter("tcp_port").value)
        self.alarm_topic = str(self.get_parameter("alarm_topic").value).strip()
        self.max_udp_packet_size = int(self.get_parameter("max_udp_packet_size").value)
        self.send_fps = float(self.get_parameter("send_fps").value)
        self.nav_check_interval_sec = float(self.get_parameter("nav_check_interval_sec").value)
        self.camera_width = int(self.get_parameter("camera_width").value)
        self.camera_height = int(self.get_parameter("camera_height").value)
        self.jpeg_quality = int(self.get_parameter("jpeg_quality").value)
        self.tcp_connect_timeout_sec = float(self.get_parameter("tcp_connect_timeout_sec").value)
        self.tcp_reconnect_delay_sec = float(self.get_parameter("tcp_reconnect_delay_sec").value)
        self.path_interpolation_step_m = float(self.get_parameter("path_interpolation_step_m").value)
        self.segment_retry_count = int(self.get_parameter("segment_retry_count").value)
        self.segment_retry_delay_sec = float(self.get_parameter("segment_retry_delay_sec").value)
        self.waypoints = [
            str(waypoint).strip()
            for waypoint in list(self.get_parameter("waypoints").value)
            if str(waypoint).strip()
        ]

        if not self.server_ip:
            raise ValueError("server_ip parameter is required.")
        if self.udp_port <= 0:
            raise ValueError("udp_port must be greater than 0.")
        if self.tcp_port <= 0:
            raise ValueError("tcp_port must be greater than 0.")
        if not self.alarm_topic:
            raise ValueError("alarm_topic parameter is required.")
        if len(self.waypoints) < 2:
            raise ValueError("At least two waypoints are required for path following.")
        if self.send_fps <= 0:
            raise ValueError("send_fps must be greater than 0.")
        if self.nav_check_interval_sec <= 0:
            raise ValueError("nav_check_interval_sec must be greater than 0.")
        if self.path_interpolation_step_m <= 0:
            raise ValueError("path_interpolation_step_m must be greater than 0.")
        if self.segment_retry_count < 0:
            raise ValueError("segment_retry_count must be 0 or greater.")
        if self.segment_retry_delay_sec < 0:
            raise ValueError("segment_retry_delay_sec must be 0 or greater.")

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

    def send_frame_udp(self):
        """
        카메라 프레임을 읽어서 JPEG로 압축 후 UDP로 서버에 전송
        """
        try:
            frame = self.camera.get_frame()

            if frame is None:
                return

            # 너무 큰 이미지는 UDP 전송에 불리하므로 크기 축소
            frame = cv2.resize(frame, (self.camera_width, self.camera_height))

            # JPEG 압축
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            ok, encoded = cv2.imencode(".jpg", frame, encode_param)

            if not ok:
                self.get_logger().warn("Failed to encode frame.")
                return

            data = encoded.tobytes()

            if len(data) > self.max_udp_packet_size:
                self.get_logger().warn(
                    f"Frame too large for UDP: {len(data)} bytes. Skipped."
                )
                return

            self.udp_sock.sendto(data, (self.server_ip, self.udp_port))

        except Exception as e:
            self.get_logger().error(f"UDP frame send error: {e}")

    def tcp_alarm_receive_loop(self):
        """
        서버 TCP 포트에 접속해서 alarm 값을 계속 수신.

        서버에서 보내는 데이터 예:
        {"alarm": true}
        {"alarm": false}

        alarm=True:
            - /fall_alarm 토픽으로 True 발행
            - 현재 주행 중이면 cancelTask()로 정지

        alarm=False:
            - /fall_alarm 토픽으로 False 발행
            - 낙상 때문에 멈췄던 path 구간부터 다시 주행
        """
        while not self.stop_event.is_set():
            sock = None

            try:
                self.get_logger().info(
                    f"Connecting to TCP alarm server {self.server_ip}:{self.tcp_port}..."
                )

                sock = socket.create_connection(
                    (self.server_ip, self.tcp_port),
                    timeout=self.tcp_connect_timeout_sec,
                )

                self.get_logger().info("Connected to TCP alarm server.")

                file = sock.makefile("r")

                for line in file:
                    if self.stop_event.is_set():
                        break

                    line = line.strip()
                    if not line:
                        continue

                    msg = json.loads(line)
                    alarm = bool(msg.get("alarm", False))

                    # alarm 상태를 ROS2 topic으로 발행
                    # fallen_alarm.py가 이 값을 받아 부저를 울리거나 끔
                    ros_msg = Bool()
                    ros_msg.data = alarm
                    self.alarm_pub.publish(ros_msg)

                    self.get_logger().info(f"Received alarm: {alarm}")

                    # alarm 상태에 따라 navigation 정지 또는 재개
                    self.handle_alarm_for_navigation(alarm)

            except Exception as e:
                if not self.stop_event.is_set():
                    self.get_logger().warn(f"TCP alarm receive error: {e}")
                    time.sleep(self.tcp_reconnect_delay_sec)

            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

    def handle_alarm_for_navigation(self, alarm):
        """
        alarm 상태에 따라 Nav2 주행을 제어함.

        alarm=True가 처음 들어온 경우:
            - 현재 추종 중인 path 구간을 cancelTask()로 중지
            - current_segment_index는 증가시키지 않음
            - 따라서 2번째 구간 추종 중 멈췄다면 같은 구간 번호가 유지됨

        alarm=False가 처음 들어온 경우:
            - 낙상 때문에 멈췄던 path 구간부터 다시 followPath()
        """
        with self.nav_lock:
            # 같은 alarm 상태가 반복해서 들어오면 무시
            # 예: True, True, True가 계속 와도 cancelTask()는 한 번만 실행
            if self.alarm_active == alarm:
                return

            self.alarm_active = alarm

            if alarm:
                self.stop_navigation_by_alarm()
            else:
                self.resume_navigation_after_alarm()

    def stop_navigation_by_alarm(self):
        """
        낙상 감지 시 현재 주행을 중지함.

        중요한 점:
        - current_segment_index를 증가시키지 않음
        - 따라서 alarm이 해제되면 같은 path 구간부터 다시 추종할 수 있음
        """
        if not self.navigation_running:
            self.get_logger().warn("Alarm ON, but navigation is not running.")
            return

        try:
            self.navigator.cancelTask()

            self.navigation_running = False
            self.navigation_paused_by_alarm = True

            self.get_logger().warn(
                f"Alarm ON: navigation canceled at path segment {self.current_segment_index + 1}."
            )

        except Exception as e:
            self.get_logger().error(f"Failed to cancel navigation: {e}")

    def resume_navigation_after_alarm(self):
        """
        낙상 미감지 상태가 되면 중지했던 path 구간부터 다시 추종함.

        서버에서 3초 이상 낙상 미감지 시 alarm=False를 보내므로,
        여기서는 alarm=False를 받으면 현재 current_segment_index의 path 구간을 다시 추종함.
        """
        if not self.navigation_paused_by_alarm:
            self.get_logger().info("Alarm OFF, but navigation was not paused.")
            return

        self.get_logger().info(
            f"Alarm OFF: resume navigation from path segment {self.current_segment_index + 1}."
        )

        self.start_current_segment()

    def close(self):
        """
        카메라, socket, navigation 자원 반환
        """
        self.stop_event.set()

        try:
            self.timer.cancel()
        except Exception:
            pass

        try:
            self.nav_timer.cancel()
        except Exception:
            pass

        # 종료 시 주행 중이면 Nav2 작업 취소
        try:
            if self.navigation_running:
                self.navigator.cancelTask()
        except Exception:
            pass

        try:
            self.udp_sock.close()
        except Exception:
            pass

        try:
            self.camera.close()
        except Exception:
            pass

        self.get_logger().info("Fallen detection client closed.")


def main(args=None):
    rclpy.init(args=args)

    node = FallenDetectionClient()

    # 중요:
    # rclpy.spin(node)를 그대로 쓰면 global executor가 사용됨.
    # 그런데 BasicNavigator.isTaskComplete()도 내부에서 spin_until_future_complete()를 사용함.
    # 그 결과 "Executor is already spinning" 에러가 발생할 수 있음.
    #
    # 따라서 fallen_detection_client_tcp 노드는 별도의 executor로 돌리고,
    # BasicNavigator 내부 spin과 충돌하지 않도록 함.
    executor = SingleThreadedExecutor()
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
