"""Unit tests for get_sybers.cluster.ceph_info (§12).
The module is read-only by construction: callers pick a key from QUERY_MAP
and never supply a command prefix. These tests pin that contract and the
JSON handling of ``run_query`` with a fake rados cluster, so no Ceph is
needed (the ``rados`` import is optional at module level).
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type
import json
from ansible_collections.get_sybers.cluster.plugins.modules import ceph_info as mod


class FakeCluster:
    """Stand-in for rados.Rados: records mon_command calls, returns canned output."""

    def __init__(self, ret=0, out=b'', err=''):
        self.ret = ret
        self.out = out
        self.err = err
        self.calls = []

    def mon_command(self, cmd, inbuf, timeout):
        self.calls.append((json.loads(cmd), inbuf, timeout))
        return self.ret, self.out, self.err


MUTATING_WORDS = ('create', 'rm', 'del', 'set', 'add', 'purge', 'destroy', 'reweight', 'repair')


def test_query_map_is_read_only_by_construction():
    for name, cmd in mod.QUERY_MAP.items():
        words = cmd['prefix'].replace('-', ' ').replace('_', ' ').split()
        assert not any(w in MUTATING_WORDS for w in words), name
        assert 'format' not in cmd, name


def test_default_queries_are_all_allowlisted():
    assert set(mod.DEFAULT_QUERIES) <= set(mod.QUERY_MAP)
    assert len(mod.DEFAULT_QUERIES) == len(set(mod.DEFAULT_QUERIES))


def test_run_query_adds_json_format_without_mutating_the_allowlist():
    cluster = FakeCluster(out=b'{"ok": true}')
    before = dict(mod.QUERY_MAP['status'])
    value, err = mod.run_query(cluster, 'status', 7)
    assert (value, err) == ({'ok': True}, None)
    assert cluster.calls == [({'prefix': 'status', 'format': 'json'}, b'', 7)]
    assert mod.QUERY_MAP['status'] == before


def test_run_query_reports_a_nonzero_rc_as_an_error_not_a_result():
    cluster = FakeCluster(ret=-22, err='invalid command\n')
    value, err = mod.run_query(cluster, 'device_ls', 30)
    assert value is None
    assert err == 'rc=-22 invalid command'


def test_run_query_distinguishes_empty_output_from_null():
    value, err = mod.run_query(FakeCluster(out=b'  \n'), 'fsid', 30)
    assert (value, err) == ({}, None)


def test_run_query_wraps_non_json_output_instead_of_dropping_it():
    value, err = mod.run_query(FakeCluster(out=b'2026-10-09 some text'), 'fsid', 30)
    assert err is None
    assert value == {'_raw': '2026-10-09 some text'}


def test_run_query_accepts_str_output_too():
    value, err = mod.run_query(FakeCluster(out='{"a": 1}'), 'health', 30)
    assert (value, err) == ({'a': 1}, None)


def test_to_text_safe_never_raises():
    class Evil(Exception):
        def __str__(self):
            raise RuntimeError('no str for you')
    assert isinstance(mod.to_text_safe(Evil()), str)
    assert mod.to_text_safe(ValueError('boom')) == 'boom'
