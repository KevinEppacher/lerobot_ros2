^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package lerobot_ros2_control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Forthcoming
-----------

Changes since the first unofficial project version, ``v0.1.0``.

* **Breaking:** Use signed raw positions and require backend validation of
  converted targets before writing them.
* **Breaking:** Require position, velocity, and current state interfaces in
  that order, and consume feedback through the backend's ``readStates()`` method.
* **Breaking for older calibrations:** Require a unique ``servo_id`` per
  controlled joint and pass IDs to the backend in joint order. Support
  calibration lookup for prefixed joint names.
