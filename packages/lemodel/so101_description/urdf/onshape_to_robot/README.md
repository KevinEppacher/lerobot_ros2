# Export SO-101 assemblies from Onshape

The 5-DOF arm, 6-DOF arm, and gripper are maintained in a live Onshape workspace.
Each export configuration points to its own assembly tab. The checked-in URDF
and STL files are reference snapshots. The CAD revision and exporter version
are unpinned, so a fresh export can differ from those snapshots.

## Set up the exporter

Install `onshape-to-robot` in a Python environment with `pip`. Use an Onshape
API key and secret with access to the workspace. Set `ONSHAPE_API`,
`ONSHAPE_ACCESS_KEY`, and `ONSHAPE_SECRET_KEY` in the terminal that runs the
exporter. See the [exporter's authentication guide](https://onshape-to-robot.readthedocs.io/en/stable/getting_started.html).

```bash
python -m pip install onshape-to-robot
export ONSHAPE_API=https://cad.onshape.com
export ONSHAPE_ACCESS_KEY='your-access-key'
export ONSHAPE_SECRET_KEY='your-secret-key'
```

## Export and compare

Run these commands from this directory. They copy the configs into a temporary
directory so the checked-in snapshots are available for comparison.

```bash
export_dir=$(mktemp -d)
for assembly in 5dof 6dof gripper; do
  mkdir "$export_dir/$assembly"
  cp "$assembly/config.json" "$export_dir/$assembly/"
  onshape-to-robot "$export_dir/$assembly"
done
```

| Assembly config | Generated files in its export directory |
| --- | --- |
| [5-DOF arm](5dof/config.json) | `so101.urdf` and `assets/*.stl` |
| [6-DOF arm](6dof/config.json) | `so101.urdf` and `assets/*.stl` |
| [Gripper](gripper/config.json) | `gripper.urdf` and `assets/*.stl` |

Compare each URDF with its checked-in counterpart. Compare each `assets/`
directory for added, removed, or changed meshes. For example, for the 5-DOF arm:

```bash
diff -u 5dof/so101.urdf "$export_dir/5dof/so101.urdf"
diff -qr 5dof/assets "$export_dir/5dof/assets"
```

Repeat for `6dof/so101.urdf` and `gripper/gripper.urdf` and their asset
directories. Review the export diff alongside the maintained Xacros before
carrying changes into the runtime model.

## Integrate changes into Xacro

1. Use the export to identify changed links, joints, and meshes. Update the
   relevant [link macros](../links/) and [joint macros](../joints/). The two
   arm variants share the base and first two links, so review changes to those
   macros against both models.
2. Keep the runtime link and joint names, frame prefixes, and shared materials
   consistent. Put selected STL assets under [`meshes/visual/`](../../meshes/visual/)
   and use `package://so101_description/meshes/visual/…` references in the
   visual and collision geometry. Preserve intentional differences such as the
   shared flange mesh. The files under `meshes/cad/` are separate STEP resources.
3. Preserve intentional adjustments to transforms, mass, center of mass,
   inertia, and joint limits. The installed model also adds the fixed `tcp`
   frame at the end of each arm. Some runtime inertials and the 6-DOF terminal
   joint limits differ from the exports. Use the maintained Xacros as the
   reference for these adjustments.
4. Integrate changes to the exported wrist and moving jaw in the
   [follower gripper macro](../links/gripper/follower/gripper_link.xacro).
   Preserve the `gripper` joint name and fixed attachment to `tcp` in both
   [stock robot descriptions](../robots/). The leader gripper macro is an
   intentional placeholder.

## Validate the integrated model

- Expand both stock robot Xacros in a sourced Jazzy workspace and open each DOF
  variant using the [display launch](../../README.md#usage). Check joint motion,
  visual alignment, and the TCP and gripper mount transforms.
- Review joint axes and limits, including agreement with the
  [ROS 2 control macros](../control/). Confirm that each controlled joint exists
  in the expanded model.
- Review link masses, centers of mass, and inertia tensors for unintended
  changes. Check that visual and collision mesh paths resolve to the intended
  package assets.
- Verify that the gripper jaw moves about the expected axis and that the
  `gripper` joint remains in the matching control and calibration configuration.
