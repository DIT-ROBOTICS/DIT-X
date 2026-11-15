// Startup handshake + heartbeat for one module, in one line:
//
//   reporter_ = std::make_unique<eurobot_common::StartupReporter>(*this, "localization", "fusion");
//   ...
//   reporter_->ready();   // once the module can do its job
//
// It keeps calling /robot/startup/ready_signal until main accepts, and publishes
// a heartbeat every second whose uptime comes from a steady (monotonic) clock.
#pragma once

#include <chrono>
#include <memory>
#include <string>
#include <utility>

#include <rclcpp/rclcpp.hpp>

#include "eurobot_common/contract.hpp"
#include "eurobot_interfaces/msg/module_heartbeat.hpp"
#include "eurobot_interfaces/srv/ready_signal.hpp"

namespace eurobot_common {

class StartupReporter {
public:
  using Heartbeat = eurobot_interfaces::msg::ModuleHeartbeat;
  using ReadySignal = eurobot_interfaces::srv::ReadySignal;

  StartupReporter(rclcpp::Node & node, std::string domain, std::string module)
      : node_(node),
        domain_(std::move(domain)),
        module_(std::move(module)),
        started_(std::chrono::steady_clock::now()) {
    heartbeat_pub_ =
        node_.create_publisher<Heartbeat>(contract::HEARTBEAT.name, contract::HEARTBEAT.qos());
    client_ = node_.create_client<ReadySignal>(contract::READY_SIGNAL.name);
    timer_ = node_.create_wall_timer(std::chrono::seconds(1), [this] { tick(); });
  }

  // Report READY (or ERROR) to main; retried every second until accepted.
  void ready() { set_state(ReadySignal::Request::STATE_READY); }
  void error(const std::string & detail) {
    detail_ = detail;
    level_ = Heartbeat::ERROR;
    set_state(ReadySignal::Request::STATE_ERROR);
  }
  void set_health(uint8_t level, std::string detail) {
    level_ = level;
    detail_ = std::move(detail);
  }
  bool accepted() const { return accepted_; }

private:
  void set_state(uint8_t state) {
    state_ = state;
    accepted_ = false;
    tick();
  }

  void tick() {
    Heartbeat hb;
    hb.header.stamp = node_.now();
    hb.domain = domain_;
    hb.module = module_;
    hb.level = level_;
    hb.uptime_sec =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - started_).count();
    hb.detail = detail_;
    heartbeat_pub_->publish(hb);

    if (state_ == ReadySignal::Request::STATE_BOOTING || accepted_ || in_flight_) {
      return;
    }
    if (!client_->service_is_ready()) {
      RCLCPP_INFO_THROTTLE(node_.get_logger(),
                           *node_.get_clock(),
                           5000,
                           "waiting for %s",
                           contract::READY_SIGNAL.name);
      return;
    }
    auto req = std::make_shared<ReadySignal::Request>();
    req->domain = domain_;
    req->module = module_;
    req->state = state_;
    in_flight_ = true;
    client_->async_send_request(req, [this](rclcpp::Client<ReadySignal>::SharedFuture f) {
      in_flight_ = false;
      auto res = f.get();
      accepted_ = res->accepted;
      if (!accepted_) {
        RCLCPP_ERROR(node_.get_logger(), "startup rejected: %s", res->message.c_str());
      }
    });
  }

  rclcpp::Node & node_;
  std::string domain_, module_, detail_;
  std::chrono::steady_clock::time_point started_;
  uint8_t state_{ReadySignal::Request::STATE_BOOTING};
  uint8_t level_{Heartbeat::OK};
  bool accepted_{false};
  bool in_flight_{false};
  rclcpp::Publisher<Heartbeat>::SharedPtr heartbeat_pub_;
  rclcpp::Client<ReadySignal>::SharedPtr client_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace eurobot_common
