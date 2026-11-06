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

#include <yaml-cpp/yaml.h>

#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "hiwonder_lerobot_cpp/follower.hpp"

namespace
{

struct Joint
{
  std::string name;
  uint8_t servo_id;
};

struct JointCalibration
{
  int16_t lower_position;
  int16_t upper_position;
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

// Parses the optional "--dof <5|6>" arguments that follow the positional ones.
bool parseDof(int argc, char ** argv, int first, int & dof)
{
  dof = 5;

  if (first == argc) {
    return true;
  }

  if (first + 2 != argc || std::string(argv[first]) != "--dof") {
    return false;
  }

  const std::string value = argv[first + 1];

  if (value != "5" && value != "6") {
    return false;
  }

  dof = std::stoi(value);

  return true;
}

void waitForEnter()
{
  std::string input;
  std::getline(std::cin, input);
}

bool readPosition(
  hiwonder::Follower & robot,
  std::size_t joint_count,
  std::size_t index,
  int16_t & position)
{
  std::vector<int16_t> positions;

  if (!robot.readPositions(positions)) {
    std::cerr
      << "Failed to read motor positions.\n";

    return false;
  }

  if (positions.size() != joint_count) {
    std::cerr
      << "Unexpected motor count: "
      << positions.size()
      << '\n';

    return false;
  }

  position = positions[index];

  return true;
}

bool calibrateJoint(
  hiwonder::Follower & robot,
  const std::vector<Joint> & joints,
  std::size_t index,
  JointCalibration & calibration)
{
  const auto & joint = joints[index];

  std::cout
    << "\nJoint "
    << index + 1
    << "/"
    << joints.size()
    << ": "
    << joint.name
    << " (servo "
    << static_cast<unsigned int>(joint.servo_id)
    << ")\n"
    << "----------------------------------------\n";

  std::cout
    << "Move the joint to its URDF LOWER limit.\n"
    << "Press ENTER to record the position.";

  waitForEnter();

  if (!readPosition(
      robot,
      joints.size(),
      index,
      calibration.lower_position))
  {
    return false;
  }

  std::cout
    << "Recorded lower position: "
    << calibration.lower_position
    << "\n\n";

  std::cout
    << "Move the joint to its URDF UPPER limit.\n"
    << "Press ENTER to record the position.";

  waitForEnter();

  if (!readPosition(
      robot,
      joints.size(),
      index,
      calibration.upper_position))
  {
    return false;
  }

  std::cout
    << "Recorded upper position: "
    << calibration.upper_position
    << '\n';

  if (calibration.lower_position ==
    calibration.upper_position)
  {
    std::cerr
      << "Lower and upper positions are identical for joint '"
      << joint.name
      << "'.\n";

    return false;
  }

  return true;
}

void printCalibration(
  const std::vector<Joint> & joints,
  const std::vector<JointCalibration> & calibration)
{
  std::cout
    << "\n\nLeRobot Calibration\n"
    << "====================\n\n";

  std::cout
    << std::left
    << std::setw(18) << "NAME"
    << std::right
    << std::setw(10) << "SERVO"
    << std::setw(12) << "LOWER"
    << std::setw(12) << "UPPER"
    << '\n';

  std::cout
    << "----------------------------------------------------\n";

  for (std::size_t i = 0; i < calibration.size(); ++i) {
    std::cout
      << std::left
      << std::setw(18) << joints[i].name
      << std::right
      << std::setw(10)
      << static_cast<unsigned int>(
      joints[i].servo_id)
      << std::setw(12)
      << calibration[i].lower_position
      << std::setw(12)
      << calibration[i].upper_position
      << '\n';
  }
}

bool saveCalibration(
  const std::string & path,
  const std::vector<Joint> & joints,
  const std::vector<JointCalibration> & calibration)
{
  if (calibration.size() != joints.size()) {
    std::cerr
      << "Calibration data does not match joint count.\n";

    return false;
  }

  YAML::Node root;

  for (std::size_t i = 0; i < calibration.size(); ++i) {
    YAML::Node joint;

    joint["servo_id"] =
      static_cast<unsigned int>(
      joints[i].servo_id);

    joint["lower_position"] =
      calibration[i].lower_position;

    joint["upper_position"] =
      calibration[i].upper_position;

    root[joints[i].name] = joint;
  }

  std::ofstream output(path);

  if (!output.is_open()) {
    std::cerr
      << "Failed to open calibration file: "
      << path
      << '\n';

    return false;
  }

  output << root << '\n';

  if (!output.good()) {
    std::cerr
      << "Failed to write calibration file: "
      << path
      << '\n';

    return false;
  }

  return true;
}

}  // namespace

int main(int argc, char ** argv)
{
  int dof = 5;

  if (argc < 3 || !parseDof(argc, argv, 3, dof)) {
    std::cerr
      << "Usage:\n"
      << "  lerobot-calibrate <port> <calibration.yaml> [--dof <5|6>]\n"
      << "\n"
      << "Example:\n"
      << "  lerobot-calibrate /dev/ttyACM0 "
      << "/app/src/so101_description/config/calibration.yaml --dof 6\n";

    return 1;
  }

  const std::vector<Joint> joints = makeJoints(dof);

  const std::string port = argv[1];
  const std::string calibration_path = argv[2];

  hiwonder::Follower robot;

  lerobot::RobotConfig config;
  config.port = port;
  config.baud_rate = 1000000;
  for (const auto & joint : joints) {
    config.motor_ids.push_back(joint.servo_id);
  }

  if (!robot.configure(config)) {
    std::cerr << "Failed to configure robot\n";
    return 1;
  }

  std::cout
    << "LeRobot Calibration\n"
    << "====================\n\n"
    << "Connecting to robot...\n";

  if (!robot.connect()) {
    std::cerr
      << "Failed to connect to robot.\n";

    return 1;
  }

  std::cout
    << "Connected successfully.\n"
    << "Disabling motor torque...\n";

  if (!robot.setTorqueEnabled(false)) {
    std::cerr
      << "Failed to disable motor torque.\n";

    return 1;
  }

  std::cout
    << "Torque disabled.\n\n"
    << "Each joint will now be calibrated individually.\n"
    << "For each joint:\n"
    << "  1. Move it to the position corresponding to "
    << "the URDF lower limit.\n"
    << "  2. Press ENTER.\n"
    << "  3. Move it to the position corresponding to "
    << "the URDF upper limit.\n"
    << "  4. Press ENTER.\n\n"
    << "Press ENTER to begin.";

  waitForEnter();

  std::vector<JointCalibration> calibration(
    joints.size());

  for (std::size_t i = 0; i < joints.size(); ++i) {
    if (!calibrateJoint(
        robot,
        joints,
        i,
        calibration[i]))
    {
      return 1;
    }
  }

  printCalibration(joints, calibration);

  std::cout
    << "\nCalibration file:\n"
    << calibration_path
    << "\n\n"
    << "Press ENTER to save calibration.";

  waitForEnter();

  if (!saveCalibration(
      calibration_path,
      joints,
      calibration))
  {
    return 1;
  }

  std::cout
    << "\nCalibration saved successfully.\n";

  return 0;
}
