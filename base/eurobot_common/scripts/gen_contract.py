#!/usr/bin/env python3
"""Generate C++/Python/Markdown from contract.yaml.

Usage: gen_contract.py CONTRACT {--cpp OUT | --py OUT | --md OUT | --check}
Validation errors exit 1 with a message that points at the offending entry.
"""

import argparse
import re
import sys

import yaml

QOS_KEYS = {
    'reliability': ('reliable', 'best_effort'),
    'durability': ('volatile', 'transient_local'),
    'history': ('keep_last', 'keep_all'),
}
# rclcpp::QoS method names (`volatile` is a C++ keyword)
CPP_DURABILITY = {'volatile': 'durability_volatile', 'transient_local': 'transient_local'}
NAME_RE = re.compile(r'^/robot/[a-z0-9_]+(/[a-z0-9_]+)+$')
TYPE_RE = re.compile(r'^[a-z0-9_]+/(msg|srv|action)/[A-Z][A-Za-z0-9]*$')
KEY_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')


def fail(msg):
    sys.exit(f'contract.yaml: {msg}')


def load(path):
    with open(path, encoding='utf-8') as f:
        c = yaml.safe_load(f)
    domains = c.get('domains') or fail('missing domains')
    who = set(domains) | {'*'}
    for name, q in (c.get('qos') or {}).items():
        for k, allowed in QOS_KEYS.items():
            if q.get(k) not in allowed:
                fail(f'qos {name}: {k} must be one of {allowed}')
        if q['history'] == 'keep_last' and int(q.get('depth', 0)) < 1:
            fail(f'qos {name}: keep_last needs depth >= 1')
    names = {}
    for section, (pub, sub) in (
        ('topics', ('publisher', 'subscribers')),
        ('services', ('server', 'clients')),
    ):
        for key, t in (c.get(section) or {}).items():
            where = f'{section}.{key}'
            if not KEY_RE.match(key):
                fail(f'{where}: key must be UPPER_SNAKE_CASE')
            if not NAME_RE.match(t.get('name', '')):
                fail(f'{where}: name must look like /robot/<domain>/<thing>')
            if t['name'] in names:
                fail(f'{where}: name {t["name"]} already used by {names[t["name"]]}')
            names[t['name']] = where
            if not TYPE_RE.match(t.get('type', '')):
                fail(f'{where}: type must look like pkg/msg/Type')
            if section == 'topics' and t.get('qos') not in c['qos']:
                fail(f'{where}: qos must be one of {list(c["qos"])}')
            if t.get(pub) not in who:
                fail(f'{where}: {pub} must be a domain or "*"')
            for s in t.get(sub, []):
                if s not in who:
                    fail(f'{where}: {sub} entry {s!r} is not a domain')
    return c


def gen_cpp(c):
    out = [
        '// Generated from contract.yaml by gen_contract.py. Do not edit.',
        '#pragma once',
        '',
        '#include <rclcpp/qos.hpp>',
        '',
        'namespace eurobot_common::contract',
        '{',
        '',
        'struct Topic',
        '{',
        '  const char * name;',
        '  const char * type;',
        '  rclcpp::QoS (*qos)();',
        '};',
        '',
        'struct Service',
        '{',
        '  const char * name;',
        '  const char * type;',
        '};',
        '',
    ]
    for name, q in c['qos'].items():
        depth = int(q.get('depth', 1))
        hist = 'KeepLast(%d)' % depth if q['history'] == 'keep_last' else 'KeepAll()'
        out += [
            f'inline rclcpp::QoS qos_{name}()',
            '{',
            f'  return rclcpp::QoS(rclcpp::{hist})',
            f'         .{q["reliability"]}()',
            f'         .{CPP_DURABILITY[q["durability"]]}();',
            '}',
            '',
        ]
    for key, t in c.get('topics', {}).items():
        out.append(f'// {t.get("doc", "").strip()}')
        out.append(
            f'inline constexpr Topic {key}{{"{t["name"]}", "{t["type"]}", &qos_{t["qos"]}}};'
        )
    out.append('')
    for key, s in c.get('services', {}).items():
        out.append(f'// {s.get("doc", "").strip()}')
        out.append(f'inline constexpr Service {key}{{"{s["name"]}", "{s["type"]}"}};')
    out += [
        '',
        'inline constexpr const char * DOMAINS[] = {'
        + ', '.join(f'"{d}"' for d in c['domains'])
        + '};',
        '',
        '}  // namespace eurobot_common::contract',
        '',
    ]
    return '\n'.join(out)


def gen_py(c):
    out = [
        '# Generated from contract.yaml by gen_contract.py. Do not edit.',
        'from dataclasses import dataclass',
        '',
        'from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy',
        '',
        f'DOMAINS = {tuple(c["domains"])!r}',
        '',
    ]
    for name, q in c['qos'].items():
        out += [
            f'def qos_{name}():',
            '    return QoSProfile(',
            f'        history=HistoryPolicy.{q["history"].upper()},',
            f'        depth={int(q.get("depth", 1))},',
            f'        reliability=ReliabilityPolicy.{q["reliability"].upper()},',
            f'        durability=DurabilityPolicy.{q["durability"].upper()},',
            '    )',
            '',
            '',
        ]
    out += [
        '@dataclass(frozen=True)',
        'class Topic:',
        '    name: str',
        '    type: str',
        '    qos_name: str',
        '',
        '    def qos(self):',
        '        return globals()["qos_" + self.qos_name]()',
        '',
        '',
        '@dataclass(frozen=True)',
        'class Service:',
        '    name: str',
        '    type: str',
        '',
        '',
    ]
    for key, t in c.get('topics', {}).items():
        out.append(f'{key} = Topic({t["name"]!r}, {t["type"]!r}, {t["qos"]!r})')
    for key, s in c.get('services', {}).items():
        out.append(f'{key} = Service({s["name"]!r}, {s["type"]!r})')
    out += ['', 'TOPICS = {t.name: t for t in (' + ', '.join(c.get('topics', {})) + ',)}', '']
    return '\n'.join(out)


def gen_md(c):
    out = [
        '# Interface contract',
        '',
        '> Generated from `base/eurobot_common/contract.yaml` by `ditx contract md`. Do not edit.',
        '',
        '## QoS profiles',
        '',
        '| profile | reliability | durability | history | depth |',
        '|---|---|---|---|---|',
    ]
    for name, q in c['qos'].items():
        row = [
            f'`{name}`',
            q['reliability'],
            q['durability'],
            q['history'],
            str(q.get('depth', '')),
        ]
        out.append('| ' + ' | '.join(row) + ' |')
    out += [
        '',
        '## Topics',
        '',
        '| name | type | QoS | publisher | subscribers | rate | description |',
        '|---|---|---|---|---|---|---|',
    ]
    for t in c.get('topics', {}).values():
        out.append(
            f'| `{t["name"]}` | `{t["type"]}` | {t["qos"]} | {t["publisher"]} | '
            f'{", ".join(t.get("subscribers", []))} | {t.get("rate_hz", "")} | {t.get("doc", "")} |'
        )
    out += [
        '',
        '## Services',
        '',
        '| name | type | server | clients | description |',
        '|---|---|---|---|---|',
    ]
    for s in c.get('services', {}).values():
        out.append(
            f'| `{s["name"]}` | `{s["type"]}` | {s["server"]} | '
            f'{", ".join(s.get("clients", []))} | {s.get("doc", "")} |'
        )
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('contract')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--cpp')
    g.add_argument('--py')
    g.add_argument('--md')
    g.add_argument('--check', action='store_true')
    a = ap.parse_args()
    c = load(a.contract)
    for path, fn in ((a.cpp, gen_cpp), (a.py, gen_py), (a.md, gen_md)):
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(fn(c))


if __name__ == '__main__':
    main()
