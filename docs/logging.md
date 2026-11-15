# Logging and observability

Last season's final-match localization failure could not be explained because nothing was
recorded. The rules below make every run diagnosable afterwards, by a person or an AI agent.

## One format, one place

| What | Where on the robot | Written by |
|---|---|---|
| Container output (stdout/stderr, all ROS logs) | `/home/share/eurobot/logs/<container>/<container>_<start time>.log` | `docker/entrypoint.sh` |
| ROS per-node log files | `/home/share/eurobot/logs/<container>/ros/` | rcl (`ROS_LOG_DIR`) |
| System journal, kernel (USB resets, OOM, network) | `/home/share/eurobot/logs/system/{journal,kernel}_<date>.log` | `eurobot-syslog-export.timer` |
| Live metrics (CPU, RAM, disk, net, per container) | netdata on `http://<robot>:19999` | compose profile `monitoring` |

* Every ROS line has the same shape (`RCUTILS_CONSOLE_OUTPUT_FORMAT` in the image):
  `[INFO] [1731500000.123456789] [localization.fusion]: message`.
* Every container's first lines name the image, and the overlay with its full manifest
  (who, when, git sha). A log file therefore always says which code produced it.

## Retention and sync

* `eurobot-log-retention.timer`: delete logs older than 7 days, then the oldest until the folder is
  under 100 GB (`/home/share/eurobot/config/logging.env`).
* `eurobot-log-sync.timer`: nightly `rsync` to the lab NAS (`NAS_TARGET`). If it is unset or
  unreachable (e.g. at the competition), it skips quietly and catches up later.
* `ditx logs -r white --fetch` copies a robot's whole log folder to `./logs/white/` for analysis.

## Clocks

* **Durations, timeouts, rates → steady clock** (`std::chrono::steady_clock`,
  `time.monotonic()`, ROS timers created with `create_wall_timer`). It never jumps, even when
  NTP/chrony corrects the system time. A jump in the system clock has crashed containers before.
* **Stamps and log lines → system time** (ROS time), synced with chrony between all machines
  (robots, central beacon, SIMAs). Only then can stamps from two machines be subtracted.
* Latency of a message = `now() - header.stamp`. Use `eurobot_common::stamp_age_ms()`, which
  localization_fusion uses to report the age of vision data in its heartbeat. Measure the latency budget
  before designing around it. For example: how stale can a camera pose be before fusion makes things
  worse?

## Health

* Every module publishes `/robot/system/heartbeat` (1 Hz, level OK/WARN/ERROR + detail) through
  `StartupReporter`. `main_startup` warns when a module's heartbeat goes stale.
* `ditx contract live -r white` compares the running graph with the contract.

## Next steps (left for the team)

* A daily job that summarizes the synced logs together with the overlay manifests and commits.
  It should say what got slower or started restarting, and which overlay/commit was running at that time.
* Ship `ros2 bag` (MCAP) recordings for selected topics during matches. Logs come first, bags second.
