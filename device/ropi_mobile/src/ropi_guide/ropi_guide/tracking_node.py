import json
import time
import traceback
import socket
import cv2

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist

from PIL import Image
from pinkylib import Camera

LCD_AVAILABLE = True
LCD_IMPORT_ERROR = None

try:
    from pinky_lcd import LCD
except Exception as e:
    LCD_AVAILABLE = False
    LCD_IMPORT_ERROR = e


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class TrackingNode(Node):

    def __init__(self):
        super().__init__('tracking_node')

        # =========================
        # Camera / UDP Parameters
        # =========================
        self.declare_parameter('server_ip', '')
        self.declare_parameter('server_video_port', 5005)
        self.declare_parameter('result_port', 6006)
        self.declare_parameter('jpeg_quality', 45)

        self.declare_parameter('cam_width', 320)
        self.declare_parameter('cam_height', 240)

        self.declare_parameter('socket_recv_timeout_sec', 0.001)

        # =========================
        # ROS Parameters
        # =========================
        self.declare_parameter('detection_topic', 'tracking')
        self.declare_parameter('cmd_vel_topic', '/tracking_cmd_vel')

        # =========================
        # Tracking Parameters
        # =========================
        self.declare_parameter('center_dead_band', 20)
        self.declare_parameter('area_dead_band', 5000)
        self.declare_parameter('min_valid_area', 1200)

        self.declare_parameter('turn_gain', 0.0035)
        self.declare_parameter('dist_gain', 0.00003)

        self.declare_parameter('result_timeout_sec', 2.0)

        self.declare_parameter('target_bbox_area', 38000)
        self.declare_parameter('area_ema_alpha', 0.35)

        self.declare_parameter('big_turn_err_px', 80)
        self.declare_parameter('big_turn_forward_scale', 0.5)

        self.declare_parameter('max_linear_x', 0.20)
        self.declare_parameter('max_angular_z', 1.20)

        self.declare_parameter('control_period_sec', 0.05)

        # =========================
        # Load Parameters
        # =========================
        self.server_ip = self.get_parameter('server_ip').value
        self.video_port = self.get_parameter('server_video_port').value
        self.result_port = self.get_parameter('result_port').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value

        self.CAM_WIDTH = self.get_parameter('cam_width').value
        self.CAM_HEIGHT = self.get_parameter('cam_height').value
        self.socket_recv_timeout_sec = self.get_parameter('socket_recv_timeout_sec').value

        self.detection_topic = self.get_parameter('detection_topic').value
        self.cmd_vel_topic = self.get_parameter('cmd_vel_topic').value

        self.CENTER_DEAD_BAND = self.get_parameter('center_dead_band').value
        self.AREA_DEAD_BAND = self.get_parameter('area_dead_band').value
        self.MIN_VALID_AREA = self.get_parameter('min_valid_area').value

        self.TURN_GAIN = self.get_parameter('turn_gain').value
        self.DIST_GAIN = self.get_parameter('dist_gain').value

        self.RESULT_TIMEOUT_SEC = self.get_parameter('result_timeout_sec').value

        self.TARGET_BBOX_AREA = self.get_parameter('target_bbox_area').value
        self.AREA_EMA_ALPHA = self.get_parameter('area_ema_alpha').value

        self.BIG_TURN_ERR_PX = self.get_parameter('big_turn_err_px').value
        self.BIG_TURN_FORWARD_SCALE = self.get_parameter('big_turn_forward_scale').value

        self.MAX_LINEAR_X = self.get_parameter('max_linear_x').value
        self.MAX_ANGULAR_Z = self.get_parameter('max_angular_z').value

        self.control_period_sec = self.get_parameter('control_period_sec').value

        if not str(self.server_ip).strip():
            raise ValueError(
                'server_ip parameter is required. '
                'Use guide.launch.py or pass --ros-args -p server_ip:=...'
            )

        # =========================
        # State
        # =========================
        self.latest_detection = {
            "found": False,
            "track_id": -1,
            "cx": -1,
            "cy": -1,
            "w": 0,
            "h": 0,
            "conf": 0.0,
            "frame_w": self.CAM_WIDTH,
            "frame_h": self.CAM_HEIGHT,
            "ts": 0.0,
        }

        self.smoothed_area = None
        self.lcd_red_shown = False
        self.last_log_time = 0.0

        # =========================
        # ROS interfaces
        # =========================
        self.det_pub = self.create_publisher(
            String,
            self.detection_topic,
            10
        )

        self.cmd_pub = self.create_publisher(
            Twist,
            self.cmd_vel_topic,
            10
        )

        # =========================
        # Camera
        # =========================
        self.cam = Camera()
        self.cam.start(width=self.CAM_WIDTH, height=self.CAM_HEIGHT)

        # =========================
        # UDP sockets
        # =========================
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.bind(("0.0.0.0", self.result_port))
        self.sock_recv.settimeout(float(self.socket_recv_timeout_sec))

        # =========================
        # LCD
        # =========================
        self.lcd = self.safe_create_lcd()

        if self.lcd is not None:
            self.show_lcd_color((0, 0, 255))
            time.sleep(1.0)
            self.clear_lcd()

        # =========================
        # Timer
        # =========================
        self.timer = self.create_timer(
            self.control_period_sec,
            self.loop
        )

        self.get_logger().info(
            f'tracking node started: '
            f'server_ip={self.server_ip}, '
            f'video_port={self.video_port}, '
            f'result_port={self.result_port}, '
            f'detection_topic={self.detection_topic}, '
            f'cmd_vel_topic={self.cmd_vel_topic}'
        )

    # =========================================================
    # LCD helpers
    # =========================================================
    def safe_create_lcd(self):
        if not LCD_AVAILABLE:
            self.get_logger().warning(
                f'LCD import failed: {repr(LCD_IMPORT_ERROR)}'
            )
            return None

        try:
            lcd = LCD()
            self.get_logger().info('LCD initialized')
            return lcd
        except Exception as e:
            self.get_logger().error(f'LCD init failed: {repr(e)}')
            traceback.print_exc()
            return None

    def show_lcd_color(self, color):
        if self.lcd is None:
            return

        try:
            img = Image.new("RGB", (320, 240), color=color)
            self.lcd.img_show(img)
        except Exception as e:
            self.get_logger().error(f'LCD show failed: {repr(e)}')
            traceback.print_exc()

    def clear_lcd(self):
        if self.lcd is None:
            return

        try:
            if hasattr(self.lcd, 'clear'):
                self.lcd.clear()
        except Exception as e:
            self.get_logger().error(f'LCD clear failed: {repr(e)}')
            traceback.print_exc()

    # =========================================================
    # Logging helper
    # =========================================================
    def log_throttled(self, text, interval=0.5):
        now = time.time()
        if now - self.last_log_time >= interval:
            self.get_logger().info(text)
            self.last_log_time = now

    # =========================================================
    # Detection publish/update
    # =========================================================
    def publish_detection(self, data: dict):
        ros_msg = String()
        ros_msg.data = json.dumps(data)
        self.det_pub.publish(ros_msg)

    def update_latest_detection(self, data: dict):
        if 'ts' not in data:
            data['ts'] = time.time()

        if 'frame_w' not in data:
            data['frame_w'] = self.CAM_WIDTH

        if 'frame_h' not in data:
            data['frame_h'] = self.CAM_HEIGHT

        self.latest_detection = data
        self.publish_detection(data)

    # =========================================================
    # Camera / UDP
    # =========================================================
    def send_frame_to_server(self):
        frame = self.cam.get_frame()
        if frame is None:
            return

        ok, enc = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, int(self.jpeg_quality)]
        )
        if not ok:
            return

        data = enc.tobytes()

        try:
            self.sock_send.sendto(data, (self.server_ip, self.video_port))
        except Exception as e:
            self.get_logger().warning(f'send error: {repr(e)}')

    def receive_server_result(self):
        while True:
            try:
                data, _ = self.sock_recv.recvfrom(4096)
            except socket.timeout:
                break
            except BlockingIOError:
                break
            except Exception as e:
                self.get_logger().warning(f'recv socket error: {repr(e)}')
                break

            try:
                msg = json.loads(data.decode())
                self.update_latest_detection(msg)
            except Exception as e:
                self.get_logger().warning(f'recv parse error: {repr(e)}')

    # =========================================================
    # Motion helpers
    # =========================================================
    def publish_cmd_vel(self, linear_x: float, angular_z: float):
        twist = Twist()
        twist.linear.x = float(clamp(linear_x, -self.MAX_LINEAR_X, self.MAX_LINEAR_X))
        twist.angular.z = float(clamp(angular_z, -self.MAX_ANGULAR_Z, self.MAX_ANGULAR_Z))
        self.cmd_pub.publish(twist)

    def stop_robot(self):
        self.publish_cmd_vel(0.0, 0.0)

    # =========================================================
    # Tracking control
    # =========================================================
    def control_from_latest_detection(self):
        det = dict(self.latest_detection)

        now = time.time()
        found = bool(det.get("found", False))
        ts = float(det.get("ts", 0.0))
        age = now - ts
        result_too_old = age > self.RESULT_TIMEOUT_SEC

        if (not found) or result_too_old:
            self.stop_robot()
            self.smoothed_area = None

            if self.lcd_red_shown:
                self.clear_lcd()
                self.lcd_red_shown = False

            self.log_throttled(
                f'no valid detection -> stop '
                f'(found={found}, age={age:.2f}, timeout={self.RESULT_TIMEOUT_SEC:.2f})'
            )
            return

        if not self.lcd_red_shown:
            self.show_lcd_color((255, 0, 0))
            self.lcd_red_shown = True

        frame_w = int(det.get("frame_w", self.CAM_WIDTH))
        cx = int(det.get("cx", frame_w // 2))
        w = int(det.get("w", 0))
        h = int(det.get("h", 0))
        conf = float(det.get("conf", 0.0))

        err_x = cx - (frame_w // 2)
        raw_area = w * h

        if raw_area < self.MIN_VALID_AREA:
            self.stop_robot()
            self.log_throttled(
                f'bbox too small -> stop (area={raw_area}, min={self.MIN_VALID_AREA})'
            )
            return

        # EMA smoothing
        if self.smoothed_area is None:
            self.smoothed_area = float(raw_area)
        else:
            self.smoothed_area = (
                self.AREA_EMA_ALPHA * raw_area
                + (1.0 - self.AREA_EMA_ALPHA) * self.smoothed_area
            )

        area_err = self.TARGET_BBOX_AREA - self.smoothed_area

        angular_z = 0.0
        linear_x = 0.0

        # 좌우 회전
        if abs(err_x) > self.CENTER_DEAD_BAND:
            angular_z = -self.TURN_GAIN * err_x

        # 전후 이동
        if abs(area_err) > self.AREA_DEAD_BAND:
            linear_x = self.DIST_GAIN * area_err

        # 많이 틀어져 있을 때는 전진/후진 줄이기
        if abs(err_x) >= self.BIG_TURN_ERR_PX:
            linear_x *= self.BIG_TURN_FORWARD_SCALE

        linear_x = clamp(linear_x, -self.MAX_LINEAR_X, self.MAX_LINEAR_X)
        angular_z = clamp(angular_z, -self.MAX_ANGULAR_Z, self.MAX_ANGULAR_Z)

        self.publish_cmd_vel(linear_x, angular_z)

        self.log_throttled(
            f'found={found} '
            f'id={det.get("track_id")} '
            f'conf={conf:.2f} '
            f'cx={cx} err_x={err_x} '
            f'w={w} h={h} '
            f'raw_area={raw_area} smooth_area={self.smoothed_area:.1f} '
            f'target_area={self.TARGET_BBOX_AREA} area_err={area_err:.1f} '
            f'linear_x={linear_x:.3f} angular_z={angular_z:.3f}'
        )

    # =========================================================
    # Main loop
    # =========================================================
    def loop(self):
        self.send_frame_to_server()
        self.receive_server_result()
        self.control_from_latest_detection()

    def destroy_node(self):
        try:
            self.stop_robot()
        except Exception:
            pass

        try:
            self.clear_lcd()
        except Exception:
            pass

        try:
            self.sock_send.close()
        except Exception:
            pass

        try:
            self.sock_recv.close()
        except Exception:
            pass

        try:
            self.cam.stop()
        except Exception:
            pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TrackingNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('tracking node interrupted')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
