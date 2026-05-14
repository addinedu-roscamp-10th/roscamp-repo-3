import socket
import threading
import time
import json

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool
from geometry_msgs.msg import Twist


PINKY_RESULT_PORT = 6006

DEFAULT_FRAME_WIDTH = 320
DEFAULT_FRAME_HEIGHT = 240

CENTER_DEAD_BAND = 20

TARGET_BBOX_RATIO = 0.15

# 너무 작은 bbox는 노이즈로 간주
MIN_VALID_RATIO = 0.02

# EMA 평활
RATIO_EMA_ALPHA = 0.30

# 단일 임계치 (hysteresis 제거)
# ratio_err 절댓값이 이 값보다 크면 FAR/CLOSE, 작으면 NEUTRAL
RATIO_THRESHOLD = 0.02

# 시간 기반 디바운싱
STATE_DEBOUNCE_FRAMES = 4

TURN_GAIN = 0.003

# DIST_GAIN: ratio_err 가 0.4 일 때 -0.10 (풀스피드)
DIST_GAIN_RATIO = 0.35

MAX_LINEAR_X = 0.04
MAX_LINEAR_X_BACKWARD = 0.08
MAX_ANGULAR_Z = 0.3

LINEAR_SLEW_RATE = 0.006
ANGULAR_SLEW_RATE = 0.06

RESULT_TIMEOUT_SEC = 10.0

# is_moving 판정용 (비율 기준)
MOVING_RATIO_THRESHOLD = 0.07
MOVING_CENTER_THRESHOLD = 25

FLIP_X = True
FLIP_Y = True

# 현재 안씀
REAR_CAMERA = False
REAR_CAMERA_FLIP_ANGULAR = False


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def slew(target, current, rate):
    if target > current + rate:
        return current + rate
    if target < current - rate:
        return current - rate
    return target


class TrackingNode(Node):
    def __init__(self):
        super().__init__('tracking_node')

        self.cmd_pub = self.create_publisher(Twist, '/tracking/tracking_cmd_vel', 10)
        self.detection_pub = self.create_publisher(Bool, '/tracking/detected', 10)
        self.tracking_pub = self.create_publisher(Bool, '/tracking/is_tracking', 10)
        self.moving_pub = self.create_publisher(Bool, '/tracking/is_moving', 10)
        self.too_close_pub = self.create_publisher(Bool, '/tracking/is_too_close', 10)
        self.too_far_pub = self.create_publisher(Bool, '/tracking/is_too_far', 10)

        self.latest_detection = {
            'found': False,
            'track_id': -1,
            'cx': -1,
            'cy': -1,
            'w': 0,
            'h': 0,
            'conf': 0.0,
            'frame_w': DEFAULT_FRAME_WIDTH,
            'frame_h': DEFAULT_FRAME_HEIGHT,
            'ts': 0.0,
        }

        self.lock = threading.Lock()
        self.running = True

        self.smoothed_ratio = None
        self.prev_ratio = None
        self.prev_cx = None

        self.confirmed_state = 'NEUTRAL'
        self.candidate_state = 'NEUTRAL'
        self.candidate_count = 0

        self.last_linear_x = 0.0
        self.last_angular_z = 0.0

        self.receiver_thread = threading.Thread(
            target=self.detection_receiver,
            daemon=True
        )
        self.receiver_thread.start()

        self.timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info(
            f'Tracking UDP receiver started on port {PINKY_RESULT_PORT}'
        )

    def publish_bool(self, publisher, value):
        msg = Bool()
        msg.data = bool(value)
        publisher.publish(msg)

    def reset_tracking_state(self):
        self.smoothed_ratio = None
        self.prev_ratio = None
        self.prev_cx = None

        self.confirmed_state = 'NEUTRAL'
        self.candidate_state = 'NEUTRAL'
        self.candidate_count = 0

        self.last_linear_x = 0.0
        self.last_angular_z = 0.0

        self.publish_bool(self.detection_pub, False)
        self.publish_bool(self.tracking_pub, False)
        self.publish_bool(self.moving_pub, False)
        self.publish_bool(self.too_close_pub, False)
        self.publish_bool(self.too_far_pub, False)

        self.cmd_pub.publish(Twist())

    def detection_receiver(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', PINKY_RESULT_PORT))
        sock.settimeout(0.2)

        self.get_logger().info(
            f'Listening detection result on 0.0.0.0:{PINKY_RESULT_PORT}'
        )

        try:
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.get_logger().warn(f'UDP socket error: {repr(e)}')
                    continue

                try:
                    msg = json.loads(data.decode('utf-8'))
                except Exception as e:
                    self.get_logger().warn(f'JSON decode failed: {repr(e)}')
                    continue

                if 'ts' not in msg:
                    msg['ts'] = time.time()

                with self.lock:
                    self.latest_detection = msg

        finally:
            sock.close()
            self.get_logger().info('UDP socket closed')

    def update_state_with_debounce(self, raw_state):
        if raw_state == self.candidate_state:
            self.candidate_count += 1
        else:
            self.candidate_state = raw_state
            self.candidate_count = 1

        if self.candidate_count >= STATE_DEBOUNCE_FRAMES:
            self.confirmed_state = self.candidate_state

    def control_loop(self):
        with self.lock:
            det = dict(self.latest_detection)

        now = time.time()

        found = bool(det.get('found', False))
        ts = float(det.get('ts', 0.0))
        result_too_old = (now - ts) > RESULT_TIMEOUT_SEC

        if (not found) or result_too_old:
            self.reset_tracking_state()
            return

        frame_w = int(det.get('frame_w', DEFAULT_FRAME_WIDTH))
        frame_h = int(det.get('frame_h', DEFAULT_FRAME_HEIGHT))

        cx = int(det.get('cx', frame_w // 2))
        cy = int(det.get('cy', frame_h // 2))

        if FLIP_X:
            cx = frame_w - cx
        if FLIP_Y:
            cy = frame_h - cy

        w = int(det.get('w', 0))
        h = int(det.get('h', 0))
        conf = float(det.get('conf', 0.0))
        track_id = int(det.get('track_id', -1))

        # bbox 비율 계산 (해상도 무관)
        frame_area = float(frame_w * frame_h)
        if frame_area <= 0:
            self.reset_tracking_state()
            return

        raw_area = w * h
        raw_ratio = raw_area / frame_area

        if raw_ratio < MIN_VALID_RATIO:
            self.reset_tracking_state()
            return

        # EMA 평활
        if self.smoothed_ratio is None:
            self.smoothed_ratio = raw_ratio
        else:
            self.smoothed_ratio = (
                RATIO_EMA_ALPHA * raw_ratio +
                (1.0 - RATIO_EMA_ALPHA) * self.smoothed_ratio
            )

        err_x = cx - (frame_w // 2)
        ratio_err = TARGET_BBOX_RATIO - self.smoothed_ratio

        # 단일 임계치 기반 raw 상태 판정 (hysteresis 제거)
        if ratio_err > RATIO_THRESHOLD:
            raw_state = 'FAR'
        elif ratio_err < -RATIO_THRESHOLD:
            raw_state = 'CLOSE'
        else:
            raw_state = 'NEUTRAL'

        # 디바운싱
        self.update_state_with_debounce(raw_state)

        is_too_far = (self.confirmed_state == 'FAR')
        is_too_close = (self.confirmed_state == 'CLOSE')

        is_center_moving = False
        is_ratio_moving = False

        if self.prev_cx is not None:
            is_center_moving = abs(cx - self.prev_cx) > MOVING_CENTER_THRESHOLD

        if self.prev_ratio is not None:
            is_ratio_moving = abs(self.smoothed_ratio - self.prev_ratio) > MOVING_RATIO_THRESHOLD

        is_moving = is_center_moving or is_ratio_moving

        self.prev_cx = cx
        self.prev_ratio = self.smoothed_ratio

        # 명령값 계산
        angular_z_target = -TURN_GAIN * err_x

        if self.confirmed_state == 'NEUTRAL':
            linear_x_target = 0.0
        else:
            linear_x_target = -DIST_GAIN_RATIO * ratio_err

        if REAR_CAMERA and REAR_CAMERA_FLIP_ANGULAR:
            angular_z_target *= -1.0

        if abs(err_x) <= CENTER_DEAD_BAND:
            angular_z_target = 0.0

        if linear_x_target >= 0.0:
            linear_x_target = clamp(linear_x_target, 0.0, MAX_LINEAR_X)
        else:
            linear_x_target = clamp(linear_x_target, -MAX_LINEAR_X_BACKWARD, 0.0)

        angular_z_target = clamp(angular_z_target, -MAX_ANGULAR_Z, MAX_ANGULAR_Z)

        linear_x = slew(linear_x_target, self.last_linear_x, LINEAR_SLEW_RATE)
        angular_z = slew(angular_z_target, self.last_angular_z, ANGULAR_SLEW_RATE)

        self.last_linear_x = linear_x
        self.last_angular_z = angular_z

        cmd = Twist()
        cmd.linear.x = linear_x
        cmd.angular.z = angular_z

        self.publish_bool(self.detection_pub, True)
        self.publish_bool(self.tracking_pub, True)
        self.publish_bool(self.moving_pub, is_moving)
        self.publish_bool(self.too_close_pub, is_too_close)
        self.publish_bool(self.too_far_pub, is_too_far)

        self.cmd_pub.publish(cmd)

        self.get_logger().info(
            f'track_id={track_id} conf={conf:.2f} '
            f'cx={cx} err_x={err_x} '
            f'raw_ratio={raw_ratio:.3f} smooth={self.smoothed_ratio:.3f} '
            f'ratio_err={ratio_err:+.3f} '
            f'raw={raw_state} confirmed={self.confirmed_state} '
            f'cmd.linear.x={linear_x:.3f} cmd.angular.z={angular_z:.3f}'
        )

    def destroy_node(self):
        self.running = False
        self.cmd_pub.publish(Twist())
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TrackingNode()

    try:
        rclpy.spin(node)
    finally:
        node.running = False
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()