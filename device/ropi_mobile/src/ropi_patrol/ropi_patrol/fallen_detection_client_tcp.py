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

        self.goals = self._build_goals_from_waypoints(self.waypoints)

        # 현재 이동해야 하는 goal 번호
        # 예: goal2 이동 중 낙상이 발생하면 current_goal_index는 1로 유지됨
        self.current_goal_index = 0

        # 현재 Nav2에 goal을 보낸 상태인지 여부
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
        # goal 도착 여부를 주기적으로 확인하고 다음 goal로 이동함
        self.nav_timer = self.create_timer(
            self.nav_check_interval_sec,
            self.check_navigation,
        )

        self.get_logger().info("Fallen detection client started.")
        self.get_logger().info(f"UDP image target: {self.server_ip}:{self.udp_port}")
        self.get_logger().info(f"TCP alarm server: {self.server_ip}:{self.tcp_port}")

        if self.auto_start_patrol:
            self.start_current_goal()

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
        self.declare_parameter("auto_start_patrol", True)
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
        self.auto_start_patrol = bool(self.get_parameter("auto_start_patrol").value)
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
        if not self.waypoints:
            raise ValueError("At least one waypoint is required.")
        if self.send_fps <= 0:
            raise ValueError("send_fps must be greater than 0.")
        if self.nav_check_interval_sec <= 0:
            raise ValueError("nav_check_interval_sec must be greater than 0.")

    def _build_goals_from_waypoints(self, waypoints):
        return [self.make_pose(*self._parse_waypoint(waypoint)) for waypoint in waypoints]

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

        Nav2의 goToPose()는 PoseStamped를 사용하므로
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

    def start_current_goal(self):
        """
        현재 current_goal_index에 해당하는 goal로 주행 시작.

        예:
        current_goal_index = 0 -> goal1로 이동
        current_goal_index = 1 -> goal2로 이동
        current_goal_index = 2 -> goal3로 이동
        """
        if self.alarm_active:
            self.get_logger().warn("Alarm is active. Navigation will not start.")
            return

        if len(self.goals) == 0:
            self.get_logger().warn("No goals are defined.")
            return

        goal = self.goals[self.current_goal_index]

        # goal을 보낼 때 stamp를 현재 시간으로 갱신
        goal.header.stamp = self.get_clock().now().to_msg()

        self.navigator.goToPose(goal)
        self.navigation_running = True
        self.navigation_paused_by_alarm = False

        self.get_logger().info(
            f"Navigation started: goal {self.current_goal_index + 1}"
        )

    def check_navigation(self):
        """
        Nav2 주행 상태를 주기적으로 확인함.

        동작:
        1. alarm 중이면 아무것도 하지 않음
        2. 주행 중이 아니면 아무것도 하지 않음
        3. 현재 goal에 도착하면 다음 goal로 이동
        4. 마지막 goal에 도착하면 다시 goal1부터 반복
        """
        with self.nav_lock:
            if self.alarm_active:
                return

            if not self.navigation_running:
                return

            # 아직 goal 이동 중이면 그대로 둠
            if not self.navigator.isTaskComplete():
                return

            result = self.navigator.getResult()

            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(
                    f"Goal {self.current_goal_index + 1} reached."
                )
            elif result == TaskResult.CANCELED:
                self.get_logger().warn(
                    f"Goal {self.current_goal_index + 1} was canceled."
                )
            elif result == TaskResult.FAILED:
                self.get_logger().warn(
                    f"Goal {self.current_goal_index + 1} failed."
                )
            else:
                self.get_logger().warn(
                    f"Goal {self.current_goal_index + 1} finished with unknown result."
                )

            self.navigation_running = False

            # 다음 goal index로 이동
            # goal3까지 갔다면 다시 goal1로 돌아감
            self.current_goal_index += 1

            # 모든 goal을 완료한 경우 순찰 종료
        if self.current_goal_index >= len(self.goals):
            self.get_logger().info("All patrol goals completed. Patrol finished.")

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

        self.start_current_goal()

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
            - 낙상 때문에 멈췄던 goal부터 다시 주행
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
            - 현재 주행 중인 goal을 cancelTask()로 중지
            - current_goal_index는 증가시키지 않음
            - 따라서 goal2 이동 중 멈췄다면 goal2 번호가 그대로 유지됨

        alarm=False가 처음 들어온 경우:
            - 낙상 때문에 멈췄던 goal부터 다시 goToPose()
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
        - current_goal_index를 증가시키지 않음
        - 따라서 alarm이 해제되면 같은 goal로 다시 주행할 수 있음
        """
        if not self.navigation_running:
            self.get_logger().warn("Alarm ON, but navigation is not running.")
            return

        try:
            self.navigator.cancelTask()

            self.navigation_running = False
            self.navigation_paused_by_alarm = True

            self.get_logger().warn(
                f"Alarm ON: navigation canceled at goal {self.current_goal_index + 1}."
            )

        except Exception as e:
            self.get_logger().error(f"Failed to cancel navigation: {e}")

    def resume_navigation_after_alarm(self):
        """
        낙상 미감지 상태가 되면 중지했던 goal부터 다시 주행함.

        서버에서 3초 이상 낙상 미감지 시 alarm=False를 보내므로,
        여기서는 alarm=False를 받으면 현재 current_goal_index의 goal로 다시 이동함.
        """
        if not self.navigation_paused_by_alarm:
            self.get_logger().info("Alarm OFF, but navigation was not paused.")
            return

        self.get_logger().info(
            f"Alarm OFF: resume navigation from goal {self.current_goal_index + 1}."
        )

        self.start_current_goal()

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

        # 종료 시 주행 중이면 Nav2 goal 취소
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
