"""Unit tests for get_sybers.cluster.config_merge / config_drift.
The discovery role's whole contract rests on these two filters: fill keeps
what the operator wrote and adds what is missing, overwrite replaces discovered
values but keeps annotations, keyed lists merge element-wise, and null never
wins. No Ansible runtime is needed.
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleFilterError
from ansible_collections.get_sybers.cluster.plugins.filter import config_merge as mod

LIST_KEYS = {'disks': 'dev', 'vms': 'id'}


def _existing():
    return {
        'name': 'pi-01',
        'kernel': '6.14-old',
        'hardware': {'cpu': 'Old CPU', 'cpus': 24},
        'disks': [
            {'dev': 'nvme0n1', 'size': '3.6T', 'role': 'rpool (ZFS root)'},
            {'dev': 'sda', 'size': '3.6T', 'role': 'tank (ZFS)'},
        ],
        'guests': {'vms': [{'id': 9400, 'name': 'Home-Velo', 'status': 'running'}]},
        'tags': ['a', 'b'],
    }


def _discovered():
    return {
        'name': 'pi-01',
        'kernel': '7.0.14-8-pve',
        'mgmt_ip': '192.0.2.10',
        'hardware': {'cpu': 'Intel Core Ultra 9 275HX', 'cpus': 24, 'mem_total_mb': 128000},
        'disks': [
            {'dev': 'nvme0n1', 'size': '3.6T', 'model': 'CT4000P3PSSD8'},
            {'dev': 'nvme1n1', 'size': '3.6T', 'model': 'CT4000P3PSSD8'},
        ],
        'guests': {'vms': [{'id': 9400, 'name': 'Home-Velo', 'status': 'stopped'}, {'id': 9509, 'name': 'sof-elk', 'status': 'stopped'}]},
        'tags': ['c'],
        'unknown': None,
    }


def test_fill_keeps_existing_values_and_adds_missing_ones():
    out = mod.config_merge(_existing(), _discovered(), list_keys=LIST_KEYS)
    assert out['kernel'] == '6.14-old'
    assert out['mgmt_ip'] == '192.0.2.10'
    assert out['hardware'] == {'cpu': 'Old CPU', 'cpus': 24, 'mem_total_mb': 128000}
    assert out['tags'] == ['a', 'b']
    assert 'unknown' not in out


def test_fill_merges_keyed_lists_element_wise_and_appends_new_members():
    out = mod.config_merge(_existing(), _discovered(), list_keys=LIST_KEYS)
    assert [d['dev'] for d in out['disks']] == ['nvme0n1', 'sda', 'nvme1n1']
    assert out['disks'][0] == {'dev': 'nvme0n1', 'size': '3.6T', 'role': 'rpool (ZFS root)', 'model': 'CT4000P3PSSD8'}
    assert out['disks'][1] == {'dev': 'sda', 'size': '3.6T', 'role': 'tank (ZFS)'}
    assert out['guests']['vms'][0]['status'] == 'running'
    assert out['guests']['vms'][1]['id'] == 9509


def test_overwrite_replaces_discovered_values_but_keeps_annotations():
    out = mod.config_merge(_existing(), _discovered(), overwrite=True, list_keys=LIST_KEYS)
    assert out['kernel'] == '7.0.14-8-pve'
    assert out['hardware']['cpu'] == 'Intel Core Ultra 9 275HX'
    assert out['tags'] == ['c']
    assert out['disks'][0]['role'] == 'rpool (ZFS root)'
    assert out['disks'][0]['model'] == 'CT4000P3PSSD8'
    assert out['guests']['vms'][0]['status'] == 'stopped'
    assert 'unknown' not in out


def test_null_never_fills_or_overwrites():
    out = mod.config_merge({'a': 1}, {'a': None, 'b': None}, overwrite=True)
    assert out == {'a': 1}


def test_null_is_stripped_from_new_nested_values():
    out = mod.config_merge({}, {'hw': {'cpu': None, 'cpus': 8}, 'l': [{'dev': 'a', 'serial': None}]}, list_keys={'l': 'dev'})
    assert out == {'hw': {'cpus': 8}, 'l': [{'dev': 'a'}]}
    assert mod.config_drift({}, {'hw': {'cpu': None, 'cpus': 8}}) == [{'path': 'hw', 'config': None, 'live': {'cpus': 8}}]


def test_dotted_list_keys_pick_the_identity_per_path():
    existing = {'pools': [{'id': 'ADMIN', 'note': 'kept'}], 'ceph': {'pools': [{'name': 'rbd', 'note': 'kept'}]}}
    discovered = {'pools': [{'id': 'ADMIN', 'comment': 'x'}, {'id': 'NEW'}], 'ceph': {'pools': [{'name': 'rbd', 'size': 2}]}}
    keys = {'pools': 'id', 'ceph.pools': 'name'}
    out = mod.config_merge(existing, discovered, list_keys=keys)
    assert out['pools'] == [{'id': 'ADMIN', 'note': 'kept', 'comment': 'x'}, {'id': 'NEW'}]
    assert out['ceph']['pools'] == [{'name': 'rbd', 'note': 'kept', 'size': 2}]
    drift = mod.config_drift(existing, discovered, list_keys=keys)
    assert sorted(d['path'] for d in drift) == ['ceph.pools[name=rbd].size', 'pools[id=ADMIN].comment', 'pools[id=NEW]']


def test_key_order_is_configuration_first_then_new_keys():
    out = mod.config_merge({'z': 1, 'a': 2}, {'a': 3, 'm': 4, 'z': 5})
    assert list(out) == ['z', 'a', 'm']


def test_input_is_not_mutated():
    existing = _existing()
    snapshot = _existing()
    mod.config_merge(existing, _discovered(), overwrite=True, list_keys=LIST_KEYS)
    assert existing == snapshot


def test_drift_reports_missing_and_differing_leaves_only():
    drift = mod.config_drift(_existing(), _discovered(), list_keys=LIST_KEYS)
    paths = dict((d['path'], d) for d in drift)
    assert paths['kernel'] == {'path': 'kernel', 'config': '6.14-old', 'live': '7.0.14-8-pve'}
    assert paths['mgmt_ip']['config'] is None
    assert paths['hardware.cpu']['live'] == 'Intel Core Ultra 9 275HX'
    assert paths['hardware.mem_total_mb']['config'] is None
    assert 'hardware.cpus' not in paths
    assert paths['disks[dev=nvme0n1].model']['config'] is None
    assert paths['disks[dev=nvme1n1]']['config'] is None
    assert 'disks[dev=sda]' not in paths
    assert paths['guests.vms[id=9400].status']['live'] == 'stopped'
    assert paths['tags'] == {'path': 'tags', 'config': ['a', 'b'], 'live': ['c']}
    assert 'unknown' not in paths


def test_no_drift_when_configuration_already_matches():
    disc = _discovered()
    merged = mod.config_merge(_existing(), disc, overwrite=True, list_keys=LIST_KEYS)
    assert mod.config_drift(merged, disc, list_keys=LIST_KEYS) == []


@pytest.mark.parametrize('bad', [[], 'x', 3])
def test_non_mapping_input_is_a_clean_error(bad):
    with pytest.raises(AnsibleFilterError):
        mod.config_merge(bad, {})
    with pytest.raises(AnsibleFilterError):
        mod.config_drift({}, bad)


def test_filter_module_exposes_both_filters():
    assert set(mod.FilterModule().filters()) == {'config_merge', 'config_drift'}
