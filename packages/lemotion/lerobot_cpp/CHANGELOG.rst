^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package lerobot_cpp
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Forthcoming
-----------

Changes since the first unofficial project version, ``v0.1.0``.

* Breaking: use signed 16-bit values in raw position read and write vectors.
* Breaking: require ``validatePositions()`` for raw target validation.
* Breaking: require ``readStates()`` and add ``JointState`` for raw position,
  velocity, and current feedback.
* Breaking: add ordered motor IDs to ``RobotConfig``, changing its layout and
  making motor count configuration-driven.

Update backend implementations and rebuild providers and consumers together.
