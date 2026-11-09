#!/usr/bin/env bash

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
RESET='\033[0m'

set -euo pipefail

echo -e "${BOLD}${CYAN}Running tests inside the container...${RESET}"
cd /app

echo -e "${BOLD}${CYAN}Sourcing ROS 2 and workspace setup files...${RESET}"
set +u
# First source the specific ROS 2 distribution setup file, then the workspace.
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u

package_exists() {
    colcon list --names-only | grep -qx "$1"
}

run_colcon_tests() {
    local package="$1"
    local log_file

    if ! package_exists "$package"; then
        echo -e "${BOLD}${YELLOW}Package ${package} does not exist. Skipping.${RESET}"
        return
    fi

    log_file="$(mktemp)"

    if colcon test \
        --event-handlers console_direct+ \
        --packages-select "$package" \
        --return-code-on-test-failure \
        >"$log_file" 2>&1
    then
        echo -e "${GREEN}✓ ${package}${RESET}"
        rm -f "$log_file"
    else
        echo -e "${BOLD}${RED}✗ ${package} failed${RESET}"
        echo
        cat "$log_file"
        rm -f "$log_file"
        return 1
    fi
}

run_colcon_tests hiwonder_servo_driver
run_colcon_tests lerobot_cpp
run_colcon_tests hiwonder_lerobot_cpp
run_colcon_tests lerobot_ros2_control
run_colcon_tests lerobot_teleop
run_colcon_tests lerobot_control

echo
echo -e "${BOLD}${GREEN}✓ All unit checks passed${RESET}"
