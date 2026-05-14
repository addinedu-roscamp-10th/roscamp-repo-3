import rclpy
from rclpy.node import Node

from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def slew(target, current, rate):
    if target > current + rate:
        return current + rate
    if target < current - rate:
        return current - rate
    return target


class CmdVelMux(Node):
    def __init__(self):
        super().__init__('cmd_vel_mux')

        self.mode = 'IDLE'

        self.nav2_cmd = Twist()
        self.tracking_cmd = Twist()
        self.re_search_cmd = Twist()
        self.spin_cmd = Twist()

        self.tracking_detected = False
        self.is_moving = False
        self.is_too_close = False
        self.is_too_far = False

        self.max_forward = 0.08
        self.max_backward = -0.10
        self.max_angular = 0.5

        self.tracking_angular_weight = 0.3
        self.tracking_boost_weight = 1.0

        # NAV_TRACKING 모드용 slew rate
        self.tracking_linear_slew = 0.006
        self.tracking_angular_slew = 0.10

        self.last_tracking_linear = 0.0
        self.last_tracking_angular = 0.0

        self.create_subscription(String, '/robot/mode', self.mode_callback, 10)

        self.create_subscription(Twist, '/nav2/cmd_vel', self.nav2_callback, 10)
        self.create_subscription(Twist, '/tracking/tracking_cmd_vel', self.tracking_callback, 10)
        self.create_subscription(Twist, '/re_search/cmd_vel', self.re_search_callback, 10)
        self.create_subscription(Twist, '/spin/cmd_vel', self.spin_callback, 10)

        self.create_subscription(Bool, '/tracking/detected', self.tracking_detected_callback, 10)
        self.create_subscription(Bool, '/tracking/is_moving', self.moving_callback, 10)
        self.create_subscription(Bool, '/tracking/is_too_close', self.too_close_callback, 10)
        self.create_subscription(Bool, '/tracking/is_too_far', self.too_far_callback, 10)

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.timer = self.create_timer(0.05, self.publish_cmd)

    def mode_callback(self, msg):
        if msg.data != self.mode:
            self.last_tracking_linear = 0.0
            self.last_tracking_angular = 0.0
        self.mode = msg.data

    def nav2_callback(self, msg):
        self.nav2_cmd = msg

    def tracking_callback(self, msg):
        self.tracking_cmd = msg

    def re_search_callback(self, msg):
        self.re_search_cmd = msg

    def spin_callback(self, msg):
        self.spin_cmd = msg

    def tracking_detected_callback(self, msg):
        self.tracking_detected = msg.data

    def moving_callback(self, msg):
        self.is_moving = msg.data

    def too_close_callback(self, msg):
        self.is_too_close = msg.data

    def too_far_callback(self, msg):
        self.is_too_far = msg.data

    def publish_cmd(self):
        cmd = Twist()

        if self.mode == 'IDLE':
            self.cmd_pub.publish(cmd)
            return

        if self.mode == 'NAV_WAIT':
            self.cmd_pub.publish(cmd)
            return

        if self.mode == 'NAV_MOVING':
            self.cmd_pub.publish(self.nav2_cmd)
            return

        if self.mode == 'RETURN_HOME':
            self.cmd_pub.publish(self.nav2_cmd)
            return

        if self.mode == 'RE_SEARCH':
            cmd = Twist()
            cmd.linear.x = clamp(
                self.re_search_cmd.linear.x,
                self.max_backward,
                self.max_forward
            )
            cmd.angular.z = clamp(
                self.re_search_cmd.angular.z,
                -self.max_angular,
                self.max_angular
            )
            self.cmd_pub.publish(cmd)
            return

        if self.mode == 'SPINNING':
            cmd = Twist()
            cmd.angular.z = clamp(
                self.spin_cmd.angular.z,
                -self.max_angular,
                self.max_angular
            )
            self.cmd_pub.publish(cmd)
            return

        if self.mode == 'VISITOR_SEARCH':
            self.cmd_pub.publish(self.re_search_cmd)
            return

        if self.mode == 'NAV_TRACKING':
            cmd = self.make_nav_tracking_cmd()
            self.cmd_pub.publish(cmd)
            return

        self.cmd_pub.publish(cmd)

    def make_nav_tracking_cmd(self):
        """
        - is_too_far  : Nav2 무시, tracking_cmd 그대로 (후진해서 다가감)
        - is_too_close: Nav2 + tracking 가속 (전진)
        - NEUTRAL     : 정지 (Nav2 무시), 사람 정렬용 angular만 살짝
        """
        cmd = Twist()

        if not self.tracking_detected:
            target_linear = 0.0
            target_angular = 0.0
        else:
            nav = self.nav2_cmd
            trk = self.tracking_cmd

            if self.is_too_far:
                target_linear = trk.linear.x
                target_angular = trk.angular.z
            elif self.is_too_close:
                target_linear = nav.linear.x + self.tracking_boost_weight * trk.linear.x
                target_angular = nav.angular.z + self.tracking_angular_weight * trk.angular.z
            else:
                target_linear = 0.0
                target_angular = self.tracking_angular_weight * trk.angular.z

        target_linear = clamp(target_linear, self.max_backward, self.max_forward)
        target_angular = clamp(target_angular, -self.max_angular, self.max_angular)

        linear_x = slew(target_linear, self.last_tracking_linear, self.tracking_linear_slew)
        angular_z = slew(target_angular, self.last_tracking_angular, self.tracking_angular_slew)

        self.last_tracking_linear = linear_x
        self.last_tracking_angular = angular_z

        cmd.linear.x = linear_x
        cmd.angular.z = angular_z

        return cmd


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelMux()

    try:
        rclpy.spin(node)
    finally:
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()