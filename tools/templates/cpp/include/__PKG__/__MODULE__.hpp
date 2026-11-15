// Pure logic of __PKG__, kept free of ROS so it can be unit-tested directly.
// Put the algorithm here; the node only moves data in and out.
#pragma once

namespace __PKG__ {

// First-order low-pass filter: y += alpha * (x - y). alpha in (0, 1], 1 = no smoothing.
class ExponentialFilter {
public:
  explicit ExponentialFilter(double alpha) : alpha_(alpha) {}

  double update(double x) {
    value_ = initialized_ ? value_ + alpha_ * (x - value_) : x;
    initialized_ = true;
    return value_;
  }

  double value() const { return value_; }

private:
  double alpha_;
  double value_{0.0};
  bool initialized_{false};
};

}  // namespace __PKG__
