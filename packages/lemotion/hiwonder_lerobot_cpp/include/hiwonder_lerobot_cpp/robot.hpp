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
#include <memory>
#include <string>
#include <vector>

#include "hiwonder_servo_driver/hiwonder_bus.hpp"
#include "hiwonder_servo_driver/motor.hpp"
#include "hiwonder_servo_driver/serial_port.hpp"
#include "lerobot_cpp/robot.hpp"

namespace hiwonder
{

/**
 * @brief Implements the generic LeRobot interface for HiWonder servo hardware.
 */
class LeRobot : public lerobot::Robot
{
public:
  LeRobot() = default;

  ~LeRobot() override = default;

  /**
   * @brief Configures the HiWonder robot backend.
   *
   * The configuration is rejected while connected. The motor IDs must be
   * non-empty, unique and valid HiWonder servo IDs (0-253). Their order is
   * preserved. An invalid configuration leaves the previous state unchanged.
   *
   * @param config Robot configuration containing serial settings and motor IDs.
   * @return True if the configuration is valid, otherwise false.
   */
  bool configure(
    const lerobot::RobotConfig & config) override;

  /**
   * @brief Connects to the configured HiWonder servo bus.
   *
   * @return True if the connection succeeds, otherwise false.
   */
  bool connect() override;

  /**
   * @brief Disconnects from the HiWonder servo bus.
   */
  void disconnect() override;

  /**
   * @brief Checks whether the robot is connected.
   *
   * @return True if the robot is connected, otherwise false.
   */
  [[nodiscard]] bool isConnected() const noexcept override;

  /**
   * @brief Returns a motor by index.
   *
   * @param index Motor index.
   * @return Reference to the requested motor.
   */
  Motor & motor(
    std::size_t index);

  /**
   * @brief Returns a motor by index.
   *
   * @param index Motor index.
   * @return Const reference to the requested motor.
   */
  const Motor & motor(
    std::size_t index) const;

  /**
   * @brief Returns the number of configured motors.
   *
   * @return Number of configured motors.
   */
  [[nodiscard]] std::size_t motorCount() const noexcept override;

  /**
   * @brief Returns the configured motor IDs in configuration order.
   *
   * @return Configured motor IDs.
   */
  [[nodiscard]] const std::vector<uint8_t> & motorIds() const noexcept
  {
    return motor_ids_;
  }

  /**
   * @brief Enables or disables torque for all motors.
   *
   * @param enabled True to enable torque, false to disable it.
   * @return True if the operation succeeds, otherwise false.
   */
  bool setTorqueEnabled(
    bool enabled) override;

  /**
   * @brief Reads the current raw positions of all motors.
   *
   * Read positions are not restricted to the supported command range.
   *
   * @param positions Vector receiving the motor positions.
   * @return True if all positions are read successfully, otherwise false.
   */
  bool readPositions(
    std::vector<int16_t> & positions) override;

  /**
   * @brief Reads the current raw states of all motors.
   * @param states Vector receiving the motor states (position, velocity, current).
   * @return True if all states are read successfully, otherwise false.
   */
  bool readStates(
    std::vector<lerobot::JointState> & states) override;

  /**
   * @brief Writes raw target positions to all motors.
   *
   * All positions must be within the supported servo command range.
   * If any position is invalid, no command is sent.
   *
   * @param positions Target positions for all motors.
   * @return True if the positions are valid and written successfully,
   * otherwise false.
   */
  bool writePositions(
    const std::vector<int16_t> & positions) override;

  /**
   * @brief Writes raw target positions with movement parameters.
   *
   * All positions must be within the supported servo command range.
   * If any position is invalid, no command is sent.
   *
   * @param positions Target positions for all motors.
   * @param move_time_ms Movement duration in milliseconds.
   * @param move_speed Movement speed.
   * @return True if the positions are valid and written successfully,
   * otherwise false.
   */
  bool writePositions(
    const std::vector<int16_t> & positions,
    uint16_t move_time_ms,
    uint16_t move_speed);

  /**
   * @brief Validates whether the given raw positions are within the supported range.
   *
   * @param positions Raw positions to validate.
   * @return True if all positions are valid, otherwise false.
   */
  bool validatePositions(
    const std::vector<int16_t> & positions) const override;

private:
  static constexpr uint8_t kMaxServoId = 253;
  static constexpr int16_t kMinCommandPosition = 0;
  static constexpr int16_t kMaxCommandPosition = 4095;

  /**
   * @brief Checks whether a raw position can be used as a servo target.
   *
   * @param position Raw target position.
   * @return True if the position is within the supported command range.
   */
  [[nodiscard]] static bool isValidCommandPosition(
    int16_t position) noexcept;

  std::string port_;
  uint32_t baud_rate_{1000000};

  std::vector<uint8_t> motor_ids_;

  std::unique_ptr<SerialPort> serial_;
  std::unique_ptr<HiwonderBus> bus_;
  std::vector<std::unique_ptr<Motor>> motors_;
};

}  // namespace hiwonder
