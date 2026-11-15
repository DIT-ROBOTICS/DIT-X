#!/usr/bin/env python3
"""Wait until main reports every domain ready, and every domain sends heartbeats."""

import argparse
import sys
import time

from eurobot_common import contract
from eurobot_interfaces.msg import ModuleHeartbeat, StartupStatus
import rclpy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domains', required=True)
    ap.add_argument('--timeout', type=float, default=45)
    a = ap.parse_args()
    want = set(a.domains.split(','))

    rclpy.init()
    node = rclpy.create_node('integration_check')
    status, beats = [None], {}
    node.create_subscription(
        StartupStatus,
        contract.STARTUP_STATUS.name,
        lambda m: status.__setitem__(0, m),
        contract.STARTUP_STATUS.qos(),
    )
    node.create_subscription(
        ModuleHeartbeat,
        contract.HEARTBEAT.name,
        lambda m: beats.setdefault(m.domain, m),
        contract.HEARTBEAT.qos(),
    )
    start = time.monotonic()
    ok = False
    while time.monotonic() - start < a.timeout:
        rclpy.spin_once(node, timeout_sec=0.2)
        s = status[0]
        if s and s.all_ready and want <= set(s.ready_domains) and want <= set(beats):
            ok = True
            break
    s = status[0]
    took = time.monotonic() - start
    if ok:
        print(
            f'OK    startup handshake: {", ".join(sorted(s.ready_domains))} ready after {took:.1f}s'
        )
    else:
        print(
            f'FAIL  startup handshake not complete after {a.timeout:.0f}s: '
            f'ready={list(s.ready_domains) if s else "no status from main"}, '
            f'missing={list(s.missing_domains) if s else sorted(want)}, '
            f'heartbeats from {sorted(beats)}'
        )
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
