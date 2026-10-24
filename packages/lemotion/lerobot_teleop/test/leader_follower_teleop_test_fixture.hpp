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

#pragma once

#include <gtest/gtest.h>

#include <chrono>
#include <memory>
#include <string>
#include <vector>

#include "lerobot_teleop/leader_follower_teleop.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"
#include "std_srvs/srv/set_bool.hpp"

namespace lerobot_teleop
{

/**
 * @brief Test fixture for leader-follower teleoperation integration tests.
 *
 * Provides mock leader and follower joint states, a mock follower controller,
 * a guiding mode service, and utilities for executing lifecycle-based
 * teleoperation tests.
 */
class LeaderFollowerTeleopTest
  : public ::testing::Test
{
protected:
  static void SetUpTestSuite();

  static void TearDownTestSuite();

  void SetUp() override;

  void TearDown() override;

  /**
   * @brief Create a joint state using the default joint order.
   *
   * @param positions Joint positions.
   * @return Joint state message.
   */
  [[nodiscard]] sensor_msgs::msg::JointState createJointState(
    const std::vector<double> & positions);

  /**
   * @brief Create a joint state with a specified joint order.
   *
   * @param names Joint names.
   * @param positions Joint positions corresponding to the joint names.
   * @return Joint state message.
   */
  [[nodiscard]] sensor_msgs::msg::JointState createJointState(
    const std::vector<std::string> & names,
    const std::vector<double> & positions);

  /**
   * @brief Publish leader joint positions.
   *
   * @param positions Leader joint positions.
   */
  void publishLeader(
    const std::vector<double> & positions);

  /**
   * @brief Publish follower joint positions.
   *
   * @param positions Follower joint positions.
   */
  void publishFollower(
    const std::vector<double> & positions);

  /**
   * @brief Publish leader and follower joint states.
   *
   * @param leader Leader joint positions.
   * @param follower Follower joint positions.
   */
  void publishJointStates(
    const std::vector<double> & leader,
    const std::vector<double> & follower);

  /**
   * @brief Publish leader and follower joint states with a specified joint order.
   *
   * @param names Joint names.
   * @param leader Leader joint positions.
   * @param follower Follower joint positions.
   */
  void publishJointStates(
    const std::vector<std::string> & names,
    const std::vector<double> & leader,
    const std::vector<double> & follower);

  /**
   * @brief Spin the test executor for a specified duration.
   *
   * @param duration Duration for which the executor is spun.
   */
  void spinFor(
    std::chrono::milliseconds duration);

  /**
   * @brief Continuously publish joint states while spinning the executor.
   *
   * @param leader Leader joint positions.
   * @param follower Follower joint positions.
   * @param duration Duration for which states are published.
   */
  void publishFor(
    const std::vector<double> & leader,
    const std::vector<double> & follower,
    std::chrono::milliseconds duration);

  /**
   * @brief Continuously publish joint states with a specified joint order.
   *
   * @param names Joint names.
   * @param leader Leader joint positions.
   * @param follower Follower joint positions.
   * @param duration Duration for which states are published.
   */
  void publishFor(
    const std::vector<std::string> & names,
    const std::vector<double> & leader,
    const std::vector<double> & follower,
    std::chrono::milliseconds duration);

  /**
   * @brief Configure and activate the teleoperation lifecycle node.
   */
  void activateTeleop();

  /**
   * @brief Verify that a command lies between start and target positions.
   *
   * @param command Command to verify.
   * @param start Initial joint positions.
   * @param target Target joint positions.
   */
  void expectCommandWithinBounds(
    const std::vector<double> & command,
    const std::vector<double> & start,
    const std::vector<double> & target);

  /**
   * @brief Compare two joint position vectors within a tolerance.
   *
   * @param actual Actual joint positions.
   * @param expected Expected joint positions.
   * @param tolerance Maximum allowed absolute difference.
   */
  void expectNear(
    const std::vector<double> & actual,
    const std::vector<double> & expected,
    double tolerance);

  const std::vector<std::string> joint_names_{
    "joint_1",
    "joint_2",
    "joint_3",
    "joint_4",
    "joint_5",
    "gripper"
  };

  static constexpr double kTolerance =
    1e-6;

  rclcpp::executors::SingleThreadedExecutor
    executor_;

  std::shared_ptr<rclcpp::Node>
  mock_node_;

  std::shared_ptr<rclcpp::Node>
  controller_node_;

  std::shared_ptr<LeaderFollowerTeleop>
  teleop_;

  rclcpp::Publisher<
    sensor_msgs::msg::JointState>::SharedPtr
    leader_publisher_;

  rclcpp::Publisher<
    sensor_msgs::msg::JointState>::SharedPtr
    follower_publisher_;

  rclcpp::Subscription<
    std_msgs::msg::Float64MultiArray>::SharedPtr
    command_subscription_;

  rclcpp::Subscription<
    std_msgs::msg::Float64MultiArray>::SharedPtr
    controller_command_subscription_;

  rclcpp::Service<
    std_srvs::srv::SetBool>::SharedPtr
    guiding_service_;

  std::vector<std::vector<double>>
  received_commands_;

  bool guiding_enabled_{false};

  std::size_t guiding_service_calls_{0};
};

}  // namespace lerobot_teleop
