"""Declarative table of every ditx command and option.

argparse (cli.py), Tab completion (complete.py) and the TUI (tui.py) are all
generated from this table, so the three can never disagree. Adding a command =
one Cmd here + one handler function in cli.py named cmd_<name>.
"""

from dataclasses import dataclass, field, replace


@dataclass
class Opt:
    flags: tuple  # ('-d', '--domain'); empty tuple = positional
    dest: str
    kind: str  # flag | choice | multi | text
    help: str
    values: object = (
        None  # tuple of choices, or a source name: domains robots packages arches stages
    )
    default: object = None
    metavar: str = None
    tui: bool = True  # offer it in the TUI
    choice_help: dict = field(default_factory=dict)  # value -> one line (help, TUI, completion)


@dataclass
class Cmd:
    name: str
    group: str
    help: str  # one line, English (shown by --help)
    opts: list = field(default_factory=list)
    confirm: str = ''  # non-empty => destructive: TUI and CLI ask before running (-y skips)
    tui: bool = True
    examples: list = field(default_factory=list)  # shown under `ditx help <command>`
    required: set = field(default_factory=set)  # dests the TUI insists on (plugins declare them)


def plugin_cmd(name, path, summary=''):
    """A plugin as a Cmd, so the TUI and completion can offer its arguments.

    Plugins declare them in their first lines, after `# ditx-plugin: <summary>`:
      # ditx-arg: tool choice:rviz|foxglove required  GUI tool to open
      # ditx-choice: rviz  RViz2 window              (meaning of a value of the arg above)
      # ditx-arg: -r,--robot choice:robots  target robot from config/robots.ini
    The kind is flag | text | choice | multi; values are `a|b|c` or a source name
    (robots, domains, packages, arches); `required` after it marks a mandatory argument.
    """
    opts, required = [], set()
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            head = fh.readlines()[:40]
    except OSError:
        head = []
    for line in head:
        line = line.lstrip('#/ ').strip()
        if line.startswith('ditx-arg:'):
            parts = line[len('ditx-arg:') :].split()
            if len(parts) < 2:
                continue
            spec, kind = parts[0], parts[1]
            kind, _, values = kind.partition(':')
            rest = parts[2:]
            if rest[:1] == ['required']:
                rest = rest[1:]
                required.add(len(opts))
            flags = tuple(spec.split(',')) if spec.startswith('-') else ()
            dest = (flags[-1].lstrip('-') if flags else spec).replace('-', '_')
            if kind not in ('flag', 'text', 'choice', 'multi'):
                continue
            vals = tuple(values.split('|')) if '|' in values else (values or None)
            meta = dest.upper() if kind != 'flag' else None
            opts.append(Opt(flags, dest, kind, ' '.join(rest), values=vals, metavar=meta))
        elif line.startswith('ditx-choice:') and opts:
            value, _, meaning = line[len('ditx-choice:') :].strip().partition(' ')
            opts[-1].choice_help[value] = meaning.strip()
    return Cmd(
        name,
        'plugins',
        summary or f'plugin {path}',
        opts,
        required={opts[i].dest for i in required},
    )


def D(help_='domains (default: all synced)'):
    return Opt(('-d', '--domain'), 'domains', 'multi', help_, values='domains', metavar='DOMAIN')


ROBOT = Opt(
    ('-r', '--robot'),
    'robot',
    'choice',
    'target robot from config/robots.ini',
    values='robots',
    metavar='ROBOT',
)
ARCH = Opt(
    ('--arch',),
    'arch',
    'choice',
    'CPU architecture to build for (default: native)',
    values='arches',
    choice_help={
        'amd64': 'x86-64 PCs and mini PCs (most laptops, Intel NUC)',
        'arm64': 'ARM boards (Raspberry Pi, Jetson); cross compiled on a PC, no qemu',
    },
)
# a shell has to run the programs, so a foreign arch is emulated instead of cross compiled
SHELL_ARCH = replace(
    ARCH,
    help='CPU architecture of the shell (default: native)',
    choice_help={**ARCH.choice_help, 'arm64': 'runs arm64 programs under qemu (see ditx doctor)'},
)
JOBS = Opt(
    ('-j', '--jobs'),
    'jobs',
    'text',
    'compile jobs per package (make -j): auto (by RAM/CPU) or a number',
    values='auto',
    default='auto',
    metavar='N',
)
WORKERS = Opt(
    ('--workers',),
    'workers',
    'text',
    'packages built at the same time (colcon --parallel-workers): auto or a number',
    values='auto',
    default='auto',
    metavar='N',
)
CLANGD = Opt(
    ('--clangd',),
    'clangd',
    'flag',
    'refresh compile_commands.json for clangd after the build (same as ditx index)',
)

COMMANDS = [
    # ── develop ────────────────────────────────────────────────────────────
    Cmd(
        'build',
        'develop',
        'build domains in the dev container (incremental)',
        [
            D(),
            Opt(
                ('-p', '--packages'),
                'packages',
                'multi',
                'only these packages (+ their deps)',
                values='packages',
                metavar='PKG',
            ),
            Opt(('--base',), 'base', 'flag', 'also rebuild the shared base (interfaces) locally'),
            ARCH,
            JOBS,
            WORKERS,
            Opt(
                ('--build-type',),
                'build_type',
                'choice',
                'CMake build type',
                values=('RelWithDebInfo', 'Release', 'Debug'),
                default='RelWithDebInfo',
                choice_help={
                    'RelWithDebInfo': 'optimized + debug symbols (default, recommended)',
                    'Release': 'fastest, no debug info: what runs at matches',
                    'Debug': 'no optimization: best for stepping through with gdb',
                },
            ),
            Opt(('--clean',), 'clean', 'flag', 'wipe the build dirs of the selected domains first'),
            CLANGD,
        ],
    ),
    Cmd(
        'test',
        'develop',
        'run unit tests (colcon test) and/or the integration test',
        [
            D(),
            Opt(
                ('-p', '--packages'),
                'packages',
                'multi',
                'only these packages',
                values='packages',
                metavar='PKG',
            ),
            Opt(('--base',), 'base', 'flag', 'also test the shared base packages'),
            Opt(
                ('--integration',),
                'integration',
                'flag',
                'start every domain together, check startup handshake + contract',
            ),
        ],
    ),
    Cmd(
        'lint',
        'develop',
        'check format and lint (clang-format, ruff, shellcheck, contract)',
        [
            D(),
            Opt(('--fix',), 'fix', 'flag', 'rewrite files in place instead of only checking'),
        ],
    ),
    Cmd(
        'index',
        'develop',
        'merge compile_commands.json for clangd (go-to-definition)',
        [D()],
    ),
    Cmd(
        'shell',
        'develop',
        'open a shell in the dev container with the workspace sourced',
        [
            SHELL_ARCH,
            Opt(
                ('--cmd',),
                'cmd',
                'text',
                'run this command instead of an interactive shell',
                metavar='CMD',
                tui=False,
            ),
        ],
    ),
    Cmd(
        'new',
        'develop',
        'scaffold a new ROS 2 package inside a domain',
        [
            Opt((), 'domain', 'choice', 'domain to add the package to', values='domains'),
            Opt((), 'package', 'text', 'package name, snake_case, prefixed with the domain'),
            Opt(
                ('--lang',),
                'lang',
                'choice',
                'language',
                values=('cpp', 'python'),
                default='cpp',
                choice_help={
                    'cpp': 'C++ node (rclcpp, ament_cmake, gtest)',
                    'python': 'Python node (rclpy, ament_python, pytest)',
                },
            ),
        ],
    ),
    # ── robot ──────────────────────────────────────────────────────────────
    Cmd(
        'deploy',
        'robot',
        'build + push an overlay, restart and verify (auto rollback)',
        [
            D('domains to deploy'),
            ROBOT,
            Opt(('--no-build',), 'no_build', 'flag', 'push the last build as is'),
            Opt(('--persist',), 'persist', 'flag', 'keep the overlay active after a reboot'),
            Opt(
                ('--allow-skew',),
                'allow_skew',
                'flag',
                'deploy even if built against different interfaces than the robot image',
            ),
            Opt(
                ('--no-rollback',),
                'no_rollback',
                'flag',
                'leave a failed overlay running for debugging',
            ),
            JOBS,
        ],
    ),
    Cmd(
        'rollback',
        'robot',
        'go back to the stable image (or an older overlay)',
        [
            D('domains to roll back'),
            ROBOT,
            Opt(
                ('--to',),
                'to',
                'text',
                'overlay id to activate instead of the stable image',
                metavar='ID',
            ),
        ],
        confirm='restarts the selected domain containers',
    ),
    Cmd(
        'overlays',
        'robot',
        "list a robot's overlays: who pushed what, when, which commit",
        [ROBOT, D()],
    ),
    Cmd(
        'up',
        'robot',
        'start (or update) the runtime stack of a robot',
        [ROBOT, Opt(('--pull',), 'pull', 'flag', 'pull the newest images first')],
    ),
    Cmd(
        'down',
        'robot',
        'stop the runtime stack of a robot',
        [ROBOT],
        confirm='stops every eurobot container on the robot',
    ),
    Cmd(
        'logs',
        'robot',
        'show container logs of a robot, or fetch its log folder',
        [
            ROBOT,
            D(),
            Opt(('-f', '--follow'), 'follow', 'flag', 'keep streaming'),
            Opt(
                ('--fetch',),
                'fetch',
                'flag',
                "copy the robot's logs (/home/share/eurobot/logs) into ./logs/<robot>/",
            ),
        ],
    ),
    Cmd(
        'contract',
        'robot',
        'validate the interface contract, render docs, check a live robot',
        [
            Opt(
                (),
                'action',
                'choice',
                'what to do',
                values=('validate', 'md', 'live'),
                default='validate',
                choice_help={
                    'validate': 'check contract.yaml (names, types, QoS profiles)',
                    'md': 'regenerate docs/contract.md from contract.yaml',
                    'live': 'compare a running robot with the contract',
                },
            ),
            ROBOT,
        ],
    ),
    Cmd(
        'robot',
        'robot',
        'list, add or remove robots in config/robots.ini',
        [
            Opt(
                (),
                'action',
                'choice',
                'what to do',
                values=('list', 'add', 'remove'),
                default='list',
                choice_help={
                    'list': 'show the configured robots',
                    'add': 'add a robot (needs a name and --host)',
                    'remove': 'remove a robot (asks first)',
                },
            ),
            Opt((), 'name', 'text', 'robot name, e.g. white', default=''),
            Opt(
                ('--host',),
                'host',
                'text',
                'robot hostname, e.g. DIT-2026-11, or any ssh target',
                metavar='H',
            ),
            Opt(
                ('--user',),
                'user',
                'text',
                'pin the ssh login (default: your own DIT_ROBOT_USER, set by ditx init)',
                metavar='U',
            ),
            Opt(
                ('--domain-id',),
                'domain_id',
                'text',
                'ROS_DOMAIN_ID (default: the number in the hostname)',
                metavar='N',
            ),
            Opt(
                ('--arch',),
                'arch',
                'choice',
                'CPU architecture of the robot (default: amd64)',
                values='arches',
                choice_help=ARCH.choice_help,
            ),
            Opt(
                ('--profiles',),
                'profiles',
                'text',
                'what runs there, comma separated (default: every domain)',
                metavar='LIST',
            ),
            Opt(('--tag',), 'tag', 'text', 'image tag it runs (default: stable)', metavar='TAG'),
        ],
    ),
    # ── workspace ──────────────────────────────────────────────────────────
    Cmd(
        'sync',
        'workspace',
        'fast-forward this repo, clone / fast-forward the domains',
        [
            Opt((), 'domains', 'multi', 'only these domains', values='domains'),
            Opt(('--no-shell',), 'no_shell', 'flag', 'leave this (shell) repo alone'),
            Opt(
                ('--ref',),
                'refs',
                'multi',
                'override a version, e.g. localization=feat/ekf',
                metavar='DOMAIN=REF',
                tui=False,
            ),
        ],
    ),
    Cmd(
        'list',
        'workspace',
        'packages of every domain: build type and path',
        [D()],
    ),
    Cmd(
        'plugins',
        'workspace',
        'list plugins (ditx-<name> executables, run as `ditx <name>`)',
        [],
    ),
    Cmd(
        'cd',
        'workspace',
        'jump to a domain or package directory (needs ./install.sh)',
        [
            Opt(
                (),
                'target',
                'choice',
                'domain or package (empty: workspace root)',
                values='targets',
                default='',
            )
        ],
        tui=False,
    ),
    Cmd(
        'status',
        'workspace',
        'branch / ahead / behind / dirty of the shell and every domain',
        [Opt(('--no-fetch',), 'no_fetch', 'flag', 'do not contact the remotes')],
    ),
    Cmd(
        'image',
        'workspace',
        'build images with docker buildx bake (base, dev, cross, runtime)',
        [
            Opt(
                ('--target',),
                'target',
                'choice',
                'what to build',
                values=('default', 'base', 'dev', 'cross', 'runtime'),
                default='default',
                choice_help={
                    'default': 'everything: base, dev, cross and one runtime image per domain',
                    'base': 'ROS + shared interfaces (what every robot container starts from)',
                    'dev': 'base + compilers and tools (what ditx build/test/lint run in)',
                    'cross': 'dev + arm64 sysroot (ditx build --arch arm64 on an amd64 PC)',
                    'runtime': 'one image per domain, as the robots run it',
                },
            ),
            Opt(('--tag',), 'tag', 'text', 'image tag (default: local)', default='local'),
            Opt(
                ('--platforms',),
                'platforms',
                'text',
                'e.g. linux/amd64,linux/arm64',
                default='linux/amd64',
            ),
            Opt(('--push',), 'push', 'flag', 'push to the registry instead of loading locally'),
        ],
    ),
    Cmd(
        'clean',
        'workspace',
        'remove build output',
        [
            D(),
            Opt(('--base',), 'base', 'flag', 'also remove the local base build'),
            Opt(('--all',), 'all', 'flag', 'remove the whole build/ directory'),
        ],
        confirm='deletes build output; the next build starts from scratch',
    ),
    Cmd(
        'doctor',
        'workspace',
        'check the host (docker, disk, RAM) and robot reachability',
        [ROBOT],
    ),
    Cmd(
        'docs',
        'workspace',
        'preview or build the user manual (MkDocs Material in Docker)',
        [
            Opt(
                (),
                'action',
                'choice',
                'action',
                values=('serve', 'build'),
                default='serve',
                choice_help={
                    'serve': 'live preview on http://localhost:<port>, reloads on save',
                    'build': 'strict build into site/, exactly like the docs CI job',
                },
            ),
            Opt(('-p', '--port'), 'port', 'text', 'preview port (default: 8000)', default='8000'),
        ],
    ),
    Cmd(
        'ci',
        'workspace',
        'run one CI stage exactly like the pipeline does',
        [
            Opt(
                (),
                'stage',
                'choice',
                'stage',
                values=('lint', 'build', 'test', 'cross', 'image'),
                choice_help={
                    'lint': 'formatting, ruff, shellcheck, contract, boundaries',
                    'build': 'build every domain',
                    'test': 'base + domain unit tests and the integration test',
                    'cross': 'build every domain for arm64 (cross compiled)',
                    'image': 'build images (push on develop / main / tags)',
                },
            ),
            D(),
        ],
    ),
    Cmd(
        'init',
        'workspace',
        'write .env (your team, default robot, ROS distro)',
        [],
        tui=False,
    ),
    Cmd('tui', 'workspace', 'interactive command builder (same as running ditx alone)', tui=False),
    Cmd(
        'completion',
        'workspace',
        'print the shell completion script',
        opts=[
            Opt(
                (),
                'shell',
                'choice',
                'shell',
                values=('bash', 'zsh', 'fish'),
                choice_help={'bash': 'bash', 'zsh': 'zsh', 'fish': 'fish'},
            )
        ],
        tui=False,
    ),
]

JSON = Opt(('--json',), 'json', 'flag', 'machine-readable output on stdout', tui=False)
YES = Opt(('-y', '--yes'), 'yes', 'flag', 'do not ask for confirmation', tui=False)
for _c in COMMANDS:
    if _c.name in ('status', 'list', 'overlays', 'plugins', 'doctor', 'robot'):
        _c.opts.append(JSON)
    if _c.confirm or _c.name == 'robot':  # robot remove asks too
        _c.opts.append(YES)
    if _c.name == 'init':
        _c.opts.append(
            Opt(('--defaults',), 'defaults', 'flag', 'take every default, ask nothing', tui=False)
        )

EXAMPLES = {
    'build': [
        'ditx build',
        'ditx build -d localization -p localization_fusion',
        'ditx build --base --clangd',
    ],
    'test': ['ditx test -d main', 'ditx test --integration'],
    'lint': ['ditx lint', 'ditx lint --fix -d vision'],
    'index': ['ditx index'],
    'shell': ['ditx shell', "ditx shell --cmd 'ros2 pkg list'"],
    'new': ['ditx new vision vision_aruco --lang cpp', 'ditx new main main_planner --lang python'],
    'deploy': [
        'ditx deploy -d localization -r sim',
        'ditx deploy -d main vision -r <robot> --persist',
    ],
    'rollback': [
        'ditx rollback -d localization -r sim',
        'ditx rollback -d main -r <robot> --to <overlay-id>',
    ],
    'overlays': ['ditx overlays -r sim', 'ditx overlays -r <robot> --json'],
    'up': ['ditx up -r sim', 'ditx up -r <robot> --pull'],
    'down': ['ditx down -r sim'],
    'logs': ['ditx logs -r sim -d localization -f', 'ditx logs -r <robot> --fetch'],
    'robot': [
        'ditx robot',
        'ditx robot add white --host DIT-2026-11',
        'ditx robot add black --host DIT-2026-13',
        'ditx robot remove white',
    ],
    'contract': ['ditx contract', 'ditx contract md', 'ditx contract live -r sim'],
    'sync': ['ditx sync', 'ditx sync localization --ref localization=feat/ekf'],
    'list': ['ditx list', 'ditx list -d vision --json'],
    'cd': ['ditx cd localization_fusion', 'ditx cd'],
    'plugins': ['ditx plugins', 'ditx topics -r sim', 'ditx app rviz -r sim'],
    'status': ['ditx status', 'ditx status --no-fetch --json'],
    'image': ['ditx image', 'ditx image --target dev --tag local'],
    'clean': ['ditx clean -d vision', 'ditx clean --all -y'],
    'doctor': ['ditx doctor', 'ditx doctor -r <robot>'],
    'docs': ['ditx docs', 'ditx docs build', 'ditx docs serve -p 8001'],
    'ci': ['ditx ci lint', 'ditx ci test'],
    'init': ['ditx init', 'ditx init --defaults'],
    'tui': ['ditx', 'ditx -n'],
    'completion': ['source <(ditx completion bash)', 'ditx completion fish | source'],
}
for _c in COMMANDS:
    _c.examples = EXAMPLES.get(_c.name, _c.examples)

BY_NAME = {c.name: c for c in COMMANDS}
GROUPS = [('develop', 'Develop'), ('robot', 'Robot'), ('workspace', 'Workspace')]


def resolve_values(src, ws, domains=None):
    """Turn Opt.values into a list of strings for completion / TUI pickers.

    domains: the -d/--domain values already chosen; packages are then only theirs.
    """
    if src is None:
        return []
    if isinstance(src, tuple | list):
        return list(src)
    if src == 'auto':
        return ['auto']
    if ws is None:
        return []
    try:
        if src == 'domains':
            return ws.domains()
        if src == 'robots':
            return list(ws.robots())
        if src == 'packages':
            return ws.packages([d for d in domains or () if d in ws.synced_domains()] or None)
        if src == 'arches':
            return ['amd64', 'arm64']
        if src == 'targets':
            return ws.domains() + ws.packages()
        if src == 'auto':
            return ['auto']
    except Exception:  # noqa: BLE001 - completion must never crash
        return []
    return []
