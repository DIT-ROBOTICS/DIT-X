"""Startup handshake + heartbeat for one module (Python twin of startup_reporter.hpp).

self.reporter = StartupReporter(self, 'vision', 'aruco')
...
self.reporter.ready()   # once the module can do its job
"""

import time

from eurobot_interfaces.msg import ModuleHeartbeat
from eurobot_interfaces.srv import ReadySignal

from eurobot_common import contract


class StartupReporter:
    def __init__(self, node, domain, module):
        self._node = node
        self._domain = domain
        self._module = module
        self._started = time.monotonic()  # steady clock: immune to NTP jumps
        self._state = ReadySignal.Request.STATE_BOOTING
        self._level = ModuleHeartbeat.OK
        self._detail = ''
        self._accepted = False
        self._future = None
        self._pub = node.create_publisher(
            ModuleHeartbeat, contract.HEARTBEAT.name, contract.HEARTBEAT.qos()
        )
        self._client = node.create_client(ReadySignal, contract.READY_SIGNAL.name)
        self._timer = node.create_timer(1.0, self._tick)

    @property
    def accepted(self):
        return self._accepted

    def ready(self):
        self._set_state(ReadySignal.Request.STATE_READY)

    def error(self, detail):
        self._level, self._detail = ModuleHeartbeat.ERROR, detail
        self._set_state(ReadySignal.Request.STATE_ERROR)

    def set_health(self, level, detail=''):
        self._level, self._detail = level, detail

    def _set_state(self, state):
        self._state, self._accepted = state, False
        self._tick()

    def _tick(self):
        hb = ModuleHeartbeat()
        hb.header.stamp = self._node.get_clock().now().to_msg()
        hb.domain, hb.module, hb.level, hb.detail = (
            self._domain,
            self._module,
            self._level,
            self._detail,
        )
        hb.uptime_sec = time.monotonic() - self._started
        self._pub.publish(hb)

        if self._state == ReadySignal.Request.STATE_BOOTING or self._accepted or self._future:
            return
        if not self._client.service_is_ready():
            self._node.get_logger().info(
                f'waiting for {contract.READY_SIGNAL.name}', throttle_duration_sec=5.0
            )
            return
        req = ReadySignal.Request(domain=self._domain, module=self._module, state=self._state)
        self._future = self._client.call_async(req)
        self._future.add_done_callback(self._on_response)

    def _on_response(self, future):
        self._future = None
        res = future.result()
        self._accepted = res.accepted
        if not res.accepted:
            self._node.get_logger().error(f'startup rejected: {res.message}')
