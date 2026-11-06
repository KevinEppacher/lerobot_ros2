// Copyright 2026 Kevin Eppacher
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <gtest/gtest.h>

#include <cstddef>
#include <cstdint>
#include <memory>
#include <utility>
#include <type_traits>
#include <vector>

#include <pluginlib/class_loader.hpp>

#include "hiwonder_lerobot_cpp/follower.hpp"
#include "hiwonder_lerobot_cpp/leader.hpp"
#include "lerobot_cpp/robot.hpp"

// Verify that Follower satisfies the generic Robot interface.
TEST(RobotInterfaceTest, FollowerImplementsRobotInterface)
{
  static_assert(
    std::is_base_of_v<lerobot::Robot, hiwonder::Follower>);

  static_assert(
    std::is_default_constructible_v<hiwonder::Follower>);
}

// Verify that Leader satisfies the generic Robot interface.
TEST(RobotInterfaceTest, LeaderImplementsRobotInterface)
{
  static_assert(
    std::is_base_of_v<lerobot::Robot, hiwonder::Leader>);

  static_assert(
    std::is_default_constructible_v<hiwonder::Leader>);
}

// Ensure Robot instances can be safely destroyed through the base class.
TEST(RobotInterfaceTest, RobotHasVirtualDestructor)
{
  static_assert(
    std::has_virtual_destructor_v<lerobot::Robot>);
}

namespace
{

using RobotLoader = pluginlib::ClassLoader<lerobot::Robot>;

lerobot::RobotConfig makeConfig(std::vector<uint8_t> ids)
{
  lerobot::RobotConfig config;
  config.port = "/dev/null_lerobot_test";
  config.motor_ids = std::move(ids);
  return config;
}

}  // namespace

class RobotPluginTest : public ::testing::TestWithParam<const char *>
{
protected:
  RobotLoader loader_{"lerobot_cpp", "lerobot::Robot"};
};

// Verify that pluginlib can discover and instantiate both plugins.
TEST_P(RobotPluginTest, LoadsPluginWithoutMotors)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_NE(robot, nullptr);
  EXPECT_EQ(robot->motorCount(), 0U);
  EXPECT_FALSE(robot->isConnected());
}

TEST_P(RobotPluginTest, RejectsEmptyMotorList)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  EXPECT_FALSE(robot->configure(makeConfig({})));
  EXPECT_EQ(robot->motorCount(), 0U);
}

TEST_P(RobotPluginTest, ConfiguresSixMotors)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_TRUE(robot->configure(makeConfig({1, 2, 3, 4, 5, 6})));
  EXPECT_EQ(robot->motorCount(), 6U);
  EXPECT_FALSE(robot->isConnected());
}

TEST_P(RobotPluginTest, ConfiguresSevenMotors)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_TRUE(robot->configure(makeConfig({1, 2, 3, 4, 5, 6, 7})));
  EXPECT_EQ(robot->motorCount(), 7U);
}

TEST_P(RobotPluginTest, AcceptsNonConsecutiveIds)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_TRUE(robot->configure(makeConfig({10, 3, 200, 0, 253})));
  EXPECT_EQ(robot->motorCount(), 5U);
}

TEST_P(RobotPluginTest, RejectsDuplicateIds)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  EXPECT_FALSE(robot->configure(makeConfig({1, 2, 3, 2})));
  EXPECT_EQ(robot->motorCount(), 0U);
}

TEST_P(RobotPluginTest, RejectsReservedServoIds)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  EXPECT_FALSE(robot->configure(makeConfig({1, 0xFE})));
  EXPECT_FALSE(robot->configure(makeConfig({1, 0xFF})));
  EXPECT_EQ(robot->motorCount(), 0U);
}

TEST_P(RobotPluginTest, RepeatedConfigurationReplacesMotors)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_TRUE(robot->configure(makeConfig({1, 2, 3, 4, 5, 6})));
  ASSERT_TRUE(robot->configure(makeConfig({1, 2, 3, 4, 5, 6, 7})));
  EXPECT_EQ(robot->motorCount(), 7U);

  ASSERT_TRUE(robot->configure(makeConfig({4, 5})));
  EXPECT_EQ(robot->motorCount(), 2U);
}

TEST_P(RobotPluginTest, InvalidConfigurationKeepsPreviousState)
{
  auto robot = loader_.createUniqueInstance(GetParam());

  ASSERT_TRUE(robot->configure(makeConfig({1, 2, 3})));

  EXPECT_FALSE(robot->configure(makeConfig({})));
  EXPECT_FALSE(robot->configure(makeConfig({7, 8, 7})));
  EXPECT_FALSE(robot->configure(makeConfig({7, 255})));
  EXPECT_EQ(robot->motorCount(), 3U);
}

INSTANTIATE_TEST_SUITE_P(
  Plugins,
  RobotPluginTest,
  ::testing::Values(
    "hiwonder_lerobot_cpp/Follower",
    "hiwonder_lerobot_cpp/Leader"));

// Motor order must follow the configured IDs and must not be sorted.
TEST(RobotConfigurationTest, PreservesMotorOrder)
{
  const std::vector<uint8_t> ids{6, 2, 9, 1};

  hiwonder::Follower robot;
  ASSERT_TRUE(robot.configure(makeConfig(ids)));
  EXPECT_EQ(robot.motorCount(), ids.size());
  EXPECT_EQ(robot.motorIds(), ids);
}

// An unreachable port must fail to connect without hardware and without
// changing the configured motors.
TEST(RobotConfigurationTest, ConnectFailureKeepsConfiguration)
{
  hiwonder::Leader robot;
  ASSERT_TRUE(robot.configure(makeConfig({1, 2, 3})));

  EXPECT_FALSE(robot.connect());
  EXPECT_FALSE(robot.isConnected());
  EXPECT_EQ(robot.motorCount(), 3U);
  EXPECT_TRUE(robot.configure(makeConfig({4, 5})));
}
