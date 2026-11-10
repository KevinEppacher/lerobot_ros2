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

#include "lerobot_teleop/leader.hpp"

#include <memory>
#include <string>
#include <utility>

#include "lerobot_teleop/utils.hpp"

namespace lerobot_teleop
{

Leader::Leader(
  rclcpp_lifecycle::LifecycleNode & node)
: Robot(
    node,
    utils::declareIfNotDeclared<std::string>(
      node,
      "leader.joint_state_topic",
      "/leader/joint_states"),
    utils::declareIfNotDeclared<std::string>(
      node,
      "leader.control_mode_service",
      "/leader/set_control_mode"))
{
  const auto guiding_mode_service = utils::declareIfNotDeclared<std::string>(
    node,
    "leader.guiding_mode_service",
    "/leader/leader_so101/guiding_mode");

  timeout_ = utils::declareIfNotDeclared<double>(
    node,
    "leader.timeout",
    0.5);

  guiding_mode_client_ =
    node_.create_client<std_srvs::srv::SetBool>(
    guiding_mode_service);
}

bool Leader::timedOut() const
{
  return stateAge() > timeout_;
}

bool Leader::setGuidingMode(
  bool enabled,
  GuidingCallback callback)
{
  if (!guiding_mode_client_->service_is_ready()) {
    RCLCPP_ERROR(
      node_.get_logger(),
      "Guiding mode service is not available");

    return false;
  }

  auto request =
    std::make_shared<std_srvs::srv::SetBool::Request>();

  request->data = enabled;

  guiding_mode_client_->async_send_request(
    request,
    [callback = std::move(callback)](
      rclcpp::Client<
        std_srvs::srv::SetBool>::SharedFuture future)
    {
      callback(future.get()->success);
    });

  return true;
}

}  // namespace lerobot_teleop
