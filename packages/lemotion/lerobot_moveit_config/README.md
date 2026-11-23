# lerobot_moveit_config

## Overview

This package configures MoveIt 2 for the stock 5-DOF and 6-DOF SO-101 models
from [`so101_description`](../../lemodel/so101_description/README.md).
Both models use the follower gripper geometry.

## Usage

From a sourced ROS 2 Jazzy workspace, start `move_group` and RViz:

```bash
ros2 launch lerobot_moveit_config moveit.launch.py dof:=5 namespace:=follower
```

Use `dof:=6` for the 6-DOF model or `gui:=false` to skip RViz. Match the DOF
and namespace of the running robot bringup. The namespace must be a single
nonempty segment. With RViz enabled, the bundled configuration expects
follower-specific planning-scene and trajectory display topics. Adjust those
topics if you use another namespace.

For planning from the current robot state and live visualization, provide
joint states and TF for the selected model. The MoveIt launch starts neither
the robot state publishers nor the hardware controllers. This package
provides no simulator or mock hardware launch.

## Configuration

- The [5-DOF SRDF](config/5dof/so101.srdf) and
  [6-DOF SRDF](config/6dof/so101.srdf) define the `manipulator` chain from
  `base_link` to `tcp`, a separate `gripper` group, named arm poses, and
  self-collision exclusions.
- Both variants use KDL for the arm. The
  [5-DOF settings](config/5dof/kinematics.yaml) enable position-only inverse
  kinematics. See the [6-DOF settings](config/6dof/kinematics.yaml) for the
  six-joint solver configuration.
- [OMPL](config/common/ompl_planning.yaml) uses `RRTConnect` for both groups.
  The [joint limits file](config/common/joint_limits.yaml) supplies planning
  acceleration limits and scaling defaults.

## Integration

For hardware execution, use
[`lerobot_bringup`](../../lebringup/lerobot_bringup/README.md) with the same
DOF and namespace. Bringup starts the
[`lerobot_ros2_control` hardware adapter](../lerobot_ros2_control/) through
the ROS 2 controller manager and loads the manipulator and gripper trajectory
controllers inactive.

The [MoveIt controller configuration](config/common/moveit_controllers.yaml)
selects `Ros2ControlManager` to discover and manage controllers in that
namespace. Both the arm and gripper use `FollowJointTrajectory` actions.
Execution requires current joint feedback and controllers that can activate
with the required joint interfaces. See the
[bringup controller configuration](../../lebringup/lerobot_bringup/config/).
