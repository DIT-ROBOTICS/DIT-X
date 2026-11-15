<!-- Title: Conventional Commits, e.g. "feat(localization): fuse camera pose". It becomes the squash commit (MR title). -->

## What / Why

<!-- What changes, and the problem it solves. Link the issue: Closes #123 -->

## How it was tested

- [ ] `ditx test` (unit) passes
- [ ] `ditx test --integration` passes (all domains + contract check)
- [ ] Ran on the sim robot: `ditx deploy -d <domain> -r sim`
- [ ] Ran on a real robot: `ditx deploy -d <domain> -r <robot>`, overlay id: `...`

<!-- Paste the relevant output, plots or log excerpts (path under /home/share/eurobot/logs/...). -->

## Interfaces changed?

- [ ] No
- [ ] Yes: `contract.yaml` / `.msg` / `.srv` changed. The base fingerprint changes, so every
      domain must be rebuilt and robots need the new base image (`develop`/`stable`) before
      overlays built on it can run. Owners of affected domains are tagged below.

## Risk / rollback

<!-- What could break on the robot? Rollback is `ditx rollback -d <domain> -r <robot>`; anything else needed? -->

## Checklist

- [ ] `ditx lint` is clean
- [ ] CHANGELOG.md updated under **Unreleased** (if user-visible)
- [ ] Docs / README updated (if behaviour or usage changed)
- [ ] I can explain every line of this diff, including AI-generated parts
