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

RUN sudo apt-get update && sudo apt-get upgrade -y

########################################################
# Custom installations
########################################################

RUN sudo apt-get update && sudo apt-get install -y \
    ros-${ROS_DISTRO}-desktop \
    python3-pip \
    ros-${ROS_DISTRO}-ament-lint

ENV PIP_BREAK_SYSTEM_PACKAGES=1

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Install DDS middleware
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    ros-${ROS_DISTRO}-rmw-fastrtps-cpp

RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-usb-cam

# Image tools for viewing compressed image topics
RUN sudo apt update && sudo apt install -y \
    ros-${ROS_DISTRO}-image-view

########################################################
# End Custom installations
########################################################

# Use Cyclone DDS as the default ROS 2 middleware
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
RUN echo "source install/setup.bash" >> ~/.bashrc
RUN echo "cd /app && source .bash_aliases" >> ~/.bashrc

WORKDIR /app
