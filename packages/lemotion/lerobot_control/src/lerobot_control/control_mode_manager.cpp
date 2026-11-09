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

#include "lerobot_control/control_mode_manager.hpp"

#include <algorithm>
#include <chrono>
#include <functional>
#include <future>
#include <stdexcept>
#include <utility>

namespace lerobot_control
{

namespace
{

constexpr char POSITION_CONTROLLER[] = "position_controller";
constexpr char MANIPULATOR_CONTROLLER[] = "manipulator_controller";
constexpr char GRIPPER_CONTROLLER[] = "gripper_controller";

const std::vector<std::string> MANAGED_CONTROLLERS = {
  POSITION_CONTROLLER,
  MANIPULATOR_CONTROLLER,
  GRIPPER_CONTROLLER
};

bool contains(
  const std::vector<std::string> & values,
  const std::string & value)
{
  return std::find(values.begin(), values.end(), value) != values.end();
}

}  // namespace

ControlModeManager::ControlModeManager(const rclcpp::NodeOptions & options)
: Node("control_mode_manager", options)
{
  controller_manager_name_ = declare_parameter<std::string>(
        "controller_manager", "controller_manager");

  service_timeout_ = declare_parameter<double>(
        "service_timeout", 5.0);

  if (service_timeout_ <= 0.0) {
    throw std::invalid_argument("service_timeout must be greater than zero");
  }

  client_callback_group_ = create_callback_group(
        rclcpp::CallbackGroupType::Reentrant);

  list_controllers_client_ = create_client<ListControllers>(
        controller_manager_name_ + "/list_controllers",
        rclcpp::ServicesQoS(),
        client_callback_group_);

  switch_controller_client_ = create_client<SwitchController>(
        controller_manager_name_ + "/switch_controller",
        rclcpp::ServicesQoS(),
        client_callback_group_);

  set_control_mode_service_ = create_service<SetControlMode>(
        "set_control_mode",
        std::bind(
            &ControlModeManager::handle_set_control_mode,
            this,
            std::placeholders::_1,
            std::placeholders::_2));

  RCLCPP_INFO(
        get_logger(),
        "Control mode manager initialized (controller_manager: %s)",
        controller_manager_name_.c_str());
}

void ControlModeManager::handle_set_control_mode(
  const std::shared_ptr<SetControlMode::Request> request,
  std::shared_ptr<SetControlMode::Response> response)
{
  std::unique_lock<std::mutex> lock(switch_mutex_, std::try_to_lock);

  if (!lock.owns_lock()) {
    response->success = false;
    response->message = "Another controller switch is already in progress";
    return;
  }

  response->success = switch_mode(request->mode, response->message);

  if (response->success) {
    RCLCPP_INFO(get_logger(), "%s", response->message.c_str());
  } else {
    RCLCPP_ERROR(get_logger(), "%s", response->message.c_str());
  }
}

bool ControlModeManager::switch_mode(
  uint8_t mode,
  std::string & message)
{
  if (switch_state_ == SwitchState::UNCERTAIN) {
    message = "Controller state is uncertain after a previous switch timeout";
    return false;
  }

  const auto required = get_required_controllers(mode);

  if (!required) {
    message = "Invalid control mode: " + std::to_string(mode);
    return false;
  }

  const auto states = get_controller_states();

  if (!states) {
    message = "Failed to query controller states";
    return false;
  }

  if (!validate_required_controllers(*required, *states, message)) {
    return false;
  }

  const auto plan = compute_switch_plan(*required, *states);

  if (plan.empty()) {
    if (!verify_controller_states(*required)) {
      message = "Controller state verification failed";
      return false;
    }
    message = "Requested control mode is already active";
    return true;
  }

  if (!execute_switch(plan, message)) {
    return false;
  }

  if (!verify_controller_states(*required)) {
    message = "Controller state verification failed";
    return false;
  }

  switch (mode) {
    case SetControlMode::Request::IDLE:
      message = "Switched to IDLE mode";
      break;

    case SetControlMode::Request::TELEOP:
      message = "Switched to TELEOP mode";
      break;

    case SetControlMode::Request::TRAJECTORY:
      message = "Switched to TRAJECTORY mode";
      break;
  }

  return true;
}

std::optional<std::vector<std::string>>
ControlModeManager::get_required_controllers(uint8_t mode)
{
  switch (mode) {
    case SetControlMode::Request::IDLE:
      return std::vector<std::string>{};

    case SetControlMode::Request::TELEOP:
      return std::vector<std::string>{
        POSITION_CONTROLLER
      };

    case SetControlMode::Request::TRAJECTORY:
      return std::vector<std::string>{
        MANIPULATOR_CONTROLLER,
        GRIPPER_CONTROLLER
      };

    default:
      return std::nullopt;
  }
}

std::optional<ControlModeManager::ControllerStates>
ControlModeManager::get_controller_states()
{
  const auto timeout = std::chrono::duration<double>(service_timeout_);

  if (!list_controllers_client_->wait_for_service(timeout)) {
    RCLCPP_ERROR(
            get_logger(),
            "Controller manager list_controllers service is unavailable");
    return std::nullopt;
  }

  auto request = std::make_shared<ListControllers::Request>();
  auto future = list_controllers_client_->async_send_request(request);

  if (future.wait_for(timeout) != std::future_status::ready) {
    list_controllers_client_->remove_pending_request(future);

    RCLCPP_ERROR(
            get_logger(),
            "Timed out while querying controller states");

    return std::nullopt;
  }

  try {
    const auto response = future.get();

    ControllerStates states;

    for (const auto & controller : response->controller) {
      states[controller.name] = controller.state;
    }

    return states;
  } catch (const std::exception & error) {
    RCLCPP_ERROR(
            get_logger(),
            "Failed to query controller states: %s",
            error.what());

    return std::nullopt;
  }
}

bool ControlModeManager::validate_required_controllers(
  const std::vector<std::string> & required,
  const ControllerStates & states,
  std::string & message)
{
  for (const auto & name : required) {
    const auto it = states.find(name);

    if (it == states.end()) {
      message = "Required controller '" + name + "' is not loaded";
      return false;
    }

    if (it->second != "active" && it->second != "inactive") {
      message = "Required controller '" + name +
        "' is not configured (state: " + it->second + ")";
      return false;
    }
  }

  return true;
}

ControlModeManager::ControllerSwitchPlan
ControlModeManager::compute_switch_plan(
  const std::vector<std::string> & required,
  const ControllerStates & states)
{
  ControllerSwitchPlan plan;

  for (const auto & name : MANAGED_CONTROLLERS) {
    const auto it = states.find(name);

    if (it == states.end()) {
      continue;
    }

    const bool should_be_active = contains(required, name);

    if (should_be_active && it->second == "inactive") {
      plan.activate.push_back(name);
    } else if (!should_be_active && it->second == "active") {
      plan.deactivate.push_back(name);
    }
  }

  return plan;
}

bool ControlModeManager::execute_switch(
  const ControllerSwitchPlan & plan,
  std::string & message)
{
  const auto timeout = std::chrono::duration<double>(service_timeout_);

  if (!switch_controller_client_->wait_for_service(timeout)) {
    message = "Controller manager switch_controller service is unavailable";
    return false;
  }

  auto request = std::make_shared<SwitchController::Request>();

  request->activate_controllers = plan.activate;
  request->deactivate_controllers = plan.deactivate;
  request->strictness = SwitchController::Request::STRICT;
  request->activate_asap = true;
  request->timeout = rclcpp::Duration::from_seconds(service_timeout_);

  auto future = switch_controller_client_->async_send_request(request);

  if (future.wait_for(timeout) != std::future_status::ready) {
    switch_state_ = SwitchState::UNCERTAIN;
    switch_controller_client_->remove_pending_request(future);
    message = "Controller switch timed out; further mode changes are blocked";
    RCLCPP_ERROR(
          get_logger(),
          "%s",
          message.c_str());
    return false;
  }

  try {
    if (!future.get()->ok) {
      message = "Controller manager rejected the controller switch";
      return false;
    }
  } catch (const std::exception & error) {
    message = std::string("Controller switching failed: ") + error.what();
    return false;
  }

  return true;
}

bool ControlModeManager::verify_controller_states(
  const std::vector<std::string> & required)
{
  const auto states = get_controller_states();

  if (!states) {
    return false;
  }

  for (const auto & name : MANAGED_CONTROLLERS) {
    const auto it = states->find(name);

    if (it == states->end()) {
      if (contains(required, name)) {
        RCLCPP_ERROR(
                    get_logger(),
                    "Required controller '%s' is missing",
                    name.c_str());

        return false;
      }

      continue;
    }

    const std::string expected_state =
      contains(required, name) ? "active" : "inactive";

    if (it->second != expected_state) {
      RCLCPP_ERROR(
                get_logger(),
                "Controller '%s' is '%s', expected '%s'",
                name.c_str(),
                it->second.c_str(),
                expected_state.c_str());

      return false;
    }
  }

  return true;
}

}  // namespace lerobot_control
