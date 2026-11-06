# Calibration files

Each calibration YAML maps every joint declared in the ROS 2 Control
description to a servo and a raw position range:

```yaml
joint_1:
  servo_id: 1          # HiWonder servo ID, 0-253, unique per joint
  lower_position: 618  # raw position at the lower joint limit
  upper_position: 3363 # raw position at the upper joint limit
```

The hardware interface derives the motor list from this file in the order of
the `<joint>` entries of the ROS 2 Control description. Servo IDs are never
inferred from joint names, and the order of entries in the YAML is irrelevant.

For descriptions with prefixed control joint names, set the hardware parameter
`joint_prefix` to that exact prefix; the YAML keys remain unprefixed. Every
controlled joint must start with the configured prefix. If the parameter is
absent or empty, joint names are used unchanged. The SO-101 control macros
accept an optional `joint_prefix` argument, which defaults to empty: their
existing `prefix` argument affects links and the hardware name, not controlled
joint names. The supplied SO-101 control macros declare unprefixed joints, so
leave `joint_prefix` empty when using them unchanged.

## Example files

Example calibrations are provided per robot variant:

| File | Joints |
|---|---|
| `5dof/{leader,follower}_example_calibration.yaml` | `joint_1`-`joint_5`, `gripper` |
| `6dof/{leader,follower}_example_calibration.yaml` | `joint_1`-`joint_6`, `gripper` |

The bringup launch files select `config/<dof>dof/<robot_type>_example_calibration.yaml`
from the `dof` argument. A calibration must always match the selected robot;
create your own with `lerobot-calibrate --dof <5|6>`.
