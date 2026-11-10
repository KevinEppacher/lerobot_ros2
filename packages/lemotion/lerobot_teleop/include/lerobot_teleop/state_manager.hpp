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

namespace lerobot_teleop
{

/**
 * @brief Manages the state of the leader-follower teleoperation.
 */
class StateManager
{
public:
  /**
   * @brief States of the teleoperation state machine.
   */
  enum class State
  {
    /** Teleoperation is inactive. */
    kIdle,

    /** Waiting for the TELEOP control mode to be activated. */
    kWaitingForControlMode,

    /** Waiting for valid leader and follower joint states. */
    kWaitingForJointStates,

    /** Aligning the follower with the leader pose. */
    kAligning,

    /** Waiting for the leader guiding mode to be enabled. */
    kWaitingForGuiding,

    /** Tracking leader joint positions with the follower. */
    kTracking
  };

  /**
   * @brief Get the current teleoperation state.
   *
   * @return Current state.
   */
  [[nodiscard]] State state() const noexcept
  {
    return state_;
  }

  /**
   * @brief Transition to a new teleoperation state.
   *
   * @param state New state.
   */
  void transitionTo(
    State state) noexcept
  {
    state_ = state;
  }

  /**
   * @brief Check whether the current state matches a given state.
   *
   * @param state State to compare against.
   * @return true if the states match, otherwise false.
   */
  [[nodiscard]] bool is(
    State state) const noexcept
  {
    return state_ == state;
  }

private:
  State state_{State::kIdle};
};

}  // namespace lerobot_teleop
