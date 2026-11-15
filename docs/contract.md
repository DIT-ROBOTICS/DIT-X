# Interface contract

> Generated from `base/eurobot_common/contract.yaml` by `ditx contract md`. Do not edit.

## QoS profiles

| profile | reliability | durability | history | depth |
|---|---|---|---|---|
| `sensor` | best_effort | volatile | keep_last | 1 |
| `state` | reliable | transient_local | keep_last | 1 |
| `command` | reliable | volatile | keep_last | 10 |

## Topics

| name | type | QoS | publisher | subscribers | rate | description |
|---|---|---|---|---|---|---|
| `/robot/startup/status` | `eurobot_interfaces/msg/StartupStatus` | state | main | * |  | Which domains have reported ready; all_ready gates the match start. |
| `/robot/system/heartbeat` | `eurobot_interfaces/msg/ModuleHeartbeat` | sensor | * | main | 1 | One message per module per second; missing heartbeats mean a dead module. |
| `/robot/localization/pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | sensor | localization | navigation, main | 50 | Fused robot pose in the map frame. header.stamp = time of the newest fused measurement. |
| `/robot/vision/rival_poses` | `geometry_msgs/msg/PoseArray` | sensor | vision | localization, navigation, main | 15 | Detected opponent robots in the map frame. |
| `/robot/navigation/goal` | `geometry_msgs/msg/PoseStamped` | command | main | navigation |  | Where main wants the robot to go next. |
| `/robot/navigation/status` | `std_msgs/msg/String` | state | navigation | main |  | One of: idle, moving, arrived, blocked. |

## Services

| name | type | server | clients | description |
|---|---|---|---|---|
| `/robot/startup/ready_signal` | `eurobot_interfaces/srv/ReadySignal` | main | * | Startup handshake; each module calls it once it is ready. |
