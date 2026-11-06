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
#include <optional>
#include <string>
#include <vector>

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
  std::string name;
  uint8_t id;
};

// Builds joint_1..joint_<dof> followed by the gripper on the next servo ID.
std::vector<Joint> makeJoints(int dof)
{
  std::vector<Joint> joints;

  for (int i = 1; i <= dof; ++i) {
    joints.push_back({"joint_" + std::to_string(i), static_cast<uint8_t>(i)});
  }

  joints.push_back({"gripper", static_cast<uint8_t>(dof + 1)});

  return joints;
}

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
  int dof = 5;

  if (
    (argc != 2 && argc != 4) ||
    (argc == 4 && (std::string(argv[2]) != "--dof" ||
    (std::string(argv[3]) != "5" && std::string(argv[3]) != "6"))))
  {
    std::cerr
            << "Usage: hiwonder-setup-motors <port> [--dof <5|6>]\n"
            << "Example: hiwonder-setup-motors /dev/ttyACM0 --dof 6\n";

    return 1;
  }

  if (argc == 4) {
    dof = std::stoi(argv[3]);
  }

  const std::string port = argv[1];
  const std::vector<Joint> joints = makeJoints(dof);

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

    for (const auto & joint : joints) {
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

      if (&joint != &joints.back()) {
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

    for (const auto & joint : joints) {
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
