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
