#!/usr/bin/env python3
"""Domain boundary rules, enforced in CI (`ditx lint`):

1. a domain may depend on base packages and ROS/system packages, never on a
   package of another domain (talk through topics in contract.yaml instead);
2. every package name starts with its domain name (unique across repos);
3. every domain has <domain>_bringup with launch/bringup.launch.py.

usage: check_boundaries.py WORKSPACE_ROOT DOMAIN...
"""

import os
import re
import sys


def packages(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != 'build']
        if 'COLCON_IGNORE' in filenames:
            dirnames[:] = []
            continue
        if 'package.xml' in filenames:
            text = open(os.path.join(dirpath, 'package.xml'), encoding='utf-8').read()
            name = re.search(r'<name>\s*(\S+?)\s*</name>', text).group(1)
            deps = set(re.findall(r'<(?:\w+_)?depend>\s*(\S+?)\s*</(?:\w+_)?depend>', text))
            out[name] = (dirpath, deps)
            dirnames[:] = []
    return out


def main():
    root, domains = sys.argv[1], sys.argv[2:]
    owner = {}
    per_domain = {}
    for d in domains:
        per_domain[d] = packages(os.path.join(root, 'domains', d))
        for p in per_domain[d]:
            owner[p] = d
    errors = []
    for d, pkgs in per_domain.items():
        for name, (path, deps) in pkgs.items():
            rel = os.path.relpath(path, root)
            if not name.startswith(d + '_'):
                errors.append(f'{rel}: package {name} must be prefixed with "{d}_"')
            for dep in sorted(deps):
                if owner.get(dep, d) != d:
                    errors.append(
                        f'{rel}: {name} depends on {dep} from domain {owner[dep]}; '
                        f'cross-domain data goes through topics in contract.yaml'
                    )
        if f'{d}_bringup' not in pkgs:
            errors.append(f'domains/{d}: missing package {d}_bringup')
        elif not os.path.isfile(
            os.path.join(pkgs[f'{d}_bringup'][0], 'launch', 'bringup.launch.py')
        ):
            errors.append(f'domains/{d}: {d}_bringup/launch/bringup.launch.py missing')
    for e in errors:
        print(f'FAIL  {e}')
    print('ok' if not errors else f'{len(errors)} boundary violation(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
