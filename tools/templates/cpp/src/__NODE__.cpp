// __NODE__ of the __DOMAIN__ domain.
//
// Starter node: runs a loop at `rate_hz`, measures its own period with the
// steady clock and warns when it falls behind. Replace loop() with the real
// work; for cross-domain topics use the generated contract, e.g.
//   create_publisher<Msg>(contract::LOCALIZATION_POSE.name, contract::LOCALIZATION_POSE.qos())
#include <chrono>
#include <memory>

#include <rclcpp/rclcpp.hpp>

#include "__PKG__/__MODULE__.hpp"
#include "eurobot_common/contract.hpp"
#include "eurobot_common/startup_reporter.hpp"

namespace __PKG__ {

class __CLASS__ : public rclcpp::Node {
public:
  __CLASS__()
      : Node("__MODULE__"),
        rate_hz_(declare_parameter("rate_hz", 10.0)),
        period_filter_(declare_parameter("smoothing", 0.2)),
        last_(std::chrono::steady_clock::now()) {
    timer_ = create_wall_timer(std::chrono::duration<double>(1.0 / rate_hz_), [this] { loop(); });
    reporter_ =
        std::make_unique<eurobot_common::StartupReporter>(*this, "__DOMAIN__", "__MODULE__");
    reporter_->ready();  // call this once the module can actually do its job
  }

private:
  void loop() {
    const auto now = std::chrono::steady_clock::now();
    const double period = period_filter_.update(std::chrono::duration<double>(now - last_).count());
    last_ = now;
    if (period > 1.5 / rate_hz_) {
      RCLCPP_WARN_THROTTLE(get_logger(),
                           *get_clock(),
                           5000,
                           "loop running slow: %.1f ms (want %.1f ms)",
                           period * 1e3,
                           1e3 / rate_hz_);
    }
    // TODO: the actual work of this module.
  }

  double rate_hz_;
  ExponentialFilter period_filter_;
  std::chrono::steady_clock::time_point last_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::unique_ptr<eurobot_common::StartupReporter> reporter_;
};

}  // namespace __PKG__

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<__PKG__::__CLASS__>());
  rclcpp::shutdown();
  return 0;
}
