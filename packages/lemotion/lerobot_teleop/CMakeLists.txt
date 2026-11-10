cmake_minimum_required(VERSION 3.22)
project(lerobot_teleop)

# Set CMake policy for modern find_package behavior
cmake_policy(SET CMP0074 NEW)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

############################################################
# Find Required Packages
############################################################

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(lerobot_interfaces REQUIRED)

############################################################
# Declare Executables
############################################################

# Leader Follower Teleop Node

add_executable(leader_follower_teleop
  src/leader_follower_teleop_node.cpp
  src/lerobot_teleop/leader_follower_teleop.cpp
  src/lerobot_teleop/follower.cpp
  src/lerobot_teleop/leader.cpp
  src/lerobot_teleop/robot.cpp
  src/lerobot_teleop/filters/low_pass_filter.cpp
)

target_include_directories(leader_follower_teleop
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(leader_follower_teleop
  rclcpp
  rclcpp_lifecycle
  sensor_msgs
  std_msgs
  std_srvs
  lerobot_interfaces
)

target_compile_features(leader_follower_teleop
  PUBLIC
    cxx_std_20
)

############################################################
# Installation
############################################################

install(
  TARGETS
    leader_follower_teleop
  DESTINATION lib/${PROJECT_NAME}
)

############################################################
# Linting and Testing
############################################################

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(lifecycle_msgs REQUIRED)

  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(
    test_leader_follower_teleop
    test/leader_follower_teleop_test_fixture.cpp
    test/test_alignment.cpp
    test/test_tracking.cpp
    test/test_joint_mapping.cpp
    src/lerobot_teleop/leader_follower_teleop.cpp
    src/lerobot_teleop/follower.cpp
    src/lerobot_teleop/leader.cpp
    src/lerobot_teleop/robot.cpp
    src/lerobot_teleop/filters/low_pass_filter.cpp
  )

  target_include_directories(
    test_leader_follower_teleop
    PUBLIC
      $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  )

  ament_target_dependencies(
    test_leader_follower_teleop
    rclcpp
    rclcpp_lifecycle
    lifecycle_msgs
    lerobot_interfaces
    sensor_msgs
    std_msgs
    std_srvs
  )

  target_compile_features(
    test_leader_follower_teleop
    PUBLIC
      cxx_std_20
  )
endif()

############################################################
# Finalization
############################################################

install(DIRECTORY
  include
  launch
  config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
