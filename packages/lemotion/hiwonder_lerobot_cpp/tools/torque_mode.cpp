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

#include <cstdint>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "hiwonder_servo_driver/hiwonder_bus.hpp"
#include "hiwonder_servo_driver/serial_port.hpp"
#include "lerobot_cpp/robot.hpp"

#include "hiwonder_lerobot_cpp/robot.hpp"

namespace
{

constexpr uint32_t kBaudRate = 1000000;
constexpr uint8_t kMinServoId = 1;
constexpr uint8_t kMaxServoId = 20;

// Scans the same ID range as hiwonder-scan. Motors must have contiguous IDs
// starting at 1, so a gap is reported as a missing or unresponsive motor.
std::vector<uint8_t> discoverMotorIds(const std::string & port)
{
  hiwonder::SerialPort serial(port, kBaudRate);
  serial.open();

  hiwonder::HiwonderBus bus(serial);

  std::vector<uint8_t> ids;

  for (uint16_t id = kMinServoId; id <= kMaxServoId; ++id) {
    if (bus.ping(static_cast<uint8_t>(id))) {
      ids.push_back(static_cast<uint8_t>(id));
    }
  }

  if (ids.empty()) {
    throw std::runtime_error("No motors found on the bus");
  }

  for (std::size_t i = 0; i < ids.size(); ++i) {
    if (ids[i] != i + 1) {
      throw std::runtime_error(
        "Motor ID " + std::to_string(i + 1) +
        " is missing or unresponsive (found IDs are not contiguous from 1)");
    }
  }

  serial.close();

  return ids;
}

}  // namespace

int main(int argc, char ** argv)
{
  if (argc != 3) {
    std::cerr
      << "Usage: lerobot-torque-mode <port> <on|off>\n"
      << "\n"
      << "  off  Disable torque output for manual guiding\n"
      << "  on   Enable torque output for position control\n"
      << "\n"
      << "Example:\n"
      << "  lerobot-torque-mode /dev/ttyACM0 off\n";

    return 1;
  }

  const std::string port = argv[1];
  const std::string mode = argv[2];

  if (mode != "on" && mode != "off") {
    std::cerr
      << "Invalid mode: "
      << mode
      << ". Use 'on' or 'off'.\n";

    return 1;
  }

  const bool enable_torque = mode == "on";

  std::vector<uint8_t> discovered_ids;

  try {
    discovered_ids = discoverMotorIds(port);
  } catch (const std::exception & exception) {
    std::cerr << "Error: " << exception.what() << '\n';
    return 1;
  }

  std::cout << "Found " << discovered_ids.size() << " motor(s): ";
  for (const auto id : discovered_ids) {
    std::cout << static_cast<int>(id) << ' ';
  }
  std::cout << '\n';

  hiwonder::LeRobot robot;
  lerobot::RobotConfig config;
  config.port = port;
  config.baud_rate = 1000000;
  config.motor_ids = discovered_ids;

  if(!robot.configure(config)) {
    std::cerr << "Failed to configure robot\n";
    return 1;
  }

  if (!robot.connect()) {
    std::cerr << "Failed to connect to robot.\n";
    return 1;
  }

  if (!robot.setTorqueEnabled(enable_torque)) {
    std::cerr << "Failed to set torque mode.\n";
    return 1;
  }

  std::cout
    << (enable_torque ?
  "Position control enabled.\n" :
  "Guiding mode enabled.\n");

  return 0;
}
