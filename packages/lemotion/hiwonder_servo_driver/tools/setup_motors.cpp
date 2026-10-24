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

#include <array>
#include <cstdint>
#include <exception>
#include <iostream>
#include <optional>
#include <string>

#include "hiwonder_servo_driver/hiwonder_bus.hpp"
#include "hiwonder_servo_driver/serial_port.hpp"
#include "hiwonder_servo_driver/servo.hpp"

namespace
{

constexpr uint32_t kBaudRate = 1000000;

constexpr uint8_t kMinServoId = 1;
constexpr uint8_t kMaxServoId = 20;

struct Joint
{
  const char * name;
  uint8_t id;
};

constexpr std::array<Joint, 6> kJoints{{
  {"joint_1", 1},
  {"joint_2", 2},
  {"joint_3", 3},
  {"joint_4", 4},
  {"joint_5", 5},
  {"gripper", 6},
}};

std::optional<uint8_t> findSingleServo(
  hiwonder::HiwonderBus & bus)
{
  std::optional<uint8_t> found_id;

  for (
    uint16_t id = kMinServoId;
    id <= kMaxServoId;
    ++id)
  {
    const auto servo_id = static_cast<uint8_t>(id);

    if (!bus.ping(servo_id)) {
      continue;
    }

    if (found_id.has_value()) {
      throw std::runtime_error(
                "More than one servo detected. "
                "Connect exactly one servo.");
    }

    found_id = servo_id;
  }

  return found_id;
}

}  // namespace

int main(int argc, char ** argv)
{
  if (argc != 2) {
    std::cerr
            << "Usage: hiwonder-setup-motors <port>\n"
            << "Example: hiwonder-setup-motors /dev/ttyACM0\n";

    return 1;
  }

  const std::string port = argv[1];

  try {
    hiwonder::SerialPort serial(port, kBaudRate);
    serial.open();

    hiwonder::HiwonderBus bus(serial);

    std::cout
            << "Hiwonder motor setup\n"
            << "Port: " << port << '\n'
            << "Baud rate: " << kBaudRate << "\n\n"
            << "IMPORTANT:\n"
            << "Connect exactly one servo at a time.\n\n";

    for (const auto & joint : kJoints) {
      std::cout
                << "Connect the motor for '" << joint.name << "'.\n"
                << "It will be configured as ID "
                << static_cast<int>(joint.id)
                << ".\n"
                << "Press Enter when ready.";

      std::cin.get();

      const auto current_id = findSingleServo(bus);

      if (!current_id.has_value()) {
        std::cerr
                    << "\nNo servo detected. Setup aborted.\n";

        return 1;
      }

      std::cout
                << "\nServo detected at ID "
                << static_cast<int>(*current_id)
                << ".\n";

      if (*current_id == joint.id) {
        std::cout
                    << "Servo already has the correct ID.\n";
      } else {
        hiwonder::Servo servo(bus, *current_id);

        std::cout
                    << "Changing ID "
                    << static_cast<int>(*current_id)
                    << " -> "
                    << static_cast<int>(joint.id)
                    << "...\n";

        if (!servo.setId(joint.id)) {
          std::cerr
                        << "Failed to change servo ID. "
                        << "Setup aborted.\n";

          return 1;
        }

        std::cout << "ID changed successfully.\n";
      }

      if (!bus.ping(joint.id)) {
        std::cerr
                    << "Verification failed for ID "
                    << static_cast<int>(joint.id)
                    << ". Setup aborted.\n";

        return 1;
      }

      std::cout
                << "Verified ID "
                << static_cast<int>(joint.id)
                << ".\n\n";

      if (&joint != &kJoints.back()) {
        std::cout
                    << "Disconnect this motor before continuing.\n"
                    << "Press Enter after disconnecting.";

        std::cin.get();

        std::cout << '\n';
      }
    }

    std::cout
            << "Motor setup complete.\n"
            << "Configured IDs:\n";

    for (const auto & joint : kJoints) {
      std::cout
                << "  "
                << static_cast<int>(joint.id)
                << ": "
                << joint.name
                << '\n';
    }
  } catch (const std::exception & exception) {
    std::cerr
            << "Error: "
            << exception.what()
            << '\n';

    return 1;
  }

  return 0;
}
