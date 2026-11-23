# lerobot_vision_bringup

## Overview

This package launches USB cameras through `usb_cam` and provides
`lerobot-list-cameras` to identify Linux V4L2 interfaces.

## Usage

In a sourced workspace with `v4l2-ctl` from `v4l-utils` available, list the
camera interfaces or filter for RGB:

```bash
lerobot-list-cameras
lerobot-list-cameras rgb
```

The tool groups interfaces by physical device where possible and reports
their types, pixel formats, and matching `/dev/v4l/by-path/` symlinks. Use
`rgbd` for depth or IR and `meta` for metadata. A single camera can expose
multiple interfaces, so select the one that supports your capture settings.

Prefer a `/dev/v4l/by-path/` path over `/dev/videoN`, whose number can change
after reconnection or reboot. The path follows the physical USB connection
and can change if you move the camera. A `/dev/v4l/by-id/` link, when
available, can identify the device independently of its port. The discovery
tool reports `by-path` links.

Set `wrist_device` to the chosen device path, then launch the wrist camera:

```bash
ros2 launch lerobot_vision_bringup camera_bringup.launch.py video_device:="$wrist_device"
```

To run a second camera, set `front_device` to its device path and launch it
in a separate terminal:

```bash
ros2 launch lerobot_vision_bringup camera_bringup.launch.py \
  camera_name:=front_camera config_file:=follower_front_camera.yaml \
  video_device:="$front_device"
```

## Configuration

[`camera_bringup.launch.py`](launch/camera_bringup.launch.py) starts
`usb_cam_node_exe` as `camera`. The launch arguments `namespace` and
`camera_name` form the camera namespace. Their defaults produce the node
`/follower/wrist_camera/camera` and the topics
`/follower/wrist_camera/image_raw` and `/follower/wrist_camera/camera_info`.
The front example uses `/follower/front_camera` instead. The launch defaults
to the wrist preset and `/dev/video0` when no device is supplied.

Select the [wrist preset](config/follower_wrist_camera.yaml) or
[front preset](config/follower_front_camera.yaml) with `config_file`.
The launch resolves this filename under the installed package's `config/`
directory. Add custom presets there through the package install. Check that
the selected device supports the preset's dimensions, frame rate, and format.

In YAML, `camera_name` identifies the camera for calibration and `frame_id`
labels its messages. Use distinct namespaces, devices, and frame IDs for
separate cameras. Provide the corresponding transforms separately if consumers
need camera TF.

## Docker deployment

The [wrist and front services](../../../docker/deploy/compose.yaml) use
`FOLLOWER_WRIST_VIDEO_DEVICE` and `FOLLOWER_FRONT_VIDEO_DEVICE` to pass the
selected host devices to their respective containers. Each container sees
its assigned camera as `/dev/video0` and loads the preset installed in the
image. See the [repository usage guide](../../../docs/usage.md) for device
discovery and deployment setup.
