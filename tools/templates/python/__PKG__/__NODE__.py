"""__NODE__ of the __DOMAIN__ domain.

Starter node: runs a loop at `rate_hz`, measures its own period with the steady
clock and warns when it falls behind. Replace loop() with the real work; for
cross-domain topics use the generated contract, e.g.
    self.create_publisher(Msg, contract.LOCALIZATION_POSE.name, contract.LOCALIZATION_POSE.qos())
"""

import time

from eurobot_common.startup import StartupReporter
import rclpy
from rclpy.node import Node

from __PKG__.__MODULE__ import ExponentialFilter


class __CLASS__(Node):
    def __init__(self):
        super().__init__('__MODULE__')
        self.rate_hz = self.declare_parameter('rate_hz', 10.0).value
        self.period = ExponentialFilter(self.declare_parameter('smoothing', 0.2).value)
        self.last = time.monotonic()  # steady clock: never jumps with NTP
        self.create_timer(1.0 / self.rate_hz, self.loop)
        self.reporter = StartupReporter(self, '__DOMAIN__', '__MODULE__')
        self.reporter.ready()  # call this once the module can actually do its job

    def loop(self):
        now = time.monotonic()
        period = self.period.update(now - self.last)
        self.last = now
        if period > 1.5 / self.rate_hz:
            self.get_logger().warn(
                f'loop running slow: {period * 1e3:.1f} ms (want {1e3 / self.rate_hz:.1f} ms)',
                throttle_duration_sec=5.0,
            )
        # TODO: the actual work of this module.


def main():
    rclpy.init()
    node = __CLASS__()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
