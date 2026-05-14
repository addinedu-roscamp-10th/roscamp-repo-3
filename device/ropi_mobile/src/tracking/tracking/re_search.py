import cv2
import socket
import struct
import threading
import time
import json
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool

from tracking.camera import Camera
from PIL import Image


LCD_AVAILABLE = True

try:
    from pinky_lcd import LCD
except Exception:
    LCD_AVAILABLE = False


SERVER_IP = "192.168.4.15"
# SERVER_IP = "192.168.0.59"
SERVER_VIDEO_PORT = 5005
PINKY_RESULT_PORT = 6007

MAX_DGRAM = 8192

CAM_WIDTH = 320
CAM_HEIGHT = 240
JPEG_QUALITY = 45

TARGET_FPS = 15
SEND_INTERVAL = 1.0 / TARGET_FPS

RESULT_TIMEOUT_SEC = 3.0

LCD_WIDTH = 320
LCD_HEIGHT = 240
LCD_IMAGE_PATH = Path(__file__).with_name("visitor_approval_dialog.png")


class VisitorDetectionNode(Node):
    def __init__(self):
        super().__init__("visitor_detection_node")

        self.declare_parameter("service_name", "/visitor/confirm_detection")
        self.service_name = str(self.get_parameter("service_name").value)

        self.visitor_pub = self.create_publisher(
            Bool,
            "/visitor/detected",
            10
        )

        # 머리 180도 회전을 위한 spin cmd_vel publisher
        self.spin_cmd_pub = self.create_publisher(
            Twist,
            "/spin/cmd_vel",
            10
        )

        # 서비스 호출 시 mission_manager에게 SPINNING 예약 요청
        self.spin_request_pub = self.create_publisher(
            Bool,
            "/visitor/spin_request",
            10
        )

        # mission_manager가 발행하는 /robot/mode 구독
        self.mode_sub = self.create_subscription(
            String,
            "/robot/mode",
            self.mode_callback,
            10
        )

        self.service = self.create_service(
            SetBool,
            self.service_name,
            self.visitor_detected_event_callback
        )

        self.latest_detection = {
            "found": False,
            "ts": 0.0,
        }

        self.lock = threading.Lock()
        self.running = True
        self.udp_active = True

        self.force_visitor_detected = False
        self.latched_visitor = False
        self.suppress_lcd_image = False

        self.lcd = None
        self.lcd_image_on = False
        self.lcd_image = None

        # 머리 180도 회전(spin) 관리
        self.prev_mode = ""
        self.spin_until = None
        self.spin_speed = 0.5
        self.spin_duration = 3.4 / self.spin_speed

        self.service_triggered = False

        if LCD_AVAILABLE:
            try:
                self.lcd = LCD()
            except Exception:
                self.lcd = None

        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.bind(("0.0.0.0", PINKY_RESULT_PORT))
        self.sock_recv.settimeout(0.2)

        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            1_000_000
        )

        self.cam = Camera()
        self.cam.start(width=CAM_WIDTH, height=CAM_HEIGHT)

        self.frame_id = 0
        self.last_send_time = 0.0

        self.recv_thread = threading.Thread(
            target=self.detection_receiver,
            daemon=True
        )
        self.recv_thread.start()

        self.camera_timer = self.create_timer(
            0.01,
            self.camera_sender_loop
        )

        self.state_timer = self.create_timer(
            0.05,
            self.publish_visitor_state
        )

        self.spin_timer = self.create_timer(
            0.02,
            self.publish_spin_cmd
        )

        self.get_logger().info(
            f"ready: service='{self.service_name}'"
        )

    def publish_visitor(self, value):
        msg = Bool()
        msg.data = bool(value)
        self.visitor_pub.publish(msg)

    def mode_callback(self, msg):
        mode = msg.data

        if mode == "SPINNING" and self.prev_mode != "SPINNING":
            now = self.get_clock().now().nanoseconds / 1_000_000_000.0
            self.spin_until = now + self.spin_duration

            if self.service_triggered:
                self.force_visitor_detected = True
                self.latched_visitor = True
                self.suppress_lcd_image = True

                with self.lock:
                    self.latest_detection = {
                        "found": True,
                        "ts": time.time(),
                    }

                self.stop_udp()
                self.publish_visitor(True)
                self.update_lcd_state(False)

                self.service_triggered = False

            self.get_logger().info(
                "mode = SPINNING -> 180 degree spin started"
            )

        self.prev_mode = mode

    def publish_spin_cmd(self):
        if self.spin_until is None:
            return

        now = self.get_clock().now().nanoseconds / 1_000_000_000.0
        cmd = Twist()

        if now < self.spin_until:
            cmd.angular.z = self.spin_speed
            self.spin_cmd_pub.publish(cmd)
            return

        self.spin_until = None
        self.spin_cmd_pub.publish(cmd)
        self.get_logger().info("180 degree spin finished")

    def visitor_detected_event_callback(self, request, response):
        if request.data:
            self.service_triggered = True

            spin_req = Bool()
            spin_req.data = True
            self.spin_request_pub.publish(spin_req)

            self.get_logger().info(
                "service called: spin_request=True published"
            )

            response.success = True
            response.message = (
                "spin_request published. "
                "spin will start when Nav2 finishes"
            )

        else:
            self.service_triggered = False
            self.force_visitor_detected = False
            self.latched_visitor = False
            self.suppress_lcd_image = False

            with self.lock:
                self.latest_detection = {
                    "found": False,
                    "ts": time.time(),
                }

            self.publish_visitor(False)
            self.update_lcd_state(False)

            self.spin_until = None
            self.spin_cmd_pub.publish(Twist())

            spin_req = Bool()
            spin_req.data = False
            self.spin_request_pub.publish(spin_req)

            response.success = True
            response.message = "visitor detection latch cleared"

        return response

    def stop_udp(self):
        if not self.udp_active:
            return

        self.udp_active = False

        for sock_name in ("sock_send", "sock_recv"):
            sock = getattr(self, sock_name, None)

            if sock is None:
                continue

            try:
                sock.close()
            except Exception:
                pass

        self.get_logger().info("UDP communication stopped")

    def load_lcd_image(self):
        if self.lcd_image is not None:
            return self.lcd_image

        img = Image.open(LCD_IMAGE_PATH).convert("RGB")
        self.lcd_image = img.resize((LCD_WIDTH, LCD_HEIGHT))

        return self.lcd_image

    def show_lcd_image(self):
        if self.lcd is None:
            return

        if self.lcd_image_on:
            return

        try:
            img = self.load_lcd_image()
            self.lcd.img_show(img)
            self.lcd_image_on = True
        except Exception:
            pass

    def clear_lcd(self):
        if self.lcd is None:
            return

        if not self.lcd_image_on:
            return

        try:
            if hasattr(self.lcd, "clear"):
                self.lcd.clear()
            else:
                img = Image.new(
                    "RGB",
                    (LCD_WIDTH, LCD_HEIGHT),
                    color=(0, 0, 0)
                )
                self.lcd.img_show(img)

            self.lcd_image_on = False

        except Exception:
            pass

    def update_lcd_state(self, visitor_detected):
        if visitor_detected:
            self.show_lcd_image()
        else:
            self.clear_lcd()

    def detection_receiver(self):
        try:
            while self.running and self.udp_active:
                try:
                    data, addr = self.sock_recv.recvfrom(4096)

                except socket.timeout:
                    continue

                except Exception:
                    if not self.udp_active:
                        break
                    continue

                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    continue

                if "ts" not in msg:
                    msg["ts"] = time.time()

                with self.lock:
                    self.latest_detection = msg

        finally:
            try:
                self.sock_recv.close()
            except Exception:
                pass

    def camera_sender_loop(self):
        if not self.udp_active:
            return

        now = time.time()

        if (now - self.last_send_time) < SEND_INTERVAL:
            return

        frame = self.cam.get_frame()

        if frame is None:
            return

        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
        )

        if not ok:
            return

        data = encoded.tobytes()
        total_chunks = (len(data) + MAX_DGRAM - 1) // MAX_DGRAM

        for chunk_idx in range(total_chunks):
            start = chunk_idx * MAX_DGRAM
            end = start + MAX_DGRAM
            chunk = data[start:end]

            header = struct.pack(
                "!IHH",
                self.frame_id,
                total_chunks,
                chunk_idx
            )

            try:
                self.sock_send.sendto(
                    header + chunk,
                    (SERVER_IP, SERVER_VIDEO_PORT)
                )

            except Exception:
                self.udp_active = False
                return

        self.frame_id += 1
        self.last_send_time = time.time()

    def publish_visitor_state(self):
        with self.lock:
            det = dict(self.latest_detection)

        found = bool(det.get("found", False))
        ts = float(det.get("ts", 0.0))
        result_too_old = (time.time() - ts) > RESULT_TIMEOUT_SEC

        current_detected = (
            self.force_visitor_detected
            or (found and not result_too_old)
        )

        if current_detected:
            self.latched_visitor = True

        visitor_detected = self.latched_visitor

        lcd_detected = visitor_detected and not self.suppress_lcd_image

        self.publish_visitor(visitor_detected)
        self.update_lcd_state(lcd_detected)

    def destroy_node(self):
        self.running = False

        self.publish_visitor(False)
        self.spin_cmd_pub.publish(Twist())
        self.clear_lcd()

        try:
            self.cam.close()
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

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VisitorDetectionNode()

    try:
        rclpy.spin(node)

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()