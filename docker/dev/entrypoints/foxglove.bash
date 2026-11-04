echo "Sourcing ROS 2..."
source /opt/ros/jazzy/setup.bash

cd /workspace
rm -rf build/ install/ log/
colcon build --symlink-install

echo "Sourcing Baubot workspace..."
source /workspace/install/setup.bash

echo "Starting Foxglove Bridge..."
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765
