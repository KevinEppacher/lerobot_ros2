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

#include "hiwonder_lerobot_cpp/robot.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <stdexcept>

#include "hiwonder_servo_driver/registers.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace hiwonder
{

bool LeRobot::configure(
  const lerobot::RobotConfig & config)
{
  if (isConnected()) {
    return false;
  }

  if (config.motor_ids.empty()) {
    return false;
  }

  std::vector<uint8_t> seen_ids;
  seen_ids.reserve(config.motor_ids.size());

  for (const uint8_t id : config.motor_ids) {
    // 0xFE is the broadcast ID and 0xFF is reserved.
    if (id > kMaxServoId) {
      return false;
    }

    if (std::find(seen_ids.begin(), seen_ids.end(), id) != seen_ids.end()) {
      return false;
    }

    seen_ids.push_back(id);
  }

  port_ = config.port;
  baud_rate_ = config.baud_rate;
  motor_ids_ = config.motor_ids;
  return true;
}

bool LeRobot::connect()
{
  if (isConnected()) {
    return true;
  }

  try {
    serial_ =
      std::make_unique<SerialPort>(
      port_,
      baud_rate_);

    serial_->open();

    bus_ =
      std::make_unique<HiwonderBus>(
      *serial_);

    motors_.clear();

    for (const uint8_t id : motor_ids_) {
      motors_.push_back(
        std::make_unique<Motor>(
          id,
          *bus_));
    }

    for (auto & motor : motors_) {
      if (!motor->ping()) {
        disconnect();
        return false;
      }
    }

    return true;
  } catch (...) {
    disconnect();
    return false;
  }
}

void LeRobot::disconnect()
{
  motors_.clear();

  bus_.reset();

  if (serial_) {
    serial_->close();
    serial_.reset();
  }
}

bool LeRobot::isConnected() const noexcept
{
  return
    serial_ &&
    serial_->isOpen() &&
    bus_;
}

Motor & LeRobot::motor(
  std::size_t index)
{
  if (index >= motors_.size()) {
    throw std::out_of_range(
      "Motor index out of range");
  }

  return *motors_[index];
}

const Motor & LeRobot::motor(
  std::size_t index) const
{
  if (index >= motors_.size()) {
    throw std::out_of_range(
      "Motor index out of range");
  }

  return *motors_[index];
}

std::size_t LeRobot::motorCount() const noexcept
{
  return motor_ids_.size();
}

bool LeRobot::setTorqueEnabled(
  bool enabled)
{
  if (!isConnected()) {
    return false;
  }

  for (auto & motor : motors_) {
    if (!motor->setTorqueEnabled(enabled)) {
      return false;
    }
  }

  return true;
}

bool LeRobot::isValidCommandPosition(
  int16_t position) noexcept
{
  return
    position >= kMinCommandPosition &&
    position <= kMaxCommandPosition;
}

bool LeRobot::writePositions(
  const std::vector<int16_t> & positions)
{
  return writePositions(positions, 0, 0);
}

bool LeRobot::writePositions(
  const std::vector<int16_t> & positions,
  uint16_t move_time_ms,
  uint16_t move_speed)
{
  if (!isConnected()) {
    return false;
  }

  if (positions.size() != motors_.size()) {
    return false;
  }

  if (!std::all_of(
      positions.begin(),
      positions.end(),
      isValidCommandPosition))
  {
    return false;
  }

  constexpr std::size_t kBytesPerMotor = 6;

  std::vector<uint8_t> ids;
  std::vector<uint8_t> data(
    motors_.size() * kBytesPerMotor);

  ids.reserve(motors_.size());

  for (std::size_t i = 0; i < motors_.size(); ++i) {
    ids.push_back(motors_[i]->id());

    uint8_t * motor_data =
      data.data() + i * kBytesPerMotor;

    const auto raw_position =
      static_cast<uint16_t>(positions[i]);

    motor_data[0] =
      static_cast<uint8_t>(
      raw_position & 0xFFU);

    motor_data[1] =
      static_cast<uint8_t>(
      (raw_position >> 8) & 0xFFU);

    motor_data[2] =
      static_cast<uint8_t>(
      move_time_ms & 0xFFU);

    motor_data[3] =
      static_cast<uint8_t>(
      (move_time_ms >> 8) & 0xFFU);

    motor_data[4] =
      static_cast<uint8_t>(
      move_speed & 0xFFU);

    motor_data[5] =
      static_cast<uint8_t>(
      (move_speed >> 8) & 0xFFU);
  }

  return bus_->syncWrite(
    reg::kTargetPosition,
    static_cast<uint8_t>(kBytesPerMotor),
    ids,
    data);
}

bool LeRobot::readPositions(
  std::vector<int16_t> & positions)
{
  if (!isConnected()) {
    return false;
  }

  positions.resize(motors_.size());

  for (std::size_t i = 0; i < motors_.size(); ++i) {
    if (!motors_[i]->readPosition(positions[i])) {
      return false;
    }
  }

  return true;
}

bool LeRobot::validatePositions(
  const std::vector<int16_t> & positions) const
{
  return std::all_of(
    positions.begin(),
    positions.end(),
    isValidCommandPosition);
}

bool LeRobot::readStates(
  std::vector<lerobot::JointState> & states)
{
  if (!isConnected()) {
    return false;
  }

  states.resize(motors_.size());

  for (std::size_t i = 0; i < motors_.size(); ++i) {
    MotorState motor_state;

    if (!motors_[i]->readState(motor_state)) {
      return false;
    }

    states[i].position = motor_state.position;
    states[i].velocity = motor_state.velocity;
    states[i].current = motor_state.current;
  }

  return true;
}

bool LeRobot::writePosition(uint8_t motor_id, int16_t position)
{
  if (!isConnected() || !isValidCommandPosition(position)) {
    return false;
  }

  const auto it = std::find_if(
        motors_.begin(),
        motors_.end(),
    [motor_id](const auto & motor) {
      return motor->id() == motor_id;
        });

  if (it == motors_.end()) {
    return false;
  }

  return (*it)->writePosition(position);
}

}  // namespace hiwonder

PLUGINLIB_EXPORT_CLASS(hiwonder::LeRobot, lerobot::Robot)
