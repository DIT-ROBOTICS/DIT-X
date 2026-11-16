import os
import subprocess
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, '..', 'scripts', 'gen_contract.py')
CONTRACT = os.path.join(HERE, '..', 'contract.yaml')


def run(contract_dict, tmp_path):
    p = tmp_path / 'c.yaml'
    p.write_text(yaml.safe_dump(contract_dict))
    return subprocess.run([sys.executable, GEN, str(p), '--check'], capture_output=True, text=True)


@pytest.fixture
def contract():
    with open(CONTRACT) as f:
        return yaml.safe_load(f)


def test_repo_contract_is_valid(contract, tmp_path):
    assert run(contract, tmp_path).returncode == 0


def test_rejects_unknown_qos(contract, tmp_path):
    contract['topics']['LOCALIZATION_POSE']['qos'] = 'fast'
    r = run(contract, tmp_path)
    assert r.returncode == 1 and 'LOCALIZATION_POSE' in r.stderr


def test_rejects_bad_name(contract, tmp_path):
    contract['topics']['LOCALIZATION_POSE']['name'] = 'final_pose'
    assert run(contract, tmp_path).returncode == 1


def test_rejects_duplicate_name(contract, tmp_path):
    contract['topics']['DUP'] = dict(contract['topics']['LOCALIZATION_POSE'])
    r = run(contract, tmp_path)
    assert r.returncode == 1 and 'already used' in r.stderr


def test_rejects_unknown_domain(contract, tmp_path):
    contract['topics']['LOCALIZATION_POSE']['subscribers'] = ['sima']
    assert run(contract, tmp_path).returncode == 1


def test_generated_python_is_valid(contract, tmp_path):
    out = tmp_path / 'contract.py'
    subprocess.run([sys.executable, GEN, CONTRACT, '--py', str(out)], check=True)
    compile(out.read_text(), str(out), 'exec')


def add_topic(contract, key, **fields):
    t = {'type': 'std_msgs/msg/Bool', 'qos': 'command', 'publisher': 'main', 'subscribers': []}
    contract['topics'][key] = {**t, **fields}
    return contract['topics'][key]


def test_firmware_names_are_exempt_but_need_the_flag(contract, tmp_path):
    t = add_topic(
        contract, 'FIRMWARE_CMD_VEL', name='/cmd_vel', firmware=True, subscribers=['firmware']
    )
    assert run(contract, tmp_path).returncode == 0
    del t['firmware']
    assert run(contract, tmp_path).returncode == 1


def test_external_names_are_exempt_but_need_the_flag(contract, tmp_path):
    t = add_topic(contract, 'MAIN_SCORE', name='/game_score', external=True)
    assert run(contract, tmp_path).returncode == 0
    del t['external']
    assert run(contract, tmp_path).returncode == 1


def test_firmware_is_not_a_domain_for_normal_topics(contract, tmp_path):
    add_topic(contract, 'MAIN_FLAG', name='/robot/main/flag', subscribers=['firmware'])
    assert run(contract, tmp_path).returncode == 1


def test_firmware_publisher_needs_hardware_flag(contract, tmp_path):
    t = add_topic(contract, 'FIRMWARE_PLUG', name='/plug', firmware=True, publisher='firmware')
    r = run(contract, tmp_path)
    assert r.returncode == 1 and 'hardware' in r.stderr
    t['hardware'] = True
    assert run(contract, tmp_path).returncode == 0


def test_flags_are_only_for_topics(contract, tmp_path):
    next(iter(contract['services'].values()))['firmware'] = True
    assert run(contract, tmp_path).returncode == 1


DOCK = {
    'name': '/robot/navigation/dock_robot',
    'type': 'opennav_docking_msgs/action/DockRobot',
    'server': 'navigation',
    'clients': ['main'],
}


def test_action_type_must_be_an_action(contract, tmp_path):
    contract['actions'] = {
        'NAVIGATION_DOCK': {**DOCK, 'type': 'opennav_docking_msgs/msg/DockRobot'}
    }
    assert run(contract, tmp_path).returncode == 1


def test_generated_python_has_actions(contract, tmp_path):
    contract['actions'] = {'NAVIGATION_DOCK': DOCK}
    src = tmp_path / 'c.yaml'
    src.write_text(yaml.safe_dump(contract))
    out = tmp_path / 'contract.py'
    subprocess.run([sys.executable, GEN, str(src), '--py', str(out)], check=True)
    assert "NAVIGATION_DOCK = Action('/robot/navigation/dock_robot'" in out.read_text()
