cmake_minimum_required(VERSION 3.8)
project(lerobot_interfaces)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
    "srv/SetControlMode.srv"
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
