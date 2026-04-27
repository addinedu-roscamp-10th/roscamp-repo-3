#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

# 실제 Buzzer 위치에 맞게 import 경로가 다르면 여기만 수정하면 됨
from ropi_patrol.buzzer import Buzzer
from .pinkyled import LED


ALARM_TOPIC = "/fall_alarm"
RED = (255, 0, 0)
OFF = (0, 0, 0)


class FallenAlarm(Node):
    def __init__(self):
        super().__init__("fallen_alarm")

        self.alarm_active = False
        self.stop_event = threading.Event()

        self.buzzer = Buzzer()
        self.leds = Led()

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

        self.get_logger().info("Fallen alarm node started.")

    def alarm_callback(self, msg):
        """
        /fall_alarm 토픽 수신

        True  -> 부저 ON
        False -> 부저 OFF
        """
        self.alarm_active = bool(msg.data)
        self.get_logger().info(f"Alarm state: {self.alarm_active}")
    
    def alarm_loop(self):
        """
        alarm_active가 True인 동안:
            - 부저를 반복해서 울림
            - LED를 빨간색으로 깜빡임

        alarm_active가 False이면:
            - 부저 정지
            - LED OFF
        """
        buzzer_started = False
        led_on = False

        while not self.stop_event.is_set():
            try:
                if self.alarm_active:
                    # 부저 시작
                    if not buzzer_started:
                        self.buzzer.buzzer_start()
                        buzzer_started = True

                    # LED 빨간색 / OFF 번갈아 점등
                    if led_on:
                        self.leds.fill(OFF)
                        led_on = False
                    else:
                        self.leds.fill(RED)
                        led_on = True

                    # 부저를 짧게 울림
                    # 너무 길게 buzzer(2)를 쓰면 LED 깜빡임이 2초마다 바뀔 수 있음
                    self.buzzer.buzzer(1)

                    time.sleep(LED_BLINK_INTERVAL)

                else:
                    # alarm이 꺼진 경우 부저 정지
                    if buzzer_started:
                        self.buzzer.buzzer_stop()
                        buzzer_started = False

                    # LED OFF
                    if led_on:
                        self.leds.fill(OFF)
                        led_on = False

                    time.sleep(0.1)

            except Exception as e:
                self.get_logger().error(f"Alarm device error: {e}")
                time.sleep(0.5)

        # 노드 종료 시 부저와 LED 정리
        try:
            self.buzzer.buzzer_stop()
        except Exception:
            pass

        try:
            self.leds.fill(OFF)
        except Exception:
            pass

    def close(self):
        """
        부저 자원 반환
        """
        self.stop_event.set()

        try:
            self.buzzer.buzzer_stop()
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