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

#include "lerobot_teleop/robot.hpp"

#include <algorithm>
#include <functional>
#include <limits>

#include "sensor_msgs/msg/joint_state.hpp"

namespace lerobot_teleop
{

Robot::Robot(
  rclcpp_lifecycle::LifecycleNode & node,
  const std::string & joint_state_topic,
  const std::string & control_mode_service)
: node_(node)
{
  subscription_ =
    node_.create_subscription<sensor_msgs::msg::JointState>(
    joint_state_topic,
    rclcpp::SensorDataQoS(),
    std::bind(
      &Robot::jointStateCallback,
      this,
      std::placeholders::_1));

  control_mode_client_ =
    node_.create_client<SetControlMode>(control_mode_service);
}

bool Robot::stateReceived() const noexcept
{
  return state_received_;
}

const sensor_msgs::msg::JointState &
Robot::jointState() const noexcept
{
  return joint_state_;
}

bool Robot::positions(
  const std::vector<std::string> & joint_names,
  std::vector<double> & positions) const
{
  if (!state_received_) {
    return false;
  }

  positions.clear();
  positions.reserve(joint_names.size());

  for (const auto & joint_name : joint_names) {
    const auto it =
      std::find(
      joint_state_.name.begin(),
      joint_state_.name.end(),
      joint_name);

    if (it == joint_state_.name.end()) {
      positions.clear();
      return false;
    }

    const auto index =
      static_cast<std::size_t>(
      std::distance(
        joint_state_.name.begin(),
        it));

    positions.push_back(
      joint_state_.position[index]);
  }

  return true;
}

double Robot::stateAge() const
{
  if (!state_received_) {
    return std::numeric_limits<double>::infinity();
  }

  return std::chrono::duration<double>(
    std::chrono::steady_clock::now() -
    last_update_).count();
}

void Robot::jointStateCallback(
  const sensor_msgs::msg::JointState::SharedPtr msg)
{
  if (
    msg->name.empty() ||
    msg->name.size() != msg->position.size())
  {
    return;
  }

  joint_state_ = *msg;
  state_received_ = true;

  last_update_ =
    std::chrono::steady_clock::now();
}

bool Robot::setControlMode(
  uint8_t mode,
  ControlModeCallback callback)
{
  if (!control_mode_client_->service_is_ready()) {
    RCLCPP_WARN(
            node_.get_logger(),
            "Control mode service is not available");

    return false;
  }

  auto request = std::make_shared<SetControlMode::Request>();
  request->mode = mode;

  control_mode_client_->async_send_request(
        request,
    [callback = std::move(callback)](
      rclcpp::Client<SetControlMode>::SharedFuture future)
    {
      try {
        const auto response = future.get();
        callback(response->success);
      } catch (const std::exception &) {
        callback(false);
      }
        });

  return true;
}

[[nodiscard]] bool Robot::controlModeServiceReady() const
{
  return control_mode_client_ &&
         control_mode_client_->service_is_ready();
}

}  // namespace lerobot_teleop
