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

#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <controller_manager_msgs/srv/list_controllers.hpp>
#include <controller_manager_msgs/srv/switch_controller.hpp>

#include <lerobot_interfaces/srv/set_control_mode.hpp>

namespace lerobot_control
{

/**
 * @brief Manages ROS 2 controller activation based on the requested control mode.
 *
 * Supports IDLE, TELEOP, and TRAJECTORY modes by dynamically switching
 * between the available controllers through the ROS 2 controller manager.
 */
class ControlModeManager : public rclcpp::Node
{
public:
    /**
     * @brief Constructs the control mode manager node.
     * @param options ROS 2 node options.
     */
  explicit ControlModeManager(
    const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  using SetControlMode = lerobot_interfaces::srv::SetControlMode;
  using ListControllers = controller_manager_msgs::srv::ListControllers;
  using SwitchController = controller_manager_msgs::srv::SwitchController;

    /** @brief Maps controller names to their current lifecycle states. */
  using ControllerStates = std::unordered_map<std::string, std::string>;

    /**
     * @brief Describes the controller activations and deactivations required
     *        to reach a target control mode.
     */
  struct ControllerSwitchPlan
  {
    std::vector<std::string> activate;
    std::vector<std::string> deactivate;

        /**
         * @brief Checks whether the switch plan requires any changes.
         * @return True if no controllers need to be switched.
         */
    bool empty() const
    {
      return activate.empty() && deactivate.empty();
    }
  };

  /**
   * @brief Tracks whether controller switching can be performed safely.
   */
  enum class SwitchState
  {
    READY,
    UNCERTAIN
  };

    /**
     * @brief Handles incoming control mode change requests.
     * @param request Requested control mode.
     * @param response Result of the mode change.
     */
  void handle_set_control_mode(
    const std::shared_ptr<SetControlMode::Request> request,
    std::shared_ptr<SetControlMode::Response> response);

    /**
     * @brief Switches to the requested control mode.
     * @param mode Target control mode.
     * @param message Output message describing the result.
     * @return True if the requested mode was successfully established.
     */
  bool switch_mode(uint8_t mode, std::string & message);

    /**
     * @brief Determines which controllers must be active for a given mode.
     * @param mode Target control mode.
     * @return Required controllers, or std::nullopt if the mode is invalid.
     */
  std::optional<std::vector<std::string>> get_required_controllers(
    uint8_t mode);

    /**
     * @brief Queries the current controller states from the controller manager.
     * @return Controller states, or std::nullopt if the query fails.
     */
  std::optional<ControllerStates> get_controller_states();

    /**
     * @brief Validates that all required controllers are loaded and configured.
     * @param required Controllers required by the target mode.
     * @param states Current controller states.
     * @param message Output error message if validation fails.
     * @return True if all required controllers are available.
     */
  bool validate_required_controllers(
    const std::vector<std::string> & required,
    const ControllerStates & states,
    std::string & message);

    /**
     * @brief Computes the controller changes needed to reach the target mode.
     * @param required Controllers that must be active.
     * @param states Current controller states.
     * @return Switch plan containing the required activations and deactivations.
     */
  ControllerSwitchPlan compute_switch_plan(
    const std::vector<std::string> & required,
    const ControllerStates & states);

    /**
     * @brief Executes a controller switch through the controller manager.
     * @param plan Controllers to activate and deactivate.
     * @param message Output error message if switching fails.
     * @return True if the controller manager accepts the switch.
     */
  bool execute_switch(
    const ControllerSwitchPlan & plan,
    std::string & message);

    /**
     * @brief Verifies that all managed controllers match the target mode.
     *
     * Required controllers must be active, while all other loaded
     * managed controllers must be inactive.
     *
     * @param required Controllers expected to be active.
     * @return True if all managed controllers match their expected states.
     */
  bool verify_controller_states(
    const std::vector<std::string> & required);

    /** @brief Service for requesting control mode changes. */
  rclcpp::Service<SetControlMode>::SharedPtr set_control_mode_service_;

    /** @brief Client for querying loaded controllers and their states. */
  rclcpp::Client<ListControllers>::SharedPtr list_controllers_client_;

    /** @brief Client for activating and deactivating controllers. */
  rclcpp::Client<SwitchController>::SharedPtr switch_controller_client_;

    /** @brief Callback group allowing service responses to be processed concurrently. */
  rclcpp::CallbackGroup::SharedPtr client_callback_group_;

    /** @brief Prevents concurrent control mode changes. */
  std::mutex switch_mutex_;

    /** @brief Name of the target ROS 2 controller manager. */
  std::string controller_manager_name_;

    /** @brief Timeout in seconds for controller manager service operations. */
  double service_timeout_;

  /** @brief Current controller switching state. */
  SwitchState switch_state_{SwitchState::READY};
};

}  // namespace lerobot_control
