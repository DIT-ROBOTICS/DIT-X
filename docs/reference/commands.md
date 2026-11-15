# 指令總覽

本頁內容直接取自 `ditx help <指令>` 的輸出（英文部分為工具本身的說明文字）。你可以隨時在終端機中執行 `ditx help <指令>` 或 `ditx <指令> --help`，查看最新版本的說明。

## 全域選項

所有指令皆支援下列選項：

| 選項 | 說明 |
|---|---|
| `-n`, `--dry-run` | 僅列出將要執行的動作，不進行任何變更 |
| `-v`, `--verbose` | 顯示每個工具的完整輸出 |
| `-q`, `--quiet` | 僅輸出警告與錯誤 |
| `-h`, `--help` | 顯示說明 |
| `-V`, `--version` | 顯示版本（僅能置於最前面：`ditx -V`） |

以下各指令的說明省略上述共用選項。

```text
ditx (DIT-X): build, test and deploy the Eurobot workspace.
Run `ditx` alone for the interactive command builder.

Usage
  ditx <command> [flags]

Develop commands
  build       build domains in the dev container (incremental)
  test        run unit tests (colcon test) and/or the integration test
  lint        check format and lint (clang-format, ruff, shellcheck, contract)
  index       merge compile_commands.json for clangd (go-to-definition)
  shell       open a shell in the dev container with the workspace sourced
  new         scaffold a new ROS 2 package inside a domain

Robot commands
  deploy      build + push an overlay, restart and verify (auto rollback)
  rollback    go back to the stable image (or an older overlay)
  overlays    list a robot's overlays: who pushed what, when, which commit
  up          start (or update) the runtime stack of a robot
  down        stop the runtime stack of a robot
  logs        show container logs of a robot, or fetch its log folder
  contract    validate the interface contract, render docs, check a live robot
  robot       list, add or remove robots in config/robots.ini

Workspace commands
  sync        fast-forward this repo, clone / fast-forward the domains
  list        packages of every domain: build type and path
  plugins     list plugins (ditx-<name> executables, run as `ditx <name>`)
  cd          jump to a domain or package directory (needs ./install.sh)
  status      branch / ahead / behind / dirty of the shell and every domain
  image       build images with docker buildx bake (base, dev, cross, runtime)
  clean       remove build output
  doctor      check the host (docker, disk, RAM) and robot reachability
  docs        preview or build the user manual (MkDocs Material in Docker)
  ci          run one CI stage exactly like the pipeline does
  init        write .env (your team, default robot, ROS distro)
  tui         interactive command builder (same as running ditx alone)
  completion  print the shell completion script

Plugins  (ditx-<name> in tools/ext or on PATH)
  app         GUI tools: foxglove, rviz, gazebo, groot, qgc
  topics      live topics on a robot: name, type, publishers

Global flags
  -n, --dry-run   print what would run, change nothing
  -v, --verbose   show the full output of every tool
  -q, --quiet     print only warnings and errors
  -h, --help      show help
  -V, --version   print the version

Examples
  ditx sync && ditx build
  ditx test --integration
  ditx deploy -d localization -r sim
  ditx robot add white --host DIT-2026-11

Run `ditx help <command>` for details on a command.
```

## 開發指令

### ditx build

build domains in the dev container (incremental)

```text
usage: ditx build [flags]

build domains in the dev container (incremental)

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  -p PKG..., --packages PKG...
                        only these packages (+ their deps)
  --base                also rebuild the shared base (interfaces) locally
  --arch ARCH           CPU architecture to build for (default: native)
  -j N, --jobs N        compile jobs per package (make -j): auto (by RAM/CPU) or a number
  --workers N           packages built at the same time (colcon --parallel-workers): auto or a
                        number
  --build-type {RelWithDebInfo,Release,Debug}
                        CMake build type
  --clean               wipe the build dirs of the selected domains first
  --clangd              refresh compile_commands.json for clangd after the build (same as ditx
                        index)

Choices:
  --arch amd64                 x86-64 PCs and mini PCs (most laptops, Intel NUC)
  --arch arm64                 ARM boards (Raspberry Pi, Jetson); cross compiled on a PC, no qemu
  --build-type RelWithDebInfo  optimized + debug symbols (default, recommended)
  --build-type Release         fastest, no debug info: what runs at matches
  --build-type Debug           no optimization: best for stepping through with gdb

Examples:
  ditx build
  ditx build -d localization -p localization_fusion
  ditx build --base --clangd
```

### ditx test

run unit tests (colcon test) and/or the integration test

```text
usage: ditx test [flags]

run unit tests (colcon test) and/or the integration test

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  -p PKG..., --packages PKG...
                        only these packages
  --base                also test the shared base packages
  --integration         start every domain together, check startup handshake + contract

Examples:
  ditx test -d main
  ditx test --integration
```

### ditx lint

check format and lint (clang-format, ruff, shellcheck, contract)

```text
usage: ditx lint [flags]

check format and lint (clang-format, ruff, shellcheck, contract)

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  --fix                 rewrite files in place instead of only checking

Examples:
  ditx lint
  ditx lint --fix -d vision
```

### ditx index

merge compile_commands.json for clangd (go-to-definition)

```text
usage: ditx index [flags]

merge compile_commands.json for clangd (go-to-definition)

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)

Examples:
  ditx index
```

### ditx shell

open a shell in the dev container with the workspace sourced

```text
usage: ditx shell [flags]

open a shell in the dev container with the workspace sourced

options:
  --arch ARCH    CPU architecture of the shell (default: native)
  --cmd CMD      run this command instead of an interactive shell

Choices:
  --arch amd64  x86-64 PCs and mini PCs (most laptops, Intel NUC)
  --arch arm64  runs arm64 programs under qemu (see ditx doctor)

Examples:
  ditx shell
  ditx shell --cmd 'ros2 pkg list'
```

### ditx new

scaffold a new ROS 2 package inside a domain

```text
usage: ditx new DOMAIN PACKAGE [flags]

scaffold a new ROS 2 package inside a domain

positional arguments:
  domain               domain to add the package to
  package              package name, snake_case, prefixed with the domain

options:
  --lang {cpp,python}  language

Choices:
  --lang cpp     C++ node (rclcpp, ament_cmake, gtest)
  --lang python  Python node (rclpy, ament_python, pytest)

Examples:
  ditx new vision vision_aruco --lang cpp
  ditx new main main_planner --lang python
```

## 機器人指令

### ditx deploy

build + push an overlay, restart and verify (auto rollback)

```text
usage: ditx deploy [flags]

build + push an overlay, restart and verify (auto rollback)

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains to deploy
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  --no-build            push the last build as is
  --persist             keep the overlay active after a reboot
  --allow-skew          deploy even if built against different interfaces than the robot image
  --no-rollback         leave a failed overlay running for debugging
  -j N, --jobs N        compile jobs per package (make -j): auto (by RAM/CPU) or a number

Examples:
  ditx deploy -d localization -r sim
  ditx deploy -d main vision -r <robot> --persist
```

### ditx rollback

go back to the stable image (or an older overlay)

```text
usage: ditx rollback [flags]

go back to the stable image (or an older overlay)

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains to roll back
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  --to ID               overlay id to activate instead of the stable image
  -y, --yes             do not ask for confirmation

Examples:
  ditx rollback -d localization -r sim
  ditx rollback -d main -r <robot> --to <overlay-id>

Asks for confirmation (restarts the selected domain containers); -y skips it.
```

### ditx overlays

list a robot's overlays: who pushed what, when, which commit

```text
usage: ditx overlays [flags]

list a robot's overlays: who pushed what, when, which commit

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  --json                machine-readable output on stdout

Examples:
  ditx overlays -r sim
  ditx overlays -r <robot> --json
```

### ditx up

start (or update) the runtime stack of a robot

```text
usage: ditx up [flags]

start (or update) the runtime stack of a robot

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  --pull                pull the newest images first

Examples:
  ditx up -r sim
  ditx up -r <robot> --pull
```

### ditx down

stop the runtime stack of a robot

```text
usage: ditx down [flags]

stop the runtime stack of a robot

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  -y, --yes             do not ask for confirmation

Examples:
  ditx down -r sim

Asks for confirmation (stops every eurobot container on the robot); -y skips it.
```

### ditx logs

show container logs of a robot, or fetch its log folder

```text
usage: ditx logs [flags]

show container logs of a robot, or fetch its log folder

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  -f, --follow          keep streaming
  --fetch               copy the robot's logs (/home/share/eurobot/logs) into ./logs/<robot>/

Examples:
  ditx logs -r sim -d localization -f
  ditx logs -r <robot> --fetch
```

### ditx contract

validate the interface contract, render docs, check a live robot

```text
usage: ditx contract [ACTION] [flags]

validate the interface contract, render docs, check a live robot

positional arguments:
  {validate,md,live}    what to do

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini

Choices:
  action validate  check contract.yaml (names, types, QoS profiles)
  action md        regenerate docs/contract.md from contract.yaml
  action live      compare a running robot with the contract

Examples:
  ditx contract
  ditx contract md
  ditx contract live -r sim
```

### ditx robot

list, add or remove robots in config/robots.ini

```text
usage: ditx robot [ACTION] [NAME] [flags]

list, add or remove robots in config/robots.ini

positional arguments:
  {list,add,remove}  what to do
  name               robot name, e.g. white

options:
  --host H           robot hostname, e.g. DIT-2026-11, or any ssh target
  --user U           pin the ssh login (default: your own DIT_ROBOT_USER, set by ditx init)
  --domain-id N      ROS_DOMAIN_ID (default: the number in the hostname)
  --arch ARCH        CPU architecture of the robot (default: amd64)
  --profiles LIST    what runs there, comma separated (default: every domain)
  --tag TAG          image tag it runs (default: stable)
  --json             machine-readable output on stdout
  -y, --yes          do not ask for confirmation

Choices:
  action list    show the configured robots
  action add     add a robot (needs a name and --host)
  action remove  remove a robot (asks first)
  --arch amd64   x86-64 PCs and mini PCs (most laptops, Intel NUC)
  --arch arm64   ARM boards (Raspberry Pi, Jetson); cross compiled on a PC, no qemu

Examples:
  ditx robot
  ditx robot add white --host DIT-2026-11
  ditx robot add black --host DIT-2026-13
  ditx robot remove white
```

## 工作區指令

### ditx sync

fast-forward this repo, clone / fast-forward the domains

```text
usage: ditx sync [DOMAINS] [flags]

fast-forward this repo, clone / fast-forward the domains

positional arguments:
  domains              only these domains

options:
  --no-shell           leave this (shell) repo alone
  --ref DOMAIN=REF...  override a version, e.g. localization=feat/ekf

Examples:
  ditx sync
  ditx sync localization --ref localization=feat/ekf
```

### ditx list

packages of every domain: build type and path

```text
usage: ditx list [flags]

packages of every domain: build type and path

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  --json                machine-readable output on stdout

Examples:
  ditx list
  ditx list -d vision --json
```

### ditx plugins

list plugins (ditx-<name> executables, run as `ditx <name>`)

```text
usage: ditx plugins [flags]

list plugins (ditx-<name> executables, run as `ditx <name>`)

options:
  --json         machine-readable output on stdout

Examples:
  ditx plugins
  ditx topics -r sim
  ditx app rviz -r sim
```

### ditx cd

jump to a domain or package directory (needs ./install.sh)

```text
usage: ditx cd [TARGET] [flags]

jump to a domain or package directory (needs ./install.sh)

positional arguments:
  target         domain or package (empty: workspace root)

options:

Examples:
  ditx cd localization_fusion
  ditx cd
```

### ditx status

branch / ahead / behind / dirty of the shell and every domain

```text
usage: ditx status [flags]

branch / ahead / behind / dirty of the shell and every domain

options:
  --no-fetch     do not contact the remotes
  --json         machine-readable output on stdout

Examples:
  ditx status
  ditx status --no-fetch --json
```

### ditx image

build images with docker buildx bake (base, dev, cross, runtime)

```text
usage: ditx image [flags]

build images with docker buildx bake (base, dev, cross, runtime)

options:
  --target {default,base,dev,cross,runtime}
                        what to build
  --tag TAG             image tag (default: local)
  --platforms PLATFORMS
                        e.g. linux/amd64,linux/arm64
  --push                push to the registry instead of loading locally

Choices:
  --target default  everything: base, dev, cross and one runtime image per domain
  --target base     ROS + shared interfaces (what every robot container starts from)
  --target dev      base + compilers and tools (what ditx build/test/lint run in)
  --target cross    dev + arm64 sysroot (ditx build --arch arm64 on an amd64 PC)
  --target runtime  one image per domain, as the robots run it

Examples:
  ditx image
  ditx image --target dev --tag local
```

### ditx clean

remove build output

```text
usage: ditx clean [flags]

remove build output

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)
  --base                also remove the local base build
  --all                 remove the whole build/ directory
  -y, --yes             do not ask for confirmation

Examples:
  ditx clean -d vision
  ditx clean --all -y

Asks for confirmation (deletes build output; the next build starts from scratch); -y skips it.
```

### ditx doctor

check the host (docker, disk, RAM) and robot reachability

```text
usage: ditx doctor [flags]

check the host (docker, disk, RAM) and robot reachability

options:
  -r ROBOT, --robot ROBOT
                        target robot from config/robots.ini
  --json                machine-readable output on stdout

Examples:
  ditx doctor
  ditx doctor -r <robot>
```

### ditx docs

preview or build the user manual (MkDocs Material in Docker)

```text
usage: ditx docs [ACTION] [flags]

preview or build the user manual (MkDocs Material in Docker)

positional arguments:
  {serve,build}         action

options:
  -p PORT, --port PORT  preview port (default: 8000)

Choices:
  action serve  live preview on http://localhost:<port>, reloads on save
  action build  strict build into site/, exactly like the docs CI job

Examples:
  ditx docs
  ditx docs build
  ditx docs serve -p 8001
```

### ditx ci

run one CI stage exactly like the pipeline does

```text
usage: ditx ci STAGE [flags]

run one CI stage exactly like the pipeline does

positional arguments:
  {lint,build,test,cross,image}
                        stage

options:
  -d DOMAIN..., --domain DOMAIN...
                        domains (default: all synced)

Choices:
  stage lint   formatting, ruff, shellcheck, contract, boundaries
  stage build  build every domain
  stage test   base + domain unit tests and the integration test
  stage cross  build every domain for arm64 (cross compiled)
  stage image  build images (push on develop / main / tags)

Examples:
  ditx ci lint
  ditx ci test
```

### ditx init

write .env (your team, default robot, ROS distro)

```text
usage: ditx init [flags]

write .env (your team, default robot, ROS distro)

options:
  --defaults     take every default, ask nothing

Examples:
  ditx init
  ditx init --defaults
```

### ditx tui

interactive command builder (same as running ditx alone)

```text
usage: ditx tui [flags]

interactive command builder (same as running ditx alone)

options:

Examples:
  ditx
  ditx -n
```

### ditx completion

print the shell completion script

```text
usage: ditx completion SHELL [flags]

print the shell completion script

positional arguments:
  {bash,zsh,fish}  shell

options:

Choices:
  shell bash  bash
  shell zsh   zsh
  shell fish  fish

Examples:
  source <(ditx completion bash)
  ditx completion fish | source
```
