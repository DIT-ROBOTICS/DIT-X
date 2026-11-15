# Changelog

All notable changes to this workspace are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/)
(tags `vX.Y.Z` on `main`; the release workflow publishes the matching section below).

## [Unreleased]

### Added
- Shell repo + domain repos layout (`ditx.repos`, `ditx sync`), replacing one copied repo per year.
- `ditx` CLI and TUI: build, test, lint, index, deploy, rollback, overlays, logs, image, sync, status, doctor.
- Layered images: `eurobot-base` (ROS + shared interfaces), `eurobot-dev`, one runtime image per domain.
- Overlay deploys: only build output goes to the robot, with a manifest (who, when, commit);
  verification with automatic rollback; reboot falls back to the stable image.
- Interface contract `contract.yaml` (topics, types, QoS, owners) with generated C++/Python constants
  and a live-graph checker.
- Startup handshake (`ReadySignal`) and module heartbeats shared by all domains.
- CI on GitHub Actions and GitLab CI (lint → build → test → image), reusable domain pipelines.
- Unified logging: one file per container start, retention (7 days / 100 GB), NAS sync, system log export.

<!--
Template for a release (move Unreleased entries here, then tag):

## [1.2.0] - 2027-03-01
### Added
### Changed
### Fixed
### Removed
-->
