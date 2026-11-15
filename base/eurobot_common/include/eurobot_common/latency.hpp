// Clock rules (see docs/logging.md):
//   - durations, timeouts, rates  -> std::chrono::steady_clock (never jumps)
//   - message stamps, log lines   -> ROS time (system clock, NTP/chrony-synced across machines)
// Comparing a header.stamp with now() therefore measures end-to-end latency
// *across machines*, and is only meaningful when their clocks are synced.
#pragma once

#include <builtin_interfaces/msg/time.hpp>
#include <rclcpp/rclcpp.hpp>

namespace eurobot_common {

// Age of a stamped message in milliseconds (negative => clocks are not synced).
inline double stamp_age_ms(rclcpp::Node & node, const builtin_interfaces::msg::Time & stamp) {
  return (node.now() - rclcpp::Time(stamp, node.get_clock()->get_clock_type())).seconds() * 1e3;
}

}  // namespace eurobot_common
