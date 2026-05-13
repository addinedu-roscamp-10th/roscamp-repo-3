#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time

import rclpy
from rclpy.node import Node
from pinky_interfaces.srv import SetLed
from std_msgs.msg import Bool

# 실제 Buzzer 위치에 맞게 import 경로가 다르면 여기만 수정하면 됨
from ropi_patrol.buzzer import Buzzer


ALARM_TOPIC = "/fall_alarm"
LED_SERVICE_NAME = "/set_led"


class FallenAlarm(Node):
    def __init__(self):
        super().__init__("fallen_alarm")

        self.alarm_active = False
        self.stop_event = threading.Event()

        self.buzzer = Buzzer()
        self.led_client = self.create_client(SetLed, LED_SERVICE_NAME)
        self.led_blink_interval_sec = 0.5
        self.last_led_service_warn_at = 0.0

        self.sub = self.create_subscription(
            Bool,
            ALARM_TOPIC,
            self.alarm_callback,
            10,
        )

        # 부저를 ROS callback 안에서 직접 오래 울리면 callback이 막힐 수 있으므로
        # 부저 동작만 별도 thread에서 처리
        self.buzzer_thread = threading.Thread(
            target=self.buzzer_loop,
            daemon=True,
        )
        self.buzzer_thread.start()

        self.led_thread = threading.Thread(
            target=self.led_loop,
            daemon=True,
        )
        self.led_thread.start()

        self.get_logger().info("Fallen alarm node started.")

    def alarm_callback(self, msg):
        """
        /fall_alarm 토픽 수신

        True  -> 부저 ON
        False -> 부저 OFF
        """
        self.alarm_active = bool(msg.data)
        self.get_logger().info(f"Alarm state: {self.alarm_active}")

    def buzzer_loop(self):
        """
        alarm_active가 True인 동안 부저를 반복해서 울림
        False가 되면 부저 정지
        """
        buzzer_started = False

        while not self.stop_event.is_set():
            try:
                if self.alarm_active:
                    if not buzzer_started:
                        self.buzzer.buzzer_start()
                        buzzer_started = True

                    # 2초 동안 부저 울림
                    self.buzzer.buzzer(2)

                else:
                    if buzzer_started:
                        self.buzzer.buzzer_stop()
                        buzzer_started = False

                    time.sleep(0.1)

            except Exception as e:
                self.get_logger().error(f"Buzzer error: {e}")
                time.sleep(0.5)

        # 종료 시 부저 정지
        try:
            self.buzzer.buzzer_stop()
        except Exception:
            pass

    def led_loop(self):
        """
        alarm_active가 True인 동안 LED 전체를 빨간색으로 깜빡임
        False가 되면 LED를 clear
        """
        led_on = False

        while not self.stop_event.is_set():
            try:
                if self.alarm_active:
                    self._call_led_service("fill", 255, 0, 0)
                    led_on = True
                    time.sleep(self.led_blink_interval_sec)

                    if self.stop_event.is_set():
                        break

                    self._call_led_service("clear")
                    led_on = False
                    time.sleep(self.led_blink_interval_sec)

                else:
                    if led_on:
                        self._call_led_service("clear")
                        led_on = False

                    time.sleep(0.1)

            except Exception as e:
                self.get_logger().error(f"LED error: {e}")
                time.sleep(0.5)

        try:
            self._call_led_service("clear")
        except Exception:
            pass

    def _call_led_service(self, command, r=0, g=0, b=0):
        if not self.led_client.wait_for_service(timeout_sec=0.1):
            now = time.monotonic()
            if now - self.last_led_service_warn_at >= 5.0:
                self.get_logger().warn(f"LED service not available: {LED_SERVICE_NAME}")
                self.last_led_service_warn_at = now
            return

        request = SetLed.Request()
        request.command = command
        request.pixels = []
        request.r = int(r)
        request.g = int(g)
        request.b = int(b)

        future = self.led_client.call_async(request)
        future.add_done_callback(self._handle_led_response)

    def _handle_led_response(self, future):
        try:
            response = future.result()
        except Exception as e:
            self.get_logger().error(f"LED service call failed: {e}")
            return

        if response is not None and not response.success:
            self.get_logger().warn(f"LED service rejected command: {response.message}")

    def close(self):
        """
        부저 자원 반환 및 LED clear
        """
        self.stop_event.set()

        try:
            self.buzzer.buzzer_stop()
        except Exception:
            pass

        try:
            self._call_led_service("clear")
        except Exception:
            pass

        try:
            self.buzzer.close()
        except Exception:
            pass

        self.get_logger().info("Fallen alarm node closed.")


def main(args=None):
    rclpy.init(args=args)

    node = FallenAlarm()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
