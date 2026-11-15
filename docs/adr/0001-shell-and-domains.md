# 0001. Shell repo + domain repos, layered images, overlays for development

* Status: accepted
* Date: 2026-11-13

## Context

In 2026 every subsystem repo had its own Dockerfile, compose file, copy of the shared
interfaces (`btcpp_ros2_interfaces` ×5, Nav2 source ×3), and its own way to pick a robot (by
`ROS_DOMAIN_ID`, by git branch). The interface contract existed only implicitly and was
already broken in several places (type mismatches on `/robot/on_take`, `final_pose`,
`initial_pose`; a plan topic name mismatch). Code was edited and built directly on the robots,
so nobody knew exactly what was running, and there were no logs to find out afterwards.

## Decision

1. One **shell repo** owns tooling (`ditx`), CI, images, the shared interfaces and the
   contract. Team code lives in **domain repos** listed in `ditx.repos` (vcstool format).
2. Images are layered: `eurobot-base` → `eurobot-<domain>`. Robots only run images.
3. Development builds are pushed as **overlays** (build output + manifest), and they disappear on
   reboot unless persisted. Releases come only from CI.
4. Cross-domain communication goes through `contract.yaml` with named QoS profiles. CI
   checks it statically (lint) and at runtime (integration test).

## Alternatives

| Option | Why not |
|---|---|
| One monorepo | Simplest, but every team's history and CI in one place; access per team is harder. Still a valid fallback: put the domains in `domains/` directly and drop `ditx sync`. |
| Keep per-team repos with own docker | The 2026 situation: drift, duplicated interfaces, no shared CI. |
| Build on the robot | Fast to hack, but no clean baseline, no record of what runs, and ARM boards compile slowly. |

## Consequences

* Changing an interface is a deliberate PR to the shell that needs a new base image.
* Teams depend on the shell's tooling. When `ditx` is wrong, everyone is blocked, so the shell
  has tests (`tools/tests`) and its own CI.
* Students must learn layering once. The TUI (`ditx`) shows the exact command for every action.
