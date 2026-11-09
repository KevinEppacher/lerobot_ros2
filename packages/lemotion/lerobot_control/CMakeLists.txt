cmake_minimum_required(VERSION 3.8)
project(lerobot_control)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

############################################################
# Find Required Packages
############################################################

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(controller_manager_msgs REQUIRED)
find_package(lerobot_interfaces REQUIRED)

############################################################
# Declare Executables
############################################################

# Control Mode Manager Node

add_executable(control_mode_manager
    src/lerobot_control/control_mode_manager.cpp
    src/control_mode_manager_node.cpp
)

target_compile_features(control_mode_manager PUBLIC cxx_std_17)

target_include_directories(control_mode_manager PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(control_mode_manager
    rclcpp
    controller_manager_msgs
    lerobot_interfaces
)

############################################################
# Installation
############################################################

install(TARGETS
    control_mode_manager
    DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
    include/
    DESTINATION include
)

############################################################
# Linting and Testing
############################################################

if(BUILD_TESTING)
    find_package(ament_lint_auto REQUIRED)
    ament_lint_auto_find_test_dependencies()
endif()

############################################################
# Finalization
############################################################

ament_package()
