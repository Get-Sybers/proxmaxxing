"""Unit tests for get_sybers.cluster.to_config_yaml: the inventory files the
discovery role writes must satisfy the repository's yamllint style (indented
sequences, insertion order, block style) and round-trip losslessly.
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest
import yaml

from ansible.errors import AnsibleFilterError
from ansible_collections.get_sybers.cluster.plugins.filter import to_config_yaml as mod

DOC = {
    'node': {
        'name': 'pi-01',
        'hardware': {'cpu': 'Intel', 'cpus': 24},
        'disks': [{'dev': 'nvme0n1', 'size': '3.6T'}, {'dev': 'sda', 'role': 'tank (ZFS)'}],
        'network': {'vmbr0': {'ip': '192.0.2.10/24', 'ports': ['nic0']}},
        'empty_list': [],
        'empty_map': {},
        'unicode': 'café',
    },
}

EXPECTED = """node:
  name: pi-01
  hardware:
    cpu: Intel
    cpus: 24
  disks:
    - dev: nvme0n1
      size: 3.6T
    - dev: sda
      role: tank (ZFS)
  network:
    vmbr0:
      ip: 192.0.2.10/24
      ports:
        - nic0
  empty_list: []
  empty_map: {}
  unicode: café
"""


def test_renders_indented_block_yaml_in_insertion_order():
    assert mod.to_config_yaml(DOC) == EXPECTED


class TaggedStr(str):
    """Stand-in for Ansible's tagged str subclasses."""


class TaggedInt(int):
    """Stand-in for Ansible's tagged int subclasses."""


def test_subclassed_scalars_render_as_their_plain_values():
    doc = {TaggedStr('node'): {TaggedStr('name'): TaggedStr('pi-01'), 'cpus': TaggedInt(24), 'up': True, 'ratio': 0.5,
                               'disks': [{TaggedStr('dev'): TaggedStr('sda')}]}}
    text = mod.to_config_yaml(doc)
    assert text == "node:\n  name: pi-01\n  cpus: 24\n  up: true\n  ratio: 0.5\n  disks:\n    - dev: sda\n"
    assert yaml.safe_load(text) == {'node': {'name': 'pi-01', 'cpus': 24, 'up': True, 'ratio': 0.5, 'disks': [{'dev': 'sda'}]}}


def test_the_dumper_is_the_pure_python_emitter():
    # libyaml's C emitter ignores increase_indent, so the result would silently
    # lose the sequence indentation yamllint requires.
    assert not issubclass(mod._ConfigDumper, getattr(yaml, 'CSafeDumper', ()))
    assert issubclass(mod._ConfigDumper, yaml.SafeDumper)


def test_round_trips_losslessly():
    assert yaml.safe_load(mod.to_config_yaml(DOC)) == DOC


def test_long_scalars_fold_only_past_the_requested_width():
    text = mod.to_config_yaml({'k': 'x' * 100})
    assert '\n' not in text.strip()


@pytest.mark.parametrize('bad', [[], 'x', 3])
def test_non_mapping_input_is_a_clean_error(bad):
    with pytest.raises(AnsibleFilterError):
        mod.to_config_yaml(bad)
