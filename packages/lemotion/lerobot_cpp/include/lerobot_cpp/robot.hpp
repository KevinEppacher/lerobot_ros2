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

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lerobot
{

/**
 * @brief Represents the state of a single joint.
 */
struct JointState
{
  int16_t position{};
  int16_t velocity{};
  uint16_t current{};
};

/**
 * @brief Configuration parameters for a LeRobot backend.
 */
struct RobotConfig
{
  /// Serial port used for communication with the robot.
  std::string port;

  /// Serial communication baud rate.
  uint32_t baud_rate{1000000};

  /// Ordered motor IDs; the number of motors is motor_ids.size().
  std::vector<uint8_t> motor_ids;
};

/**
 * @brief Defines the generic interface for LeRobot hardware backends.
 */
class Robot
{
public:
  Robot() = default;
  virtual ~Robot() = default;

  /**
   * @brief Configures the robot backend.
   *
   * @param config Backend configuration parameters.
   * @return True if the configuration is valid, otherwise false.
   */
  virtual bool configure(
    const RobotConfig & config) = 0;

  /**
   * @brief Connects to the robot hardware.
   *
   * @return True if the connection succeeds, otherwise false.
   */
  virtual bool connect() = 0;

  /**
   * @brief Disconnects from the robot hardware.
   */
  virtual void disconnect() = 0;

  /**
   * @brief Checks whether the robot is connected.
   *
   * @return True if the robot is connected, otherwise false.
   */
  [[nodiscard]] virtual bool isConnected() const noexcept = 0;

  /**
   * @brief Returns the number of configured motors.
   *
   * @return Number of motors.
   */
  [[nodiscard]] virtual std::size_t motorCount() const noexcept = 0;

  /**
   * @brief Enables or disables torque for all motors.
   *
   * @param enabled True to enable torque, false to disable it.
   * @return True if the operation succeeds, otherwise false.
   */
  virtual bool setTorqueEnabled(
    bool enabled) = 0;

  /**
   * @brief Reads the current raw positions of all motors.
   *
   * @param positions Vector receiving the motor raw positions (ticks).
   * @return True if all positions are read successfully, otherwise false.
   */
  virtual bool readPositions(
    std::vector<int16_t> & positions) = 0;

  /**
   * @brief Writes raw target positions to all motors.
   *
   * @param positions Target positions for all motors.
   * @return True if the positions are written successfully, otherwise false.
   */
  virtual bool writePositions(
    const std::vector<int16_t> & positions) = 0;

  /**
   * @brief Validates whether the given raw positions are within the supported range.
   * @param positions Raw positions to validate.
   * @return True if all positions are valid, otherwise false.
   */
  virtual bool validatePositions(
    const std::vector<int16_t> & positions) const = 0;

  /**
   * @brief Reads the current raw states of all motors.
   * @param states Vector receiving the motor states (position, velocity, current).
   * @return True if all states are read successfully, otherwise false.
   */
  virtual bool readStates(
    std::vector<JointState> & states) = 0;
};

}  // namespace lerobot
