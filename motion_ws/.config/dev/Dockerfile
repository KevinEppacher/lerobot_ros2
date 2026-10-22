ARG ROS_DISTRO=jazzy

FROM ros:${ROS_DISTRO}

ARG USERNAME=ubuntu
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN if ! id -u $USER_UID >/dev/null 2>&1; then \
        groupadd --gid $USER_GID $USERNAME && \
        useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME; \
    fi

RUN apt-get update && \
    apt-get install -y sudo && \
    echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME

RUN sudo apt update && sudo apt upgrade -y

########################################################
# Custom installations
########################################################

RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-desktop

# Install python3-pip for installing Python packages with pip
RUN sudo apt update && \
    sudo apt upgrade -y && \
    sudo apt install -y python3-pip

# We do not care about breaking system packages in this container
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install python packages from requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Install ros ament lint packages
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-ament-lint

RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-ros2-control

# Install ROS packages for working with robot models and visualization
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-xacro \
    ros-${ROS_DISTRO}-joint-state-publisher \
    ros-${ROS_DISTRO}-joint-state-publisher-gui \
    ros-${ROS_DISTRO}-robot-state-publisher \
    ros-${ROS_DISTRO}-tf2-tools \
    ros-${ROS_DISTRO}-rqt-tf-tree \
    ros-${ROS_DISTRO}-tf-transformations \
    ros-${ROS_DISTRO}-rqt \
    ros-${ROS_DISTRO}-rqt-common-plugins \
    ros-${ROS_DISTRO}-urdf \
    ros-${ROS_DISTRO}-joint-state-broadcaster \
    ros-${ROS_DISTRO}-forward-command-controller

RUN sudo apt update && sudo apt install -y \
    libyaml-cpp-dev

# Install utils (plotjuggler, foxglove bridge)
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-plotjuggler-ros \
    ros-${ROS_DISTRO}-foxglove-bridge

# Install DDS middleware
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    ros-${ROS_DISTRO}-rmw-fastrtps-cpp

# Install MoveIt packages for motion planning and manipulation
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-moveit \
    ros-${ROS_DISTRO}-moveit-ros-planning \
    ros-${ROS_DISTRO}-moveit-ros-planning-interface \
    ros-${ROS_DISTRO}-moveit-ros-move-group \
    ros-${ROS_DISTRO}-moveit-configs-utils

########################################################
# End Custom installations
########################################################

# Use Cyclone DDS as the default ROS 2 middleware
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
RUN echo "source install/setup.bash" >> ~/.bashrc
RUN echo "cd /app && source .bash_aliases" >> ~/.bashrc

WORKDIR /app
