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

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

#include "hiwonder_lerobot_cpp/robot.hpp"

namespace
{

constexpr double kTicksPerRevolution = 4096.0;
constexpr double kDegreesPerRevolution = 360.0;

constexpr double kMovementDegrees = -10.0;

constexpr int16_t kMinPosition = 0;
constexpr int16_t kMaxPosition = std::numeric_limits<int16_t>::max();

int16_t addDegrees(
  int16_t position,
  double degrees)
{
  const auto delta = static_cast<int>(
    std::lround(
      degrees *
      kTicksPerRevolution /
      kDegreesPerRevolution));

  const int target =
    static_cast<int>(position) + delta;

  return static_cast<int16_t>(
    std::clamp(
      target,
      static_cast<int>(kMinPosition),
      static_cast<int>(kMaxPosition)));
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
      << "Usage: lerobot-test-move <port> [--dof <5|6>]\n"
      << "Example: lerobot-test-move /dev/ttyACM0 --dof 6\n";

    return 1;
  }

  if (argc == 4) {
    dof = std::stoi(argv[3]);
  }

  hiwonder::LeRobot robot;

  lerobot::RobotConfig config;
  config.port = argv[1];
  config.baud_rate = 1000000;
  // dof arm joints plus the gripper, with sequential servo IDs starting at 1.
  for (int id = 1; id <= dof + 1; ++id) {
    config.motor_ids.push_back(static_cast<uint8_t>(id));
  }

  if (!robot.configure(config)) {
    std::cerr << "Failed to configure robot\n";
    return 1;
  }

  if (!robot.connect()) {
    std::cerr << "Failed to connect to robot.\n";
    return 1;
  }

  std::vector<int16_t> current_positions;

  if (!robot.readPositions(current_positions)) {
    std::cerr << "Failed to read motor positions.\n";
    return 1;
  }

  std::vector<int16_t> target_positions(
    current_positions.size());

  for (std::size_t i = 0; i < target_positions.size(); ++i) {
    target_positions[i] = addDegrees(
      current_positions[i],
      kMovementDegrees);

    std::cout
      << "Motor "
      << static_cast<int>(robot.motor(i).id())
      << ": "
      << current_positions[i]
      << " -> "
      << target_positions[i]
      << " ticks ("
      << kMovementDegrees
      << " deg)\n";
  }

  std::cout
    << "\nMoving all motors by "
    << kMovementDegrees
    << " degrees...\n";

  if (!robot.writePositions(target_positions)) {
    std::cerr << "Failed to write motor positions.\n";
    return 1;
  }

  std::cout << "Command sent successfully.\n";

  return 0;
}
