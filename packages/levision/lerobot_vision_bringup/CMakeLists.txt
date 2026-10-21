cmake_minimum_required(VERSION 3.22)
project(lerobot_vision_bringup)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

############################################################
# Find Required Packages
############################################################

find_package(ament_cmake REQUIRED)
find_package(usb_cam REQUIRED)

############################################################
# Install
############################################################

# Install launch files and configuration
install(
    DIRECTORY
        launch
        config
    DESTINATION share/${PROJECT_NAME}
)

# Install command-line tools
install(
    PROGRAMS
        scripts/lerobot-list-cameras
    DESTINATION bin
)

# Install Bash completion
install(
  FILES config/bash_completion/lerobot-list-cameras.bash
  DESTINATION share/bash-completion/completions
  RENAME lerobot-list-cameras
)

############################################################
# Finalization
############################################################

ament_package()
