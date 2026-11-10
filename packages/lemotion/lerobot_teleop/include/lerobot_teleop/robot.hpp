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

#include <chrono>
#include <string>
#include <vector>
#include <functional>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "lerobot_interfaces/srv/set_control_mode.hpp"

namespace lerobot_teleop
{

/**
 * @brief Base class for robots participating in teleoperation.
 *
 * Provides common joint state subscription, joint position lookup,
 * and joint state timing functionality.
 */
class Robot
{
public:
  using SetControlMode = lerobot_interfaces::srv::SetControlMode;
  using ControlModeCallback = std::function<void(bool)>;

  /**
   * @brief Construct a robot interface.
   *
   * Creates a subscription to the configured joint state topic.
   *
   * @param node Lifecycle node used for ROS 2 communication.
   * @param joint_state_topic Topic providing the robot joint states.
   */
  Robot(
    rclcpp_lifecycle::LifecycleNode & node,
    const std::string & joint_state_topic,
    const std::string & control_mode_service);

  /**
   * @brief Destroy the robot interface.
   */
  virtual ~Robot() = default;

  /**
   * @brief Check whether a joint state has been received.
   *
   * @return true if at least one joint state has been received,
   * otherwise false.
   */
  [[nodiscard]] bool stateReceived() const noexcept;

  /**
   * @brief Get the most recently received joint state.
   *
   * @return Reference to the latest joint state message.
   */
  [[nodiscard]] const sensor_msgs::msg::JointState &
  jointState() const noexcept;

  /**
   * @brief Get joint positions in the requested joint order.
   *
   * Joint positions are matched by joint name and written to the output
   * vector in the same order as the requested joint names.
   *
   * @param joint_names Joint names whose positions should be retrieved.
   * @param positions Output vector containing the corresponding positions.
   * @return true if all requested joint positions are available,
   * otherwise false.
   */
  [[nodiscard]] bool positions(
    const std::vector<std::string> & joint_names,
    std::vector<double> & positions) const;

  /**
   * @brief Get the age of the most recently received joint state.
   *
   * @return Time in seconds since the last joint state was received.
   */
  [[nodiscard]] double stateAge() const;

  /**
   * @brief Request a control mode change.
   *
   * @param mode Requested control mode.
   * @param callback Called when the request completes.
   * @return true if the request was sent, otherwise false.
   */
  bool setControlMode(
    uint8_t mode,
    ControlModeCallback callback);

  /**
   * @brief Check if the control mode service is ready.
   *
   * @return true if the control mode service is available, otherwise false.
   */
  [[nodiscard]] bool controlModeServiceReady() const;

protected:
  rclcpp_lifecycle::LifecycleNode & node_;
  rclcpp::Client<SetControlMode>::SharedPtr control_mode_client_;

private:
  /**
   * @brief Process an incoming joint state message.
   *
   * @param msg Received joint state message.
   */
  void jointStateCallback(
    const sensor_msgs::msg::JointState::SharedPtr msg);

  sensor_msgs::msg::JointState joint_state_;

  bool state_received_{false};

  std::chrono::steady_clock::time_point
    last_update_;

  rclcpp::Subscription<
    sensor_msgs::msg::JointState>::SharedPtr subscription_;
};

}  // namespace lerobot_teleop
