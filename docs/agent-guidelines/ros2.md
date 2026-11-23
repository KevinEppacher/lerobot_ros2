# ROS 2 Development Guidelines

## Standards

Follow ROS 2 Jazzy conventions and applicable ROS Enhancement Proposals (REPs).

Relevant standards include:

- REP-103: Standard units and coordinate conventions.
- REP-105: Coordinate frames for mobile platforms, where applicable.
- REP-140: Package manifest conventions.
- REP-2004: ROS 2 package quality guidelines.

Use official ROS 2 documentation as the primary reference.

## Packages

- Follow standard `ament_cmake` and `ament_python` conventions.
- Follow REP-140 and the ROS 2 package manifest specification.
- Keep package responsibilities clearly separated.
- Prefer existing ROS 2 packages and interfaces over custom implementations.
- Use standard ROS 2 naming conventions.
- Keep `package.xml` consistent with the actual implementation and build configuration.

## Package Validation

When analyzing or documenting a ROS 2 package, validate its `package.xml` against the implementation and ROS 2 conventions.

Verify:

- Package name, version, description, maintainer, and license.
- Correct package format and build type.
- Required build, execution, and test dependencies.
- Dependency declarations against actual source code, launch files, and configuration.
- Consistency between `package.xml`, `CMakeLists.txt` or Python packaging files.
- Compatibility with ROS 2 Jazzy.
- Release readiness, including dependency availability through `rosdep`.

Prefer the most appropriate dependency declarations (`build_depend`, `exec_depend`, `test_depend`, or `depend`).

Report missing, unnecessary, or incorrect dependencies.

Do not modify package manifests or build configurations during documentation-only tasks without approval.

## Nodes and Interfaces

- Use namespaces and relative topic names where appropriate.
- Avoid hardcoded absolute names unless explicitly required.
- Use standard ROS 2 message, service, and action types when suitable.
- Document public interfaces and their expected behavior.
- Expose configurable behavior through ROS 2 parameters.
- Validate parameters and handle invalid configurations.
- Use lifecycle nodes only when their lifecycle semantics are needed.

## Robot Control

- Follow `ros2_control` conventions for hardware interfaces and controllers.
- Keep hardware communication separate from application-level control logic.
- Avoid conflicting command interfaces.
- Define controller activation and switching behavior explicitly.
- Use standard trajectory interfaces for planned motion.

## Robot Description

- Follow REP-103 for units and coordinate conventions.
- Use consistent joint and frame naming.
- Keep URDF/Xacro descriptions modular.
- Define physically meaningful joint limits and inertial properties.
- Avoid duplicating robot configuration values.

## Launch and Configuration

- Prefer reusable ROS 2 launch files.
- Expose configurable values through launch arguments and parameters.
- Store nontrivial configuration in YAML files.
- Avoid hardcoded device paths and machine-specific settings.
- Support namespace-aware deployment.

## Testing

- Use `ament` testing infrastructure.
- Prefer unit tests for isolated logic.
- Use integration tests for ROS 2 communication and controller behavior.
- Keep hardware-dependent tests separate from hardware-independent tests.
