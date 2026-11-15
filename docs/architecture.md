# Architecture

## One shell, many domains

```mermaid
flowchart LR
  subgraph shell["eurobot shell repo · leads / infra"]
    direction TB
    tools("<b>bin/ditx + TUI</b><br/><small>one entry point</small>")
    base("<b>base/</b><br/><small>eurobot_interfaces (msgs/srvs)<br/>eurobot_common (contract.yaml)</small>")
    docker("<b>docker/</b><br/><small>Dockerfile · bake · compose</small>")
    ci("<b>CI/CD</b><br/><small>.github · .gitlab-ci.yml</small>")
    repos("<b>ditx.repos</b><br/><small>config/robots.ini</small>")
  end
  domains("<b>domains/</b><br/><small>one repo + one container per team</small><br/><br/>Eurobot-Main<br/>Eurobot-Navigation<br/>Eurobot-Localization<br/>Eurobot-Vision")
  repos -- "ditx sync" --> domains
  base -. "the only shared<br/>dependency" .-> domains
```

| Concept | Where | Rule |
|---|---|---|
| **Shell** | this repo | Tooling, CI, images, interfaces, which domains exist. Changes here affect everyone, so they need a lead's review (CODEOWNERS). |
| **Domain** | `eurobot-<domain>` repo → `domains/<domain>` | One team, one container on the robot, one colcon workspace. Packages are named `<domain>_*`. |
| **Module** | a ROS package inside a domain | Anything the team wants. Each one reports to the startup handshake. |
| **Contract** | `base/eurobot_common/contract.yaml` | Every topic and service that crosses a domain boundary, with its type and QoS. Code uses generated constants; it never spells the name. |

Domains **never depend on each other's packages** (`ditx lint` enforces this).
They talk only through the contract. Each team can therefore build, test and deploy alone,
and a contract change is a reviewed PR to the shell instead of a Notion table that drifts.

## Layers: build once, overlay only what you change

```mermaid
flowchart TB
  overlay("<b>overlay</b> · ditx deploy, your build output<br/><small>optional · per domain · removable</small>")
  image("<b>eurobot-#lt;domain#gt; image</b> · stable build<br/><small>built by CI from develop / main</small>")
  base("<b>eurobot-base</b> · ROS + shared interfaces<br/><small>built by CI · shared by every domain</small>")
  overlay -- "sourced on top of" --> image
  image -- "FROM" --> base
  classDef optional stroke-dasharray: 5 4
  class overlay optional
```

* **Every** container, on every robot and every laptop, starts from the same `eurobot-base`.
  Because the interfaces are compiled once, two teams can't each compile a different
  version of a message.
* Each layer has **its own install space** (`build/<distro>-<arch>/<layer>/install`), and they are
  sourced in order. You rebuild only your layer, incrementally. A "delete install/ and rebuild
  everything" moment means you crossed a boundary, i.e. you changed the base. Then build it
  explicitly with `ditx build --base` and get a new base image through CI.
* The base carries a **fingerprint** of all interface definitions. An overlay records the
  fingerprint it was built against, and a robot refuses an overlay whose fingerprint does not
  match its image. You get a clear message instead of a mysterious crash mid-match.

## The robot runs images, never source

```mermaid
sequenceDiagram
  participant Dev as laptop (ditx)
  participant R as robot
  Dev->>Dev: ditx build -d localization<br/>(dev container, incremental)
  Dev->>R: tar of install/ + manifest.json<br/>(who, when, git sha, fingerprint)
  R->>R: run/active/localization<br/>= #lt;overlay id#gt;
  R->>R: recreate container:<br/>entrypoint sources image + overlay
  Dev->>R: verify<br/>(container up, overlay active for 6 s)
  alt failed
    Dev->>R: rollback to previous<br/>overlay / stable image
  end
  Note over R: reboot → run/ is emptied → stable image<br/>(unless deployed with --persist)
```

* There is no compiler on the robot and nobody edits code there. What runs is always
  *image tag + overlay id*, and `ditx overlays -r white` shows who pushed which commit and when.
* Every container logs its overlay manifest on start, so the logs show exactly which code
  produced them.
* Same code for every robot: robot differences live in `config/robots.ini` (what runs, domain
  id, arch) and `<domain>_bringup/config/robots/<robot>.yaml` (parameters). A robot is never a
  git branch.

## CI/CD

```mermaid
flowchart TB
  pr("<b>PR → develop</b>") --> lint("<b>lint</b><br/><small>format · ruff · shellcheck<br/>contract · boundaries</small>")
  lint --> build("<b>build</b><br/><small>all domains</small>") --> test("<b>test</b><br/><small>unit + integration</small>")
  test -- "merge" --> done("<b>develop / main</b><br/><small>verified only: laptops and robots<br/>build their own images</small>")
```

* The pipelines only call `ditx ci <stage>`. **Whatever passes locally passes in CI**, and a
  red CI job can be reproduced with the same command.
* Domain repos run the same stages through a reusable workflow, with the other domains
  synced at `develop`. A localization PR is therefore tested *together with* navigation, main and vision.
* Lint runs before human review and is the baseline that AI-written code must also meet:
  formatting, lint, the interface contract and domain boundaries.

## Where things are decided (ADRs)

Decisions that are expensive to undo get a short record in `docs/adr/`. Start with
[0001](adr/0001-shell-and-domains.md).
