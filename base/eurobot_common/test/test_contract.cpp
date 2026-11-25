#include <gtest/gtest.h>

#include <string>

#include "eurobot_common/contract.hpp"

using eurobot_common::contract::HEARTBEAT;
using eurobot_common::contract::LOCALIZATION_POSE;
using eurobot_common::contract::STARTUP_STATUS;

TEST(Contract, SensorTopicsAreBestEffortKeepLast1) {
  auto qos = HEARTBEAT.qos().get_rmw_qos_profile();
  EXPECT_EQ(qos.reliability, RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
  EXPECT_EQ(qos.depth, 1u);
}

// Nav2 subscribes to odometry as reliable; a best_effort publisher would never match.
TEST(Contract, StreamTopicsAreReliableKeepLast10) {
  auto qos = LOCALIZATION_POSE.qos().get_rmw_qos_profile();
  EXPECT_EQ(qos.reliability, RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  EXPECT_EQ(qos.durability, RMW_QOS_POLICY_DURABILITY_VOLATILE);
  EXPECT_EQ(qos.depth, 10u);
}

TEST(Contract, StateTopicsLatch) {
  auto qos = STARTUP_STATUS.qos().get_rmw_qos_profile();
  EXPECT_EQ(qos.durability, RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);
  EXPECT_EQ(std::string(STARTUP_STATUS.name), "/robot/startup/status");
}
