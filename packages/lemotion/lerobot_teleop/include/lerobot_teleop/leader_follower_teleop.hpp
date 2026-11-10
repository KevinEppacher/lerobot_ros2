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

#include <memory>

#include "lerobot_teleop/filters/low_pass_filter.hpp"
#include "lerobot_teleop/follower.hpp"
#include "lerobot_teleop/leader.hpp"
#include "lerobot_teleop/state_manager.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

namespace lerobot_teleop
{

/**
 * @brief Lifecycle node for leader-follower teleoperation.
 *
 * Coordinates leader and follower interfaces, follower alignment,
 * leader guiding mode, joint position tracking, and command filtering.
 */
class LeaderFollowerTeleop
  : public rclcpp_lifecycle::LifecycleNode
{
public:
  /**
   * @brief Construct the leader-follower teleoperation node.
   *
   * @param options ROS 2 node options.
   */
  explicit LeaderFollowerTeleop(
    const rclcpp::NodeOptions & options =
    rclcpp::NodeOptions());

  /**
   * @brief Configure the teleoperation components.
   *
   * Creates the leader, follower, filter, and update timer.
   *
   * @param state Current lifecycle state.
   * @return Lifecycle transition result.
   */
  CallbackReturn on_configure(
    const rclcpp_lifecycle::State & state) override;

  /**
   * @brief Activate leader-follower teleoperation.
   *
   * Starts the teleoperation state machine by waiting for valid leader
   * and follower joint states.
   *
   * @param state Current lifecycle state.
   * @return Lifecycle transition result.
   */
  CallbackReturn on_activate(
    const rclcpp_lifecycle::State & state) override;

  /**
   * @brief Deactivate leader-follower teleoperation.
   *
   * Stops tracking and disables guiding mode on the leader.
   *
   * @param state Current lifecycle state.
   * @return Lifecycle transition result.
   */
  CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & state) override;

  /**
   * @brief Clean up the teleoperation components.
   *
   * Releases the leader, follower, filter, and update timer.
   *
   * @param state Current lifecycle state.
   * @return Lifecycle transition result.
   */
  CallbackReturn on_cleanup(
    const rclcpp_lifecycle::State & state) override;

private:
  using SetControlMode = lerobot_interfaces::srv::SetControlMode;

  /**
   * @brief Execute one update of the teleoperation state machine.
   */
  void update();

  /**
   * @brief Wait for valid leader and follower joint states.
   *
   * Discovers the follower command controller and transitions to alignment
   * once the required joint states and controller information are available.
   */
  void waitForJointStates();

  /**
   * @brief Update follower alignment with the leader pose.
   *
   * Enables leader guiding mode after alignment is complete.
   */
  void alignFollower();

  /**
   * @brief Track the current leader joint positions with the follower.
   *
   * Applies the configured low-pass filter before commanding the follower.
   */
  void trackLeader();

  /**
   * @brief Check whether the required leader and follower joints match.
   *
   * @return true if all controller joints are available on both robots,
   * otherwise false.
   */
  [[nodiscard]] bool jointsMatch() const;

  /**
   * @brief Attempt to enable guiding mode on the leader.
   *
   * Retries while the guiding mode service is unavailable and prevents
   * multiple requests from being active simultaneously.
   */
  void enableGuiding();

  /**
   * @brief Request TELEOP control mode for both robots.
   *
   * Teleoperation starts only after both requests succeed.
   */
  void requestTeleopControlMode();

  double update_rate_{50.0};
  bool guiding_request_pending_{false};

  std::unique_ptr<Leader> leader_;
  std::unique_ptr<Follower> follower_;
  std::unique_ptr<LowPassFilter> low_pass_filter_;

  StateManager state_manager_;

  rclcpp::TimerBase::SharedPtr update_timer_;

  /** Whether a control mode request is currently pending. */
  bool control_mode_request_pending_{false};

  /** Whether the leader control mode request has succeeded. */
  bool leader_control_mode_ready_{false};

  /** Whether the follower control mode request has succeeded. */
  bool follower_control_mode_ready_{false};
};

}  // namespace lerobot_teleop
