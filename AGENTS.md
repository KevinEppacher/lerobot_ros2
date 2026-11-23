# Agent Instructions

## Project

LeRobot ROS2 is a ROS 2 Jazzy framework for SO-101 robotic arms, including hardware drivers, `ros2_control`, MoveIt 2, teleoperation, vision, and Docker-based deployment.

## Guidelines

Before making changes, read and follow the relevant guidelines:

- [General Guidelines](docs/agent-guidelines/general.md)
- [ROS 2 Guidelines](docs/agent-guidelines/ros2.md)
- [Documentation Guidelines](docs/agent-guidelines/documentation.md)

These guidelines apply to all packages unless more specific instructions exist.

## Core Principles

- Follow established standards and conventions before introducing custom ones.
- Prefer simple, readable, and maintainable solutions.
- Minimize code, duplication, and unnecessary abstraction.
- Keep documentation concise, structured, and technically accurate.
- Prefer Mermaid diagrams over lengthy explanations when visualizing complex behavior.
- Preserve existing functionality and public interfaces unless changes are explicitly requested.
- Never invent implementation details, interfaces, or configuration values.

## Workflow

1. Inspect the relevant implementation and existing conventions.
2. Identify the smallest change that satisfies the request.
3. Modify only files within the requested scope.
4. Run relevant checks and tests when possible.
5. Review the changes for correctness and unnecessary complexity.
6. Summarize the changes and report any unverified assumptions.

Do not create commits unless explicitly requested.
