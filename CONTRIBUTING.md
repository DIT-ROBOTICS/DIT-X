# Contributing

The same rules apply to the shell repo (`DIT-X`) and to every domain repo
(`eurobot-<domain>`). CI enforces most of them; this page explains why.

## Branches

```
feat/<topic>, fix/<topic>  ──PR──▶  develop  ──release PR──▶  main  ──tag vX.Y.Z
```

- Work on a short-lived branch from `develop`: `feat/ekf-camera`, `fix/startup-timeout`.
- Open a PR into `develop`. It merges when **CI is green and one reviewer approved**
  (code owners for `base/`, `tools/`, `docker/`). We **squash merge**, so the PR title
  becomes the commit on `develop`.
- `develop` is what test robots build their images from (`:develop`). Releasing = PR
  `develop → main` (robots build `:stable` from it), then tag `vX.Y.Z` on `main` with the
  CHANGELOG section moved from *Unreleased* to the new version.
- `develop` and `main` are protected: no direct pushes, no force pushes.

## Commit messages and PR titles

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`

| type | for |
|---|---|
| `feat` | new behaviour |
| `fix` | bug fix |
| `perf` / `refactor` | faster / restructured, same behaviour |
| `test` / `docs` | tests / documentation only |
| `build` / `ci` | images, dependencies / pipelines |
| `chore` / `revert` | housekeeping / revert a commit |

Scope = domain or area (`localization`, `base`, `tools`, ...). Add `!` for breaking
changes (`feat(base)!: rename pose topic`). Set up once:

```bash
git config commit.template .gitmessage
pre-commit install && pre-commit install --hook-type commit-msg
```

Why bother: commit messages, PR descriptions and the CHANGELOG are the context we (and
AI tools that summarise robot logs against commits) use to find *which change* broke
something. "update" and "fix bug" make that impossible.

## No edits on the robot

Never edit or build source on a robot. The robot runs a stable image; you test changes
by pushing **build output only**:

```bash
ditx build -d localization                  # on your laptop, in the dev container
ditx deploy -d localization -r white        # overlay: who/when/commit recorded, auto rollback
ditx rollback -d localization -r white      # back to the stable image
```

A reboot drops non-persistent overlays, so the robot always comes back clean. If a
change works, it goes through a PR; nothing lives only on a robot.

## AI-assisted code

Using AI tools is fine and encouraged. The rules:

1. CI guards apply to everyone equally: `ditx lint`, unit tests, the integration test and
   the contract check must pass. They are the baseline that keeps a repo consistent.
2. You must be able to explain every line you submit. Reviewers will ask.
3. No drive-by refactors of other domains or of `base/` inside a feature PR.
4. Mention in the PR description what was generated and how you verified it.

## Changing interfaces (`base/`)

Messages, services and `contract.yaml` live in the shell repo, so all domains build
against one definition.

1. Open a PR in `DIT-X` that changes `base/eurobot_interfaces` and/or
   `base/eurobot_common/contract.yaml`; tag the owners of affected domains.
2. Prefer **adding** a topic/field over changing one; renames are breaking (`!`).
3. While developing: `ditx build --base -d <domains>` builds against your local base.
4. After merge, rebuild the images (`ditx image` on laptops, tutorial 14 step 3 on robots);
   a robot accepts overlays built on the new base only once its image has that base.

## Checklist before opening a PR

- [ ] `ditx lint` clean (or `ditx lint --fix`)
- [ ] `ditx test` and, if you touched topics, `ditx test --integration`
- [ ] tried on the sim robot (`ditx deploy -d <domain> -r sim`) or a real robot
- [ ] CHANGELOG.md updated under *Unreleased* for user-visible changes
