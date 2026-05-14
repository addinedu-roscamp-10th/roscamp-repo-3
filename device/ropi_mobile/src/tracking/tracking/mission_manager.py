import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Bool, String
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry
from action_msgs.msg import GoalStatusArray, GoalStatus
from nav2_msgs.action import NavigateToPose


# RETURN_HOME 목표 좌표 (map 프레임 기준)
HOME_X = -0.193
HOME_Y = -0.705
HOME_Z = 0.0
HOME_ORI_Z = 1.0
HOME_ORI_W = 0.0


def quat_to_yaw(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(a):
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


class MissionManager(Node):
    def __init__(self):
        super().__init__('mission_manager')

        self.mode_pub = self.create_publisher(String, '/robot/mode', 10)

        self.re_search_cmd_pub = self.create_publisher(
            Twist,
            '/re_search/cmd_vel',
            10
        )

        self.create_subscription(
            Bool,
            '/visitor/detected',
            self.visitor_detected_callback,
            10
        )

        self.create_subscription(
            Bool,
            '/tracking/detected',
            self.tracking_detected_callback,
            10
        )

        self.create_subscription(
            Bool,
            '/visitor/spin_request',
            self.spin_request_callback,
            10
        )

        self.create_subscription(
            GoalStatusArray,
            '/navigate_to_pose/_action/status',
            self.nav_status_callback,
            10
        )

        self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        self.nav_action_client = ActionClient(
            self,
            NavigateToPose,
            'navigate_to_pose'
        )

        self.state = 'IDLE'

        self.nav_active = False
        self.visitor_detected = False
        self.tracking_detected = False

        self.tracking_session_started = False
        self.was_tracking = False

        # SPINNING 관리 (visitor 응대용 180도 회전)
        self.spin_request_received = False
        self.spinning_active = False
        self.spinning_start_time = None
        self.spinning_duration = 7.0
        self.spinning_done = False

        # tracking lost 관리
        self.tracking_lost_time = None
        self.re_search_timeout = 7.0

        # odom 관리
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.odom_received = False

        # RE_SEARCH = 360도 회전만 (BACKTRACK 제거)
        self.re_search_spin_speed = 0.5
        self.re_search_spin_total_rotated = 0.0
        self.re_search_spin_prev_yaw = 0.0
        self.re_search_spin_target_total = 2.0 * math.pi
        self.re_search_spin_initialized = False

        # RETURN_HOME 관리
        self.return_home_sent = False
        self.return_home_arrived = False

        self.timer = self.create_timer(0.1, self.loop)

        self.get_logger().info('mission_manager started')

    def reset_tracking_session(self):
        self.tracking_session_started = False
        self.tracking_lost_time = None
        self.was_tracking = False
        self.re_search_spin_initialized = False
        self.re_search_spin_total_rotated = 0.0

    def reset_return_home(self):
        self.return_home_sent = False
        self.return_home_arrived = False

    def visitor_detected_callback(self, msg):
        self.visitor_detected = bool(msg.data)

    def spin_request_callback(self, msg):
        self.spin_request_received = bool(msg.data)

        if msg.data:
            self.get_logger().info(
                'spin_request received, will SPIN when NAV_MOVING ends'
            )
        else:
            self.get_logger().info('spin_request cleared')

    def tracking_detected_callback(self, msg):
        now = self.get_clock().now().nanoseconds / 1e9

        self.tracking_detected = msg.data

        if msg.data:
            self.tracking_lost_time = None
        else:
            if self.tracking_session_started and self.tracking_lost_time is None:
                self.tracking_lost_time = now

    def odom_callback(self, msg):
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y
        self.current_yaw = quat_to_yaw(msg.pose.pose.orientation)
        self.odom_received = True

    def nav_status_callback(self, msg):
        if len(msg.status_list) == 0:
            return

        status = msg.status_list[-1].status

        if status in [
            GoalStatus.STATUS_ACCEPTED,
            GoalStatus.STATUS_EXECUTING,
        ]:
            self.nav_active = True

        elif status == GoalStatus.STATUS_SUCCEEDED:
            self.nav_active = False

            if self.state == 'RETURN_HOME':
                self.return_home_arrived = True
                self.get_logger().info(
                    f'RETURN_HOME arrived at ({HOME_X}, {HOME_Y})'
                )
            else:
                self.reset_tracking_session()
                self.get_logger().info('Nav2 goal succeeded')

        elif status in [
            GoalStatus.STATUS_CANCELED,
            GoalStatus.STATUS_ABORTED,
        ]:
            self.nav_active = False
            if self.state != 'RETURN_HOME':
                self.reset_tracking_session()
            self.get_logger().warn('Nav2 goal canceled/aborted')

    def publish_mode(self):
        msg = String()
        msg.data = self.state
        self.mode_pub.publish(msg)

    def publish_re_search_cmd(self, cmd):
        self.re_search_cmd_pub.publish(cmd)

    def send_return_home_goal(self):
        if not self.nav_action_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().warn('Nav2 action server not available')
            return False

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = HOME_X
        goal_msg.pose.pose.position.y = HOME_Y
        goal_msg.pose.pose.position.z = HOME_Z
        goal_msg.pose.pose.orientation.z = HOME_ORI_Z
        goal_msg.pose.pose.orientation.w = HOME_ORI_W

        self.nav_action_client.send_goal_async(goal_msg)
        self.get_logger().info(
            f'RETURN_HOME goal sent: ({HOME_X}, {HOME_Y}, {HOME_Z}) '
            f'ori(z={HOME_ORI_Z}, w={HOME_ORI_W})'
        )
        return True

    def run_spin(self):
        """360도 제자리 회전. 회전 끝나면 (cmd, True) 반환."""
        cmd = Twist()

        # 첫 진입 시 시작 yaw 기록
        if not self.re_search_spin_initialized:
            self.re_search_spin_total_rotated = 0.0
            self.re_search_spin_prev_yaw = self.current_yaw
            self.re_search_spin_initialized = True

        # 회전한 총 각도 누적
        delta = normalize_angle(self.current_yaw - self.re_search_spin_prev_yaw)
        self.re_search_spin_total_rotated += abs(delta)
        self.re_search_spin_prev_yaw = self.current_yaw

        if self.re_search_spin_total_rotated >= self.re_search_spin_target_total:
            return cmd, True

        cmd.angular.z = self.re_search_spin_speed
        return cmd, False

    def loop(self):
        now = self.get_clock().now().nanoseconds / 1e9

        # SPINNING 진행 중이면 우선
        if self.spinning_active:
            if self.spinning_start_time is None:
                self.spinning_start_time = now

            spinning_elapsed = now - self.spinning_start_time

            if spinning_elapsed < self.spinning_duration:
                self.state = 'SPINNING'
                self.publish_mode()
                return
            else:
                self.spinning_active = False
                self.spinning_start_time = None
                self.spinning_done = True
                self.spin_request_received = False
                self.get_logger().info('SPINNING finished')

        # SPINNING 진입 조건
        if (
            self.spin_request_received
            and not self.nav_active
            and not self.spinning_done
        ):
            self.spinning_active = True
            self.spinning_start_time = now
            self.state = 'SPINNING'
            self.get_logger().info(
                'spin_request + Nav2 finished, SPINNING started'
            )
            self.publish_mode()
            return

        # RETURN_HOME 처리
        if self.state == 'RETURN_HOME':
            if self.return_home_arrived:
                self.state = 'IDLE'
                self.reset_tracking_session()
                self.reset_return_home()
                self.get_logger().info('RETURN_HOME done, IDLE')

            self.publish_mode()
            return

        # RE_SEARCH = 360도 회전만
        if self.state == 'RE_SEARCH':
            # 회전 중 사람 다시 발견하면 NAV_TRACKING 복귀
            if self.tracking_detected:
                self.state = 'NAV_TRACKING'
                self.tracking_lost_time = None
                self.re_search_spin_initialized = False
                self.publish_re_search_cmd(Twist())
                self.get_logger().info(
                    'RE_SEARCH: tracking found, NAV_TRACKING'
                )
                self.publish_mode()
                return

            # 회전 동작
            cmd, done = self.run_spin()
            self.publish_re_search_cmd(cmd)

            if done:
                # 360도 회전 끝, 사람 못 찾음 → RETURN_HOME
                self.publish_re_search_cmd(Twist())
                self.re_search_spin_initialized = False
                self.state = 'RETURN_HOME'
                self.reset_return_home()
                self.send_return_home_goal()
                self.get_logger().info(
                    'RE_SEARCH: spin done, person not found, RETURN_HOME'
                )

            self.publish_mode()
            return

        # nav_active False면 IDLE
        if not self.nav_active:
            self.state = 'IDLE'
            self.reset_tracking_session()
            self.publish_mode()
            return

        # tracking session 시작 전: NAV_MOVING
        if not self.tracking_session_started:
            self.state = 'NAV_MOVING'

            if self.visitor_detected and self.tracking_detected:
                self.tracking_session_started = True
                self.tracking_lost_time = None
                self.state = 'NAV_TRACKING'
                self.was_tracking = True
                self.get_logger().info(
                    'visitor + tracking detected, tracking session started'
                )

            self.publish_mode()
            return

        # tracking session 시작 후
        if self.tracking_detected:
            self.state = 'NAV_TRACKING'
            self.tracking_lost_time = None
            self.was_tracking = True
            self.publish_mode()
            return

        # tracking lost
        if self.tracking_lost_time is None:
            self.tracking_lost_time = now

        lost_duration = now - self.tracking_lost_time

        if lost_duration >= self.re_search_timeout and self.was_tracking:
            self.state = 'RE_SEARCH'
            self.re_search_spin_initialized = False
            self.get_logger().info(
                f'tracking lost {self.re_search_timeout}s, RE_SEARCH (SPIN)'
            )
        else:
            self.state = 'NAV_WAIT'

        self.publish_mode()


def main(args=None):
    rclpy.init(args=args)
    node = MissionManager()

    try:
        rclpy.spin(node)
    finally:
        node.state = 'IDLE'
        node.reset_tracking_session()
        node.publish_mode()
        node.publish_re_search_cmd(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()