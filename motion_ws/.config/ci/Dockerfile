ARG ROS_DISTRO=jazzy

FROM ros:${ROS_DISTRO}-ros-core

########################################################
# Custom installations
########################################################

# Install python3-pip for installing Python packages with pip
RUN apt update && \
    apt upgrade -y && \
    apt install -y python3-pip

# We do not care about breaking system packages in this container
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install python packages from requirements.txt
COPY motion_ws/.config/ci/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Install ros ament lint packages
RUN apt update && apt install -y \
    ros-${ROS_DISTRO}-ament-lint

# Install colcon, since ros core does not come with it
RUN apt update && apt install -y \
    python3-colcon-common-extensions

RUN apt update && apt install -y \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp

# Install ROS packages for working with robot models and visualization
RUN apt update && apt install -y \
    ros-${ROS_DISTRO}-xacro \
    ros-${ROS_DISTRO}-joint-state-publisher \
    ros-${ROS_DISTRO}-robot-state-publisher \
    ros-${ROS_DISTRO}-tf2-tools \
    ros-${ROS_DISTRO}-tf-transformations \
    ros-${ROS_DISTRO}-urdf

# Install ROS 2 Control packages for robot control and simulation
RUN apt update && apt install -y \
    ros-${ROS_DISTRO}-ros2-control \
    ros-${ROS_DISTRO}-ros2-controllers \
    ros-${ROS_DISTRO}-joint-trajectory-controller \
    libyaml-cpp-dev

# Install MoveIt packages for motion planning and manipulation
RUN apt update && apt install -y \
    ros-${ROS_DISTRO}-moveit \
    ros-${ROS_DISTRO}-moveit-ros-planning \
    ros-${ROS_DISTRO}-moveit-ros-planning-interface \
    ros-${ROS_DISTRO}-moveit-ros-move-group \
    ros-${ROS_DISTRO}-moveit-configs-utils

########################################################
# End Custom installations
########################################################

RUN apt update && apt upgrade -y

# Source ROS setup
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
RUN echo "source install/setup.bash" >> ~/.bashrc

# Configure CycloneDDS as the default RMW implementation
RUN echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc

WORKDIR /app
