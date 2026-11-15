"""Unit tests for ditx (stdlib unittest; no docker, no terminal needed).

python3 -m unittest discover -s tools/tests -v
"""

import argparse
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# tests must not depend on the caller's settings (DIT_REPOS_FILE, ROS_DISTRO, ...)
for _k in [k for k in os.environ if k.startswith('DIT_') or k in ('ROS_DISTRO', 'REGISTRY')]:
    del os.environ[_k]

from ditx import cli, commands  # noqa: E402
from ditx.complete import complete  # noqa: E402
from ditx.tui import Model, opt_label, toggle_all  # noqa: E402
from ditx.workspace import Workspace, auto_jobs, find_root, parse_repos  # noqa: E402


def make_ws(domains=('main', 'localization')):
    """A throw-away workspace with the real config and fake domain packages."""
    root = tempfile.mkdtemp(prefix='dit-test-')
    os.makedirs(os.path.join(root, 'tools', 'ditx'))
    shutil.copytree(os.path.join(ROOT, 'config'), os.path.join(root, 'config'))
    # a real robot for the tests, independent of what the template ships
    with open(os.path.join(root, 'config', 'robots.ini'), 'a') as f:
        f.write(
            '\n[white]\nhost = main@dit-2026-11.local\narch = amd64\ndomain_id = 11\n'
            'profiles = main,navigation,localization,vision,firmware,monitoring\ntag = stable\n'
        )
    with open(os.path.join(root, 'ditx.repos'), 'w') as f:
        f.write('repositories:\n')
        for d in domains:
            f.write(
                f'  domains/{d}:\n    type: git\n    url: https://example.com/{d}.git\n'
                f'    version: develop\n'
            )
    for d in domains:
        for pkg in (f'{d}_bringup', f'{d}_core'):
            p = os.path.join(root, 'domains', d, 'src', pkg)
            os.makedirs(os.path.join(p, 'launch'))
            with open(os.path.join(p, 'package.xml'), 'w') as f:
                f.write(f'<package><name>{pkg}</name><depend>rclcpp</depend></package>')
            open(os.path.join(p, 'launch', 'bringup.launch.py'), 'w').close()
    return Workspace(root)


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.ws = make_ws()

    def tearDown(self):
        shutil.rmtree(self.ws.root)

    def test_repos_file_of_the_template_parses(self):
        repos = parse_repos(os.path.join(ROOT, 'ditx.repos'))
        self.assertEqual(
            sorted(repos),
            ['domains/localization', 'domains/main', 'domains/navigation', 'domains/vision'],
        )
        self.assertEqual(repos['domains/main']['version'], 'develop')

    def test_domains_and_packages(self):
        self.assertEqual(self.ws.domains(), ['main', 'localization'])
        self.assertIn('main_core', self.ws.packages())

    def test_find_root_walks_up(self):
        deep = os.path.join(self.ws.root, 'domains', 'main', 'src')
        self.assertEqual(find_root(deep), self.ws.root)

    def test_robots(self):
        robots = self.ws.robots()
        self.assertTrue(robots['sim'].is_local)
        self.assertEqual(robots['white'].domain_id, '11')
        self.assertIn('monitoring', robots['white'].profiles)

    def test_auto_jobs_never_exceeds_ram_budget(self):
        for mem, cpus in [(8, 16), (16, 8), (32, 22), (64, 32), (4, 4)]:
            workers, jobs, cap = auto_jobs(mem, cpus)
            self.assertLessEqual(workers * jobs * 1.5, max(1.5, mem * 0.75) + 1e-9, (mem, cpus))
            self.assertLessEqual(workers * jobs, cpus)
            self.assertLess(cap, mem + 1)

    def test_default_distro_is_humble(self):
        self.assertEqual(Workspace(self.ws.root).distro, 'humble')  # what the robots run

    def test_env_precedence(self):
        with open(os.path.join(self.ws.root, '.env'), 'w') as f:
            f.write('ROS_DISTRO=jazzy\n')
        ws = Workspace(self.ws.root)
        self.assertEqual(ws.distro, 'jazzy')
        with mock.patch.dict(os.environ, {'ROS_DISTRO': 'humble'}):
            self.assertEqual(ws.distro, 'humble')


class CommandTableTest(unittest.TestCase):
    def test_every_command_has_a_handler(self):
        for c in commands.COMMANDS:
            self.assertTrue(hasattr(cli, 'cmd_' + c.name), c.name)

    def test_parser_accepts_what_the_table_declares(self):
        p = cli.build_parser()
        a = p.parse_args(['deploy', '-d', 'main', 'vision', '-r', 'white', '--persist'])
        self.assertEqual((a.domains, a.robot, a.persist), (['main', 'vision'], 'white', True))
        a = p.parse_args(['contract'])
        self.assertEqual(a.action, 'validate')
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            p.parse_args(['build', '--build-type', 'Fast'])

    def test_typo_suggests_the_command(self):
        err = io.StringIO()
        root = mock.patch.object(cli, 'find_root', return_value=ROOT)
        with contextlib.redirect_stderr(err), root:
            self.assertEqual(cli.main(['biuld']), 2)
        self.assertIn("did you mean 'build'", err.getvalue())

    def test_jobs_and_workers_share_one_budget(self):
        with mock.patch.object(cli, 'auto_jobs', return_value=(3, 5, 24)):
            self.assertEqual(cli.parse_jobs(), (3, 5, 24))
            self.assertEqual(cli.parse_jobs('8', 'auto'), (1, 8, 24))
            self.assertEqual(cli.parse_jobs('auto', '2'), (2, 7, 24))
            self.assertEqual(cli.parse_jobs('4', '4'), (4, 4, 24))
            with self.assertRaises(cli.Fail):
                cli.parse_jobs('0')
            with self.assertRaises(cli.Fail):
                cli.parse_jobs('auto', 'x')

    def test_ci_tags(self):
        env = {'GITHUB_REF_NAME': 'main', 'GITHUB_SHA': 'abcdef123'}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(cli.ci_tags(), ('stable', 'sha-abcdef1'))
        with mock.patch.dict(
            os.environ,
            {
                'CI_COMMIT_REF_NAME': 'v2027.1.0',
                'CI_COMMIT_TAG': 'v2027.1.0',
                'CI_COMMIT_SHA': '1234567',
            },
            clear=True,
        ):
            self.assertEqual(cli.ci_tags()[0], 'v2027.1.0')
        with mock.patch.dict(os.environ, {'GITHUB_REF_NAME': 'feat/x'}, clear=True):
            self.assertEqual(cli.ci_tags(), (None, None))


class CompletionTest(unittest.TestCase):
    def setUp(self):
        self.ws = make_ws()

    def tearDown(self):
        shutil.rmtree(self.ws.root)

    def test_commands(self):
        self.assertEqual(complete(self.ws, ['dep']), ['deploy'])

    def test_option_values_come_from_the_workspace(self):
        self.assertEqual(complete(self.ws, ['deploy', '-d', '']), ['main', 'localization'])
        self.assertIn('white', complete(self.ws, ['deploy', '-r', 'w']))
        self.assertEqual(complete(self.ws, ['build', '--build-type', 'D']), ['Debug'])

    def test_flags(self):
        out = complete(self.ws, ['deploy', '--p'])
        self.assertEqual(out, ['--persist'])

    def test_positionals(self):
        self.assertEqual(complete(self.ws, ['ci', 'l']), ['lint'])
        self.assertEqual(complete(self.ws, ['new', '']), ['main', 'localization'])

    def test_unknown_command_is_quiet(self):
        self.assertEqual(complete(self.ws, ['nope', '']), [])


class TuiModelTest(unittest.TestCase):
    def setUp(self):
        self.ws = make_ws()
        self.m = Model(self.ws)

    def tearDown(self):
        shutil.rmtree(self.ws.root)

    def test_deploy_command_line(self):
        self.m.select('deploy')
        self.assertIn('--domain', self.m.problem())  # domains required
        self.m.set_value(self.m.opt('domains'), ['localization'])
        self.m.set_value(self.m.opt('robot'), 'white')
        self.m.cycle(self.m.opt('persist'))
        self.assertIsNone(self.m.problem())
        # long flags, the same spelling as the option labels in the TUI
        self.assertEqual(
            self.m.command_line(), 'ditx deploy --domain localization --robot white --persist'
        )

    def test_defaults_are_not_spelled_out(self):
        self.m.select('build')
        self.assertEqual(self.m.argv(), ['build'])
        self.m.cycle(self.m.opt('build_type'))
        self.assertEqual(self.m.argv(), ['build', '--build-type', 'Release'])

    def test_positionals_and_validation(self):
        self.m.select('new')
        self.m.set_value(self.m.opt('domain'), 'main')
        self.m.set_value(self.m.opt('package'), 'planner')
        self.assertIn('main_planner', self.m.problem())
        self.m.set_value(self.m.opt('package'), 'main_planner')
        self.assertEqual(self.m.argv(), ['new', 'main', 'main_planner'])

    def test_robot_add_needs_name_and_host(self):
        self.m.select('robot')
        self.assertIsNone(self.m.problem())  # list
        self.m.set_value(self.m.opt('action'), 'add')
        self.assertIn('NAME', self.m.problem())
        self.m.set_value(self.m.opt('name'), 'white')
        self.assertIn('--host', self.m.problem())
        self.m.set_value(self.m.opt('host'), 'DIT-2026-11')
        self.assertIsNone(self.m.problem())

    def test_dry_run_toggle(self):
        self.m.select('sync')
        self.m.dry_run = True
        self.assertEqual(self.m.argv(), ['sync', '--dry-run'])

    def test_generated_line_parses_back(self):
        p = cli.build_parser()
        for c in self.m.commands:
            self.m.select(c.name)
            for o in self.m.options():
                if o.kind == 'flag':
                    self.m.cycle(o)
            if self.m.problem() is None:
                p.parse_args(self.m.argv())

    def test_state_roundtrip_and_garbage(self):
        self.m.select('logs')
        self.m.cycle(self.m.opt('follow'))
        m2 = Model(self.ws, self.m.to_dict())
        self.assertEqual(m2.cmd.name, 'logs')
        self.assertEqual(m2.argv(), ['logs', '--follow'])
        Model(self.ws, {'command': 42, 'values': {'logs': {'follow': 'yes'}, 'x': 1}})
        Model(self.ws, 'garbage')

    def test_load_drops_invalid_values_and_restores_focus(self):
        state = {
            'command': 'build',
            'values': {'build': {'jobs': 'abc', 'workers': '2', 'build_type': 'Fast'}},
            'focus': 'opts',
            'opt': 3,
        }
        m2 = Model(self.ws, state)
        self.assertEqual(m2.argv(), ['build', '--workers', '2'])  # jobs/build_type dropped
        self.assertEqual((m2.focus, m2.opt_i), ('opts', 3))

    def test_reset_returns_to_default(self):
        self.m.select('build')
        o = self.m.opt('jobs')
        self.m.set_value(o, '4')
        self.assertTrue(self.m.is_set(o))
        self.m.reset(o)
        self.assertFalse(self.m.is_set(o))
        self.assertEqual(self.m.value(o), 'auto')

    def test_value_problem(self):
        o = next(x for x in commands.BY_NAME['build'].opts if x.dest == 'jobs')
        self.assertIsNone(Model.value_problem('build', o, 'auto'))
        self.assertIsNone(Model.value_problem('build', o, '4'))
        self.assertIn('positive', Model.value_problem('build', o, '0'))

    def test_packages_follow_the_selected_domains(self):
        self.m.select('build')
        pk = self.m.opt('packages')
        self.assertEqual(
            self.m.choices(pk),
            ['localization_bringup', 'localization_core', 'main_bringup', 'main_core'],
        )
        self.m.set_value(self.m.opt('domains'), ['main'])
        self.assertEqual(self.m.choices(pk), ['main_bringup', 'main_core'])
        self.m.set_value(pk, ['localization_core'])
        self.assertIn('localization_core is not in the selected domains (main)', self.m.problem())
        self.m.set_value(pk, ['main_core'])
        self.assertIsNone(self.m.problem())

    def test_ctrl_a_selects_all_visible_or_none(self):
        self.assertEqual(toggle_all({'a'}, ['a', 'b']), {'a', 'b'})
        self.assertEqual(toggle_all({'a', 'b', 'c'}, ['a', 'b']), {'c'})

    def test_positional_labels_are_uppercase(self):
        self.m.select('new')
        labels = [opt_label(o) for o in self.m.options()]
        self.assertEqual(labels[:2], ['DOMAIN', 'PACKAGE'])
        self.assertIn('set DOMAIN first', self.m.problem())

    def test_mouse_setting_is_remembered(self):
        self.m.mouse = False
        self.assertFalse(Model(self.ws, self.m.to_dict()).mouse)
        self.assertTrue(Model(self.ws, {'mouse': 'nope'}).mouse)

    def test_plugins_get_global_flags_before_their_name(self):
        ext = os.path.join(self.ws.root, 'tools', 'ext')
        os.makedirs(ext)
        path = os.path.join(ext, 'ditx-hello')
        with open(path, 'w') as f:
            f.write('#!/bin/sh\n# ditx-plugin: says hello\n')
        os.chmod(path, 0o755)
        m = Model(self.ws)
        m.select('hello')
        m.dry_run = True
        self.assertEqual((m.cmd.group, m.cmd.help, m.cmd.opts), ('plugins', 'says hello', []))
        self.assertEqual(m.argv(), ['--dry-run', 'hello'])  # ditx passes it as DITX_DRY_RUN


class PluginArgsTest(unittest.TestCase):
    """Plugins declare `# ditx-arg:` lines; the TUI and completion offer them."""

    def setUp(self):
        self.ws = make_ws()
        ext = os.path.join(self.ws.root, 'tools', 'ext')
        os.makedirs(ext)
        shutil.copy(os.path.join(ROOT, 'tools', 'ext', 'ditx-app'), ext)

    def tearDown(self):
        shutil.rmtree(self.ws.root)

    def test_app_declares_tool_and_robot(self):
        path, summary = self.ws.plugins()['app']
        c = commands.plugin_cmd('app', path, summary)
        tool, robot = c.opts
        self.assertEqual((tool.flags, tool.kind), ((), 'choice'))
        self.assertEqual(tool.values[0], 'foxglove')
        self.assertIn('rviz', tool.choice_help)
        self.assertEqual((robot.flags, robot.values), (('-r', '--robot'), 'robots'))
        self.assertEqual(c.required, {'tool'})

    def test_tui_builds_the_plugin_command_line(self):
        m = Model(self.ws)
        m.index = next(i for i, c in enumerate(m.commands) if c.name == 'app')
        self.assertIn('tool', m.problem())
        m.set_value(m.opt('tool'), 'rviz')
        m.set_value(m.opt('robot'), 'sim')
        m.dry_run = True
        self.assertIsNone(m.problem())
        self.assertEqual(m.argv(), ['--dry-run', 'app', 'rviz', '--robot', 'sim'])

    def test_completion_offers_plugin_values(self):
        self.assertIn('foxglove', complete(self.ws, ['app', '']))
        self.assertIn('white', complete(self.ws, ['app', 'rviz', '-r', '']))
        self.assertNotIn('--dry-run', complete(self.ws, ['app', '--']))


class BoundaryTest(unittest.TestCase):
    def test_cross_domain_dependency_is_rejected(self):
        ws = make_ws()
        try:
            xml = os.path.join(ws.root, 'domains', 'main', 'src', 'main_core', 'package.xml')
            with open(xml, 'w') as f:
                f.write(
                    '<package><name>main_core</name><depend>localization_core</depend></package>'
                )
            r = subprocess.run(
                [
                    sys.executable,
                    os.path.join(ROOT, 'tools', 'check_boundaries.py'),
                    ws.root,
                    'main',
                    'localization',
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn('depends on localization_core', r.stdout)
        finally:
            shutil.rmtree(ws.root)

    def test_clean_tree_passes(self):
        ws = make_ws()
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    os.path.join(ROOT, 'tools', 'check_boundaries.py'),
                    ws.root,
                    'main',
                    'localization',
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout)
        finally:
            shutil.rmtree(ws.root)


class DryRunTest(unittest.TestCase):
    """--dry-run must print commands and change nothing."""

    def test_deploy_dry_run_touches_nothing(self):
        ws = make_ws()
        try:
            args = argparse.Namespace(
                domains=['main'],
                robot='sim',
                no_build=True,
                persist=False,
                allow_skew=False,
                no_rollback=False,
                jobs='auto',
                dry_run=True,
            )
            bdir = ws.build_dir('amd64', 'main')
            os.makedirs(os.path.join(bdir, 'install'))
            with open(os.path.join(bdir, 'BASE_FINGERPRINT'), 'w') as f:
                f.write('x')
            os.makedirs(os.path.join(ws.root, 'docker'))
            shutil.copy(
                os.path.join(ROOT, 'docker', 'compose.yaml'), os.path.join(ws.root, 'docker')
            )
            with contextlib.redirect_stderr(io.StringIO()):
                cli.cmd_deploy(ws, args)
            self.assertFalse(os.path.exists(os.path.join(ws.root, '.sim-robot')))
        finally:
            shutil.rmtree(ws.root)


if __name__ == '__main__':
    unittest.main()
