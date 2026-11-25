# opennav_docking_msgs

The docking actions of [opennav_docking](https://github.com/open-navigation/opennav_docking)
(`DockRobot`, `UndockRobot`, `ReloadDatabase`). Navigation serves them (its vendored
`opennav_docking` in `Eurobot-Template-Navigation`), main calls `DockRobot`, so the definition
lives here in the base like every other cross-domain type: one copy, built once.

Upstream name kept on purpose: the action type name (`opennav_docking_msgs/action/DockRobot`) is
part of what both sides match on, and the vendored Nav2 / opennav_docking code includes these
headers by that name.

## Where it came from

Copied from `Eurobot-Template-Navigation` `src/third_party/opennav_docking/opennav_docking_msgs`
(= `Eurobot-2026-Navigation2` `develop` bb0ab0c, upstream `package.xml` version 0.0.2).

DIT changes on top of upstream (2026; compared with upstream `main` on 2026-11-25, which has
901–906 and 999):

- `DockRobot` result error codes `STOP_ROBOT=900` and `BLOCK_BY_RIVAL=907`.

DIT-X changes:

- `package.xml` lists only what the interfaces use (upstream also depended on rclcpp,
  rclcpp_action, rclcpp_lifecycle, nav2_util, nav2_msgs and tf2_ros); it adds `std_msgs` and
  `action_msgs`, which `CMakeLists.txt` already used.

2026 main kept its own copy in `src/Interface/opennav_docking_msgs`, which had already drifted:
it lacked `STOP_ROBOT=900`. Constants do not change the wire format, so 2026 still worked, but
that is exactly the drift a single copy in the base prevents.
