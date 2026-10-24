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

#include "leader_follower_teleop_test_fixture.hpp"

namespace lerobot_teleop
{

using namespace std::chrono_literals;

TEST_F(
  LeaderFollowerTeleopTest,
  MapsShuffledJointStatesToControllerOrder)
{
  const std::vector<std::string> shuffled_joint_names{
    "joint_3",
    "gripper",
    "joint_2",
    "joint_1",
    "joint_4",
    "joint_5"
  };

  const std::vector<double> shuffled_leader_positions{
    0.3,
    0.6,
    -0.2,
    0.5,
    -0.4,
    0.1
  };

  const std::vector<double> shuffled_follower_positions{
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0
  };

  const std::vector<double> expected_command{
    0.5,
    -0.2,
    0.3,
    -0.4,
    0.1,
    0.6
  };

  activateTeleop();

  publishFor(
    shuffled_joint_names,
    shuffled_leader_positions,
    shuffled_follower_positions,
    500ms);

  ASSERT_FALSE(
    received_commands_.empty());

  ASSERT_TRUE(
    guiding_enabled_);

  expectNear(
    received_commands_.back(),
    expected_command,
    0.02);
}

}  // namespace lerobot_teleop
