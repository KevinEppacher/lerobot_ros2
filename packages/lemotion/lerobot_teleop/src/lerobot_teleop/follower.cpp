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

#include "lerobot_teleop/follower.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

#include "lerobot_teleop/utils.hpp"

namespace lerobot_teleop
{

Follower::Follower(
  rclcpp_lifecycle::LifecycleNode & node)
: Robot(
    node,
    utils::declareIfNotDeclared<std::string>(
      node,
      "follower.joint_state_topic",
      "/follower/joint_states"),
    utils::declareIfNotDeclared<std::string>(
      node,
      "follower.control_mode_service",
      "/follower/set_control_mode"))
{
  command_topic_ =
    utils::declareIfNotDeclared<std::string>(
      node,
      "follower.command_topic",
      "/follower/position_controller/commands");

  alignment_duration_ =
    utils::declareIfNotDeclared<double>(
      node,
      "follower.alignment_duration",
      3.0);

  if (alignment_duration_ <= 0.0) {
    throw std::invalid_argument(
            "Follower alignment duration must be greater than zero");
  }

  command_publisher_ =
    node_.create_publisher<
    std_msgs::msg::Float64MultiArray>(
    command_topic_,
    10);
}

bool Follower::discoverController()
{
  if (controllerDiscovered()) {
    return true;
  }

  if (discovery_in_progress_) {
    return false;
  }

  const auto controller =
    findCommandController();

  if (!controller) {
    return false;
  }

  requestControllerJoints(
    *controller);

  return false;
}

std::vector<std::string>
Follower::commandSubscribers() const
{
  std::unordered_set<std::string>
  subscriber_nodes;

  const auto subscriptions =
    node_.get_subscriptions_info_by_topic(
    command_topic_);

  for (const auto & subscription : subscriptions) {
    std::string node_name =
      subscription.node_namespace();

    if (
      node_name.empty() ||
      node_name == "/")
    {
      node_name = "/";
    } else if (node_name.back() != '/') {
      node_name += '/';
    }

    node_name +=
      subscription.node_name();

    subscriber_nodes.insert(
      std::move(node_name));
  }

  return {
    subscriber_nodes.begin(),
    subscriber_nodes.end()
  };
}

std::optional<std::string>
Follower::findCommandController()
{
  const auto subscribers =
    commandSubscribers();

  if (subscribers.size() > 1) {
    RCLCPP_DEBUG(
      node_.get_logger(),
      "Found %zu subscribers on command topic '%s', searching for controller",
      subscribers.size(),
      command_topic_.c_str());
  }

  for (const auto & subscriber : subscribers) {
    auto client =
      std::make_shared<rclcpp::AsyncParametersClient>(
      &node_,
      subscriber);

    if (!client->service_is_ready()) {
      continue;
    }

    parameter_client_ =
      std::move(client);

    return subscriber;
  }

  return std::nullopt;
}

void Follower::requestControllerJoints(
  const std::string & controller_node)
{
  discovery_in_progress_ = true;

  parameter_client_->get_parameters(
    {"joints"},
    [this, controller_node](
      std::shared_future<
        std::vector<rclcpp::Parameter>> future)
    {
      discovery_in_progress_ = false;

      handleControllerJoints(
        controller_node,
        future.get());

      parameter_client_.reset();
    });
}

void Follower::handleControllerJoints(
  const std::string & controller_node,
  const std::vector<rclcpp::Parameter> & parameters)
{
  if (parameters.size() != 1) {
    return;
  }

  const auto & parameter =
    parameters.front();

  if (
    parameter.get_type() !=
    rclcpp::ParameterType::PARAMETER_STRING_ARRAY)
  {
    return;
  }

  const auto joints =
    parameter.as_string_array();

  if (!validJointNames(joints)) {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Controller '%s' contains invalid or duplicate joint names",
      controller_node.c_str());

    return;
  }

  command_joint_names_ =
    joints;

  RCLCPP_INFO(
    node_.get_logger(),
    "Discovered controller '%s' with %zu command joints",
    controller_node.c_str(),
    command_joint_names_.size());
}

bool Follower::validJointNames(
  const std::vector<std::string> & joints) const
{
  if (joints.empty()) {
    return false;
  }

  std::unordered_set<std::string>
  unique_joints;

  return std::all_of(
    joints.begin(),
    joints.end(),
    [&unique_joints](const auto & joint)
    {
      return
        !joint.empty() &&
        unique_joints.insert(joint).second;
    });
}

bool Follower::controllerDiscovered() const noexcept
{
  return !command_joint_names_.empty();
}

const std::vector<std::string> &
Follower::commandJointNames() const noexcept
{
  return command_joint_names_;
}

void Follower::startAlignment(
  const std::vector<double> & target)
{
  if (!prepareAlignment(target)) {
    aligning_ = false;
    return;
  }

  alignment_target_ =
    target;

  alignment_start_time_ =
    std::chrono::steady_clock::now();

  aligning_ = true;
}

bool Follower::prepareAlignment(
  const std::vector<double> & target)
{
  if (!controllerDiscovered()) {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Cannot start alignment before controller discovery");

    return false;
  }

  if (!positions(
      command_joint_names_,
      alignment_start_))
  {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Failed to map follower joint positions");

    return false;
  }

  if (alignment_start_.size() != target.size()) {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Follower alignment target size does not match controller joint count");

    return false;
  }

  return true;
}

bool Follower::updateAlignment()
{
  if (!aligning_) {
    return true;
  }

  const double progress =
    alignmentProgress();

  publishCommand(
    alignmentCommand(progress));

  if (progress < 1.0) {
    return false;
  }

  aligning_ = false;

  return true;
}

double Follower::alignmentProgress() const
{
  const double elapsed =
    std::chrono::duration<double>(
    std::chrono::steady_clock::now() -
    alignment_start_time_).count();

  return std::clamp(
    elapsed / alignment_duration_,
    0.0,
    1.0);
}

std::vector<double>
Follower::alignmentCommand(
  double progress) const
{
  std::vector<double> command(
    alignment_target_.size());

  for (std::size_t i = 0; i < command.size(); ++i) {
    command[i] =
      alignment_start_[i] +
      progress *
      (alignment_target_[i] -
      alignment_start_[i]);
  }

  return command;
}

void Follower::track(
  const std::vector<double> & target)
{
  if (target.size() != command_joint_names_.size()) {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Tracking target size does not match controller joint count");

    return;
  }

  publishCommand(
    target);
}

void Follower::publishCommand(
  const std::vector<double> & positions)
{
  std_msgs::msg::Float64MultiArray command;

  command.data =
    positions;

  command_publisher_->publish(
    command);
}

}  // namespace lerobot_teleop
