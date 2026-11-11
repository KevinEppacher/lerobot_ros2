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
#include <cstdint>
#include <exception>
#include <iostream>
#include <limits>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "hiwonder_lerobot_cpp/robot.hpp"

namespace
{

constexpr int kMinPosition = 0;
constexpr int kMaxPosition = 4095;

struct MotorCommand
{
  uint8_t id;
  int value;
};

struct Options
{
  std::string port;
  int dof = 5;
  bool relative = false;
  std::optional<int> all_value;
  std::vector<MotorCommand> motor_commands;
};

void printUsage(const char * program, std::ostream & out)
{
  out
    << "Usage:\n"
    << "  " << program << " <port> [--dof <5|6>]\n"
    << "  " << program
    << " <port> [--dof <5|6>] --motor <id:ticks> [--motor <id:ticks> ...]\n"
    << "  " << program
    << " <port> [--dof <5|6>] --all <ticks>\n\n"
    << "Options:\n"
    << "  --dof <5|6>        Number of arm joints (default: 5)\n"
    << "  --motor <id:ticks> Set the target for a specific motor\n"
    << "  --all <ticks>      Set the same target for all motors\n"
    << "  --relative         Interpret ticks as relative offsets\n"
    << "  --help             Show this help message\n\n"
    << "  Without --motor or --all, hold all motors at their current positions.\n\n"
    << "Examples:\n"
    << "  " << program << " /dev/ttyACM0 --dof 6\n"
    << "  " << program << " /dev/ttyACM0 --dof 6 --motor 3:2048\n"
    << "  " << program << " /dev/ttyACM0 --motor 1:1500 --motor 2:2500\n"
    << "  " << program << " /dev/ttyACM0 --relative --motor 2:-100\n"
    << "  " << program << " /dev/ttyACM0 --relative --all 100\n";
}

bool parseInteger(const std::string & text, int & value)
{
  try {
    std::size_t parsed = 0;
    const int64_t result = std::stoll(text, &parsed);

    if (
      parsed != text.size() ||
      result < std::numeric_limits<int>::min() ||
      result > std::numeric_limits<int>::max())
    {
      return false;
    }

    value = static_cast<int>(result);
    return true;
  } catch (const std::exception &) {
    return false;
  }
}

bool parseMotorCommand(
  const std::string & argument,
  MotorCommand & command)
{
  const auto separator = argument.find(':');

  if (
    separator == std::string::npos ||
    separator == 0 ||
    separator == argument.size() - 1)
  {
    return false;
  }

  int id = 0;
  int value = 0;

  if (
    !parseInteger(argument.substr(0, separator), id) ||
    !parseInteger(argument.substr(separator + 1), value))
  {
    return false;
  }

  if (id < 1 || id > std::numeric_limits<uint8_t>::max()) {
    return false;
  }

  command = {
    static_cast<uint8_t>(id),
    value
  };

  return true;
}

bool parseArguments(
  int argc,
  char ** argv,
  Options & options)
{
  if (argc < 2) {
    return false;
  }

  options.port = argv[1];

  for (int i = 2; i < argc; ++i) {
    const std::string argument = argv[i];

    if (argument == "--dof") {
      if (++i >= argc || !parseInteger(argv[i], options.dof)) {
        return false;
      }

      if (options.dof != 5 && options.dof != 6) {
        return false;
      }
    } else if (argument == "--motor") {
      if (++i >= argc) {
        return false;
      }

      MotorCommand command{};

      if (!parseMotorCommand(argv[i], command)) {
        return false;
      }

      options.motor_commands.push_back(command);
    } else if (argument == "--all") {
      int value = 0;

      if (++i >= argc || !parseInteger(argv[i], value)) {
        return false;
      }

      options.all_value = value;
    } else if (argument == "--relative") {
      options.relative = true;
    } else {
      return false;
    }
  }

  if (options.all_value.has_value() && !options.motor_commands.empty()) {
    std::cerr << "Cannot combine --all and --motor.\n";
    return false;
  }

  std::set<uint8_t> used_ids;

  for (const auto & command : options.motor_commands) {
    if (command.id > options.dof + 1) {
      std::cerr
                << "Motor ID " << static_cast<int>(command.id)
                << " exceeds the configured motor count.\n";
      return false;
    }

    if (!used_ids.insert(command.id).second) {
      std::cerr
                << "Duplicate motor ID: "
                << static_cast<int>(command.id) << '\n';
      return false;
    }
  }

  if (!options.relative) {
    const auto validPosition = [](int value) {
        return value >= kMinPosition && value <= kMaxPosition;
      };

    if (
      options.all_value.has_value() &&
      !validPosition(*options.all_value))
    {
      std::cerr << "All target positions must be between "
                << kMinPosition << " and " << kMaxPosition
                << " ticks.\n";
      return false;
    }

    for (const auto & command : options.motor_commands) {
      if (!validPosition(command.value)) {
        std::cerr << "Motor target position must be between "
                  << kMinPosition << " and " << kMaxPosition
                  << " ticks.\n";
        return false;
      }
    }
  }

  return true;
}

bool calculateTarget(
  int16_t current,
  int value,
  bool relative,
  int16_t & target)
{
  const int64_t requested = relative ?
    static_cast<int64_t>(current) + value :
    static_cast<int64_t>(value);

  if (requested < kMinPosition || requested > kMaxPosition) {
    return false;
  }

  target = static_cast<int16_t>(requested);
  return true;
}

}  // namespace

int main(int argc, char ** argv)
{
  if (argc == 2 && std::string(argv[1]) == "--help") {
    printUsage(argv[0], std::cout);    // --help
    return 0;
  }

  Options options;

  if (!parseArguments(argc, argv, options)) {
    printUsage(argv[0], std::cerr);    // Invalid arguments
    return 1;
  }

  hiwonder::LeRobot robot;

  lerobot::RobotConfig config;
  config.port = options.port;
  config.baud_rate = 1000000;

    // Arm joints and gripper use sequential servo IDs starting at 1.
  for (int id = 1; id <= options.dof + 1; ++id) {
    config.motor_ids.push_back(static_cast<uint8_t>(id));
  }

  if (!robot.configure(config)) {
    std::cerr << "Failed to configure robot.\n";
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

  if (current_positions.size() != config.motor_ids.size()) {
    std::cerr << "Unexpected number of motor positions.\n";
    return 1;
  }

    // Preserve the current positions of motors that are not selected.
  std::vector<int16_t> target_positions = current_positions;
  std::vector<bool> selected(current_positions.size(), false);

  if (options.all_value.has_value()) {
    for (std::size_t i = 0; i < selected.size(); ++i) {
      selected[i] = true;
    }
  } else {
    for (const auto & command : options.motor_commands) {
      const auto it = std::find(
                config.motor_ids.begin(),
                config.motor_ids.end(),
                command.id
      );

      if (it == config.motor_ids.end()) {
        std::cerr
                    << "Motor ID "
                    << static_cast<int>(command.id)
                    << " not found.\n";
        return 1;
      }

      const std::size_t index = static_cast<std::size_t>(
        std::distance(config.motor_ids.begin(), it)
      );

      selected[index] = true;
    }
  }

    // Calculate and validate every target before sending commands.
  for (std::size_t i = 0; i < target_positions.size(); ++i) {
    if (!selected[i]) {
      continue;
    }

    int value = 0;

    if (options.all_value.has_value()) {
      value = *options.all_value;
    } else {
      const uint8_t id = config.motor_ids[i];

      const auto it = std::find_if(
                options.motor_commands.begin(),
                options.motor_commands.end(),
        [id](const MotorCommand & command) {
          return command.id == id;
                }
      );

      value = it->value;
    }

    if (!calculateTarget(
            current_positions[i],
            value,
            options.relative,
            target_positions[i]))
    {
      std::cerr
                << "Target position out of range for motor "
                << static_cast<int>(config.motor_ids[i])
                << ". Allowed range: "
                << kMinPosition << " - " << kMaxPosition
                << " ticks.\n";

      return 1;
    }
  }

  std::cout << "\nMotor positions:\n";

  for (std::size_t i = 0; i < target_positions.size(); ++i) {
    std::cout
            << "Motor "
            << static_cast<int>(config.motor_ids[i])
            << ": "
            << current_positions[i]
            << " -> "
            << target_positions[i]
            << " ticks";

    if (!selected[i]) {
      std::cout << " (unchanged)";
    }

    std::cout << '\n';
  }

  std::cout << "\nSending position commands...\n";

  if (options.all_value.has_value()) {
    if (!robot.writePositions(target_positions)) {
      std::cerr << "Failed to write motor positions.\n";
      return 1;
    }
  } else if (!options.motor_commands.empty()) {
    for (std::size_t i = 0; i < target_positions.size(); ++i) {
      if (!selected[i]) {
        continue;
      }

      if (!robot.writePosition(config.motor_ids[i], target_positions[i])) {
        std::cerr
                  << "Failed to write position for motor "
                  << static_cast<int>(config.motor_ids[i])
                  << ".\n";
        return 1;
      }
    }
  } else {
    if (!robot.writePositions(target_positions)) {
      std::cerr << "Failed to hold current motor positions.\n";
      return 1;
    }
  }

  std::cout << "Command sent successfully.\n";

  return 0;
}
