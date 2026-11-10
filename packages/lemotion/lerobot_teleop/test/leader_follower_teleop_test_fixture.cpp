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

#include "leader_follower_teleop_test_fixture.hpp"

#include <algorithm>
#include <random>
#include <string>
#include <thread>

#include "lifecycle_msgs/msg/state.hpp"

namespace lerobot_teleop
{

using namespace std::chrono_literals;

void LeaderFollowerTeleopTest::SetUpTestSuite()
{
  rclcpp::init(0, nullptr);
}

void LeaderFollowerTeleopTest::TearDownTestSuite()
{
  rclcpp::shutdown();
}

void LeaderFollowerTeleopTest::SetUp()
{
  std::random_device random;
  const std::string test_namespace =
    "/lerobot_teleop_test_" + std::to_string(random()) + "_" + std::to_string(random());
  const std::string leader_topic = test_namespace + "/leader/joint_states";
  const std::string follower_topic = test_namespace + "/follower/joint_states";
  const std::string command_topic =
    test_namespace + "/follower/position_controller/commands";
  const std::string guiding_service = test_namespace + "/leader/guiding_mode";
  const std::string leader_mode_service =
    test_namespace + "/leader/set_control_mode";
  const std::string follower_mode_service =
    test_namespace + "/follower/set_control_mode";

  mock_node_ =
    std::make_shared<rclcpp::Node>(
    "teleop_test_mock",
    test_namespace,
    rclcpp::NodeOptions().start_parameter_services(false));

  controller_node_ =
    std::make_shared<rclcpp::Node>(
    "position_controller",
    test_namespace + "/follower");

  controller_node_->declare_parameter(
    "joints",
    joint_names_);

  rclcpp::NodeOptions options;

  options.parameter_overrides({
      rclcpp::Parameter("leader.joint_state_topic", leader_topic),
      rclcpp::Parameter("follower.joint_state_topic", follower_topic),
      rclcpp::Parameter("follower.command_topic", command_topic),
      rclcpp::Parameter("leader.guiding_mode_service", guiding_service),
      rclcpp::Parameter("leader.control_mode_service", leader_mode_service),
      rclcpp::Parameter("follower.control_mode_service", follower_mode_service),
      rclcpp::Parameter(
      "update_rate",
      100.0),
      rclcpp::Parameter(
      "follower.alignment_duration",
      0.2),
      rclcpp::Parameter(
      "leader.timeout",
      0.5),
      rclcpp::Parameter(
      "low_pass_filter.enabled",
      true),
      rclcpp::Parameter(
      "low_pass_filter.cutoff_frequency",
      5.0)
  });

  teleop_ =
    std::make_shared<LeaderFollowerTeleop>(
    options);

  leader_publisher_ =
    mock_node_->create_publisher<
    sensor_msgs::msg::JointState>(
    leader_topic,
    rclcpp::SensorDataQoS());

  follower_publisher_ =
    mock_node_->create_publisher<
    sensor_msgs::msg::JointState>(
    follower_topic,
    rclcpp::SensorDataQoS());

  command_subscription_ =
    mock_node_->create_subscription<
    std_msgs::msg::Float64MultiArray>(
    command_topic,
    10,
    [this](
      const std_msgs::msg::Float64MultiArray::SharedPtr msg)
    {
      received_commands_.push_back(
        msg->data);
    });

  controller_command_subscription_ =
    controller_node_->create_subscription<
    std_msgs::msg::Float64MultiArray>(
    command_topic,
    10,
    [](
      const std_msgs::msg::Float64MultiArray::SharedPtr)
    {
    });

  guiding_service_ =
    mock_node_->create_service<
    std_srvs::srv::SetBool>(
    guiding_service,
    [this](
      const std_srvs::srv::SetBool::Request::SharedPtr request,
      std_srvs::srv::SetBool::Response::SharedPtr response)
    {
      guiding_enabled_ =
      request->data;

      ++guiding_service_calls_;

      response->success = true;
      response->message =
      "Mock guiding mode changed";
    });

  auto mode_callback =
    [](
    const lerobot_interfaces::srv::SetControlMode::Request::SharedPtr,
    lerobot_interfaces::srv::SetControlMode::Response::SharedPtr response)
    {
      response->success = true;
      response->message = "Mock control mode changed";
    };

  leader_control_mode_service_ =
    mock_node_->create_service<lerobot_interfaces::srv::SetControlMode>(
    leader_mode_service, mode_callback);

  follower_control_mode_service_ =
    mock_node_->create_service<lerobot_interfaces::srv::SetControlMode>(
    follower_mode_service, mode_callback);

  executor_.add_node(
    mock_node_);

  executor_.add_node(
    controller_node_);

  executor_.add_node(
    teleop_->get_node_base_interface());

  spinFor(
    100ms);
}

void LeaderFollowerTeleopTest::TearDown()
{
  executor_.remove_node(
    teleop_->get_node_base_interface());

  executor_.remove_node(
    controller_node_);

  executor_.remove_node(
    mock_node_);

  teleop_.reset();
  controller_node_.reset();
  mock_node_.reset();

  received_commands_.clear();
}

sensor_msgs::msg::JointState
LeaderFollowerTeleopTest::createJointState(
  const std::vector<double> & positions)
{
  return createJointState(
    joint_names_,
    positions);
}

sensor_msgs::msg::JointState
LeaderFollowerTeleopTest::createJointState(
  const std::vector<std::string> & names,
  const std::vector<double> & positions)
{
  sensor_msgs::msg::JointState message;

  message.header.stamp =
    mock_node_->now();

  message.name =
    names;

  message.position =
    positions;

  return message;
}

void LeaderFollowerTeleopTest::publishLeader(
  const std::vector<double> & positions)
{
  leader_publisher_->publish(
    createJointState(positions));
}

void LeaderFollowerTeleopTest::publishFollower(
  const std::vector<double> & positions)
{
  follower_publisher_->publish(
    createJointState(positions));
}

void LeaderFollowerTeleopTest::publishJointStates(
  const std::vector<double> & leader,
  const std::vector<double> & follower)
{
  publishJointStates(
    joint_names_,
    leader,
    follower);
}

void LeaderFollowerTeleopTest::publishJointStates(
  const std::vector<std::string> & names,
  const std::vector<double> & leader,
  const std::vector<double> & follower)
{
  leader_publisher_->publish(
    createJointState(
      names,
      leader));

  follower_publisher_->publish(
    createJointState(
      names,
      follower));
}

void LeaderFollowerTeleopTest::spinFor(
  std::chrono::milliseconds duration)
{
  const auto end =
    std::chrono::steady_clock::now() +
    duration;

  while (
    std::chrono::steady_clock::now() < end)
  {
    executor_.spin_some();

    std::this_thread::sleep_for(
      2ms);
  }
}

void LeaderFollowerTeleopTest::publishFor(
  const std::vector<double> & leader,
  const std::vector<double> & follower,
  std::chrono::milliseconds duration)
{
  publishFor(
    joint_names_,
    leader,
    follower,
    duration);
}

void LeaderFollowerTeleopTest::publishFor(
  const std::vector<std::string> & names,
  const std::vector<double> & leader,
  const std::vector<double> & follower,
  std::chrono::milliseconds duration)
{
  const auto end =
    std::chrono::steady_clock::now() +
    duration;

  while (
    std::chrono::steady_clock::now() < end)
  {
    publishJointStates(
      names,
      leader,
      follower);

    spinFor(
      10ms);
  }
}

void LeaderFollowerTeleopTest::activateTeleop()
{
  const auto configured_state =
    teleop_->configure();

  ASSERT_EQ(
    configured_state.id(),
    lifecycle_msgs::msg::State::
    PRIMARY_STATE_INACTIVE);

  const auto active_state =
    teleop_->activate();

  ASSERT_EQ(
    active_state.id(),
    lifecycle_msgs::msg::State::
    PRIMARY_STATE_ACTIVE);
}

void LeaderFollowerTeleopTest::expectCommandWithinBounds(
  const std::vector<double> & command,
  const std::vector<double> & start,
  const std::vector<double> & target)
{
  ASSERT_EQ(
    command.size(),
    start.size());

  ASSERT_EQ(
    command.size(),
    target.size());

  for (std::size_t i = 0;
    i < command.size();
    ++i)
  {
    const double minimum =
      std::min(
      start[i],
      target[i]);

    const double maximum =
      std::max(
      start[i],
      target[i]);

    EXPECT_GE(
      command[i],
      minimum - kTolerance);

    EXPECT_LE(
      command[i],
      maximum + kTolerance);
  }
}

void LeaderFollowerTeleopTest::expectNear(
  const std::vector<double> & actual,
  const std::vector<double> & expected,
  double tolerance)
{
  ASSERT_EQ(
    actual.size(),
    expected.size());

  for (std::size_t i = 0;
    i < actual.size();
    ++i)
  {
    EXPECT_NEAR(
      actual[i],
      expected[i],
      tolerance);
  }
}

}  // namespace lerobot_teleop
