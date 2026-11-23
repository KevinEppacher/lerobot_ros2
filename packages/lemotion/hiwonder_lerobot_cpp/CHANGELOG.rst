^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package hiwonder_lerobot_cpp
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Forthcoming
-----------

Changes since the first unofficial project version, ``v0.1.0``.

* Replace the separate leader and follower plugins with
  ``hiwonder_lerobot_cpp/Robot`` and accept an ordered list of servo IDs.
* Add 5-DOF and 6-DOF selection to calibration and motion testing, and discover
  servo IDs in the torque tool.
* Add per-servo and all-servo targets in absolute or relative ticks to
  ``lerobot-test-move``. By default, send the measured positions as hold targets.
* Support signed position, velocity, and current feedback and reject
  out-of-range raw position targets before group writes.
